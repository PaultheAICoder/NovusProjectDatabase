"""Azure AD SSO authentication with fastapi-azure-auth."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole

settings = get_settings()

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


async def get_current_user(
    token: dict[str, Any] = Depends(azure_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from Azure AD token."""
    azure_id = token.get("oid") or token.get("sub")
    email = token.get("preferred_username") or token.get("email", "")
    display_name = token.get("name", email)
    roles = token.get("roles", [])

    if not azure_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user identifier",
        )

    user = await get_or_create_user(
        db=db,
        azure_id=azure_id,
        email=email,
        display_name=display_name,
        roles=roles,
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


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
