"""Azure AD SSO authentication with fastapi-azure-auth."""

from datetime import datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.user import User, UserRole

logger = get_logger(__name__)

settings = get_settings()

# JWT settings (must match auth.py)
JWT_SECRET = settings.secret_key
JWT_ALGORITHM = "HS256"

# Azure AD authentication scheme
azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=settings.azure_ad_client_id,
    tenant_id=settings.azure_ad_tenant_id,
    scopes={
        f"api://{settings.azure_ad_client_id}/user_impersonation": "user_impersonation",
    },
)


async def get_or_create_user(
    db: AsyncSession,
    azure_id: str,
    email: str,
    display_name: str,
    roles: list[str],
) -> User:
    """Get existing user or create new one from Azure AD claims."""
    result = await db.execute(select(User).where(User.azure_id == azure_id))
    user = result.scalar_one_or_none()

    # Determine role from Azure AD app roles
    role = UserRole.ADMIN if "admin" in roles else UserRole.USER

    if user is None:
        # Create new user
        user = User(
            azure_id=azure_id,
            email=email,
            display_name=display_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.flush()
    else:
        # Update last login and potentially role
        user.last_login_at = datetime.utcnow()
        user.role = role
        user.display_name = display_name

    return user


def _is_email_domain_allowed(email: str) -> bool:
    """Check if email domain is in the allowed list."""
    allowed_domains = settings.allowed_email_domains
    if not allowed_domains:
        # Empty list = allow all domains from tenant
        return True

    email_domain = email.lower().split("@")[-1] if "@" in email else ""
    return email_domain in allowed_domains


async def get_user_from_session(
    request: Request,
    db: AsyncSession,
) -> User | None:
    """Get user from session cookie if present."""
    session_token = request.cookies.get("session")
    if not session_token:
        return None

    try:
        payload = jwt.decode(session_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        return result.scalar_one_or_none()
    except (JWTError, ValueError) as e:
        logger.debug(
            "session_token_invalid",
            error_type=type(e).__name__,
        )
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from session cookie or Azure AD token."""
    # First try session cookie
    user = await get_user_from_session(request, db)
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        return user

    # No session cookie - user is not authenticated
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user if they have admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def get_user_id(user: User) -> UUID:
    """Extract user ID for audit fields."""
    return user.id
