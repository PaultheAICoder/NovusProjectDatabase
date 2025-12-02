"""Authentication routes for Azure AD SSO."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser
from app.config import get_settings
from app.core.auth import azure_scheme
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/login")
async def login() -> RedirectResponse:
    """Initiate Azure AD SSO login.

    Redirects to Azure AD for authentication.
    """
    # Build Azure AD authorization URL
    auth_url = (
        f"https://login.microsoftonline.com/{settings.azure_ad_tenant_id}"
        f"/oauth2/v2.0/authorize"
        f"?client_id={settings.azure_ad_client_id}"
        f"&response_type=code"
        f"&redirect_uri={settings.azure_ad_redirect_uri}"
        f"&scope=openid profile email"
        f"&response_mode=query"
    )
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def auth_callback(code: str, state: str | None = None) -> RedirectResponse:
    """Handle Azure AD OAuth callback.

    Processes the authorization code and creates a session.
    """
    # In a production app, you would:
    # 1. Exchange code for tokens
    # 2. Validate tokens
    # 3. Create session
    # 4. Redirect to frontend

    # For now, redirect to frontend (actual implementation depends on session strategy)
    frontend_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:6700"
    return RedirectResponse(url=frontend_url, status_code=status.HTTP_302_FOUND)


@router.post("/logout")
async def logout(current_user: CurrentUser) -> dict[str, str]:
    """Log out current user.

    Clears session and returns success message.
    """
    # In production, clear session cookie here
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)
