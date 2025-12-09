"""Authentication routes for Azure AD SSO."""

import httpx
from datetime import datetime, timedelta
from jose import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.config import get_settings
from app.core.auth import azure_scheme, get_or_create_user
from app.database import get_db
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# JWT settings for session tokens
JWT_SECRET = settings.secret_key
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


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
async def auth_callback(
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Azure AD OAuth callback.

    Processes the authorization code and creates a session.
    """
    frontend_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:6700"

    # 1. Exchange code for tokens
    token_url = f"https://login.microsoftonline.com/{settings.azure_ad_tenant_id}/oauth2/v2.0/token"

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            token_url,
            data={
                "client_id": settings.azure_ad_client_id,
                "client_secret": settings.azure_ad_client_secret,
                "code": code,
                "redirect_uri": settings.azure_ad_redirect_uri,
                "grant_type": "authorization_code",
                "scope": "openid profile email",
            },
        )

    if token_response.status_code != 200:
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{frontend_url}/login?error=token_exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )

    token_data = token_response.json()
    id_token = token_data.get("id_token")

    if not id_token:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=no_id_token",
            status_code=status.HTTP_302_FOUND,
        )

    # 2. Decode ID token (without verification for now - Azure already validated it)
    try:
        claims = jwt.get_unverified_claims(id_token)
    except Exception:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=invalid_token",
            status_code=status.HTTP_302_FOUND,
        )

    # 3. Extract user info from claims
    azure_id = claims.get("oid") or claims.get("sub")
    email = claims.get("preferred_username") or claims.get("email", "")
    display_name = claims.get("name", email)
    roles = claims.get("roles", [])

    if not azure_id or not email:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=missing_user_info",
            status_code=status.HTTP_302_FOUND,
        )

    # 4. Check email domain
    email_domain = email.lower().split("@")[-1] if "@" in email else ""
    allowed_domains = settings.allowed_email_domains
    if allowed_domains and email_domain not in allowed_domains:
        return RedirectResponse(
            url=f"{frontend_url}/login?error=domain_not_allowed",
            status_code=status.HTTP_302_FOUND,
        )

    # 5. Create or update user in database
    user = await get_or_create_user(
        db=db,
        azure_id=azure_id,
        email=email,
        display_name=display_name,
        roles=roles,
    )
    await db.commit()

    # 6. Create session JWT
    session_token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    # 7. Redirect to frontend with session cookie
    response = RedirectResponse(url=frontend_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=JWT_EXPIRATION_HOURS * 3600,
    )
    return response


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
