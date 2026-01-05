"""Azure AD SSO authentication with fastapi-azure-auth.

Supports three authentication methods:
1. Session cookies (for browser clients via OAuth callback)
2. API tokens (Bearer tokens with npd_ prefix for personal access tokens)
3. Azure AD Bearer tokens (for programmatic API access)

The get_current_user dependency tries session cookie first, then API token,
then falls back to Azure AD Bearer token validation.
"""

from datetime import datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import SecurityScopes
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.user import User, UserRole
from app.services.token_service import TOKEN_PREFIX, TokenService

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


def _map_azure_roles_to_user_role(azure_roles: list[str]) -> UserRole:
    """Map Azure AD roles to internal UserRole.

    Performs case-insensitive matching against the configured admin role name.

    Args:
        azure_roles: List of role names from Azure AD token claims.

    Returns:
        UserRole.ADMIN if admin role is present, UserRole.USER otherwise.
    """
    admin_role = settings.azure_ad_admin_role.lower()
    for role in azure_roles:
        if role.lower() == admin_role:
            return UserRole.ADMIN
    return UserRole.USER


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
    role = _map_azure_roles_to_user_role(roles)

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


async def get_user_from_bearer_token(
    request: Request,
    db: AsyncSession,
) -> User | None:
    """Get user from Bearer token if present and valid.

    Validates the Bearer token from the Authorization header using Azure AD.
    If valid, extracts user claims and creates/updates the user in the database.

    Args:
        request: The incoming HTTP request
        db: Database session for user lookup/creation

    Returns:
        User object if Bearer token is valid, None otherwise
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    # Check for Bearer token format
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug("bearer_token_invalid_format")
        return None

    # Token is extracted by azure_scheme from request headers
    try:
        # Use azure_scheme to validate the Bearer token
        # The scheme validates signature, expiry, audience, and issuer
        security_scopes = SecurityScopes(scopes=[])
        token_claims = await azure_scheme(request, security_scopes)

        if not token_claims:
            logger.debug("bearer_token_validation_returned_none")
            return None

        # Extract claims from the validated token
        # azure_scheme returns the decoded token claims as a dict-like object
        azure_id = token_claims.get("oid") or token_claims.get("sub")
        email = (
            token_claims.get("preferred_username")
            or token_claims.get("email")
            or token_claims.get("upn")
            or ""
        )
        display_name = token_claims.get("name", email)
        roles = token_claims.get("roles", [])

        if not azure_id:
            logger.warning("bearer_token_missing_azure_id")
            return None

        if not email:
            logger.warning("bearer_token_missing_email")
            return None

        # Check email domain
        if not _is_email_domain_allowed(email):
            logger.warning(
                "bearer_token_domain_not_allowed",
                email_domain=email.split("@")[-1] if "@" in email else "",
            )
            return None

        # Create or update user from Azure AD claims
        user = await get_or_create_user(
            db=db,
            azure_id=azure_id,
            email=email,
            display_name=display_name,
            roles=roles if isinstance(roles, list) else [],
        )

        logger.info(
            "bearer_token_authenticated",
            user_id=str(user.id),
            email=user.email,
        )

        return user

    except HTTPException as e:
        # azure_scheme raises HTTPException on validation failure
        logger.debug(
            "bearer_token_validation_failed",
            status_code=e.status_code,
            detail=e.detail,
        )
        return None
    except Exception as e:
        # Auth MUST fail gracefully - return None, don't raise.
        # Broad catch intentional: Azure AD scheme can raise various exceptions
        # and any auth failure should not crash the request.
        logger.debug(
            "bearer_token_unexpected_error",
            error_type=type(e).__name__,
            error=str(e),
        )
        return None


async def get_user_from_api_token(
    request: Request,
    db: AsyncSession,
) -> User | None:
    """Get user from API token if present and valid.

    Validates Bearer tokens that start with the npd_ prefix using TokenService.
    This is for API tokens (personal access tokens) as opposed to Azure AD tokens.

    Args:
        request: The incoming HTTP request
        db: Database session for token validation

    Returns:
        User object if API token is valid, None otherwise
    """
    # Extract Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    # Check for Bearer token format
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]

    # Check if this is an API token (starts with npd_ prefix)
    if not token.startswith(TOKEN_PREFIX):
        return None

    # Validate via TokenService
    try:
        token_service = TokenService(db)
        user = await token_service.validate_token(token)

        if user:
            logger.info(
                "api_token_authenticated",
                user_id=str(user.id),
                email=user.email,
            )
        else:
            logger.debug(
                "api_token_validation_failed",
                reason="invalid_or_expired",
            )

        return user
    except Exception as e:
        # Auth MUST fail gracefully - return None, don't raise.
        # Broad catch intentional: TokenService.validate_token can raise
        # various exceptions and any token validation failure should not
        # crash the request.
        logger.debug(
            "api_token_unexpected_error",
            error_type=type(e).__name__,
            error=str(e),
        )
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from session cookie, API token, or Azure AD Bearer token.

    Authentication is attempted in the following order:
    1. Session cookie (for browser clients using OAuth callback)
    2. API token (Bearer tokens starting with npd_ prefix)
    3. Azure AD Bearer token (for programmatic API access with Azure AD)

    Args:
        request: The incoming HTTP request
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException: 401 if not authenticated, 403 if user is disabled
    """
    # First try session cookie (for browser clients)
    user = await get_user_from_session(request, db)
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        return user

    # Try API token (for npd_* Bearer tokens)
    user = await get_user_from_api_token(request, db)
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        return user

    # Try Azure AD Bearer token (for programmatic API access)
    user = await get_user_from_bearer_token(request, db)
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        return user

    # No valid authentication found
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
