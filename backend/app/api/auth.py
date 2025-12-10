"""Authentication routes for Azure AD SSO."""

from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, RedirectResponse
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.config import get_settings
from app.core.auth import get_or_create_user
from app.core.logging import get_logger
from app.database import get_db
from app.schemas.user import UserResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# JWT settings for session tokens
JWT_SECRET = settings.secret_key
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


@router.get("/debug")
async def auth_debug() -> dict:
    """Debug endpoint showing Azure AD configuration (non-sensitive parts)."""
    return {
        "tenant_id": settings.azure_ad_tenant_id,
        "client_id": settings.azure_ad_client_id,
        "redirect_uri": settings.azure_ad_redirect_uri,
        "client_secret_set": bool(settings.azure_ad_client_secret),
        "allowed_email_domains": settings.allowed_email_domains,
    }


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
    logger.info("auth_login_redirect", auth_url=auth_url)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def auth_callback(
    code: str,
    state: str | None = None,  # noqa: ARG001 - Reserved for CSRF protection
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Azure AD OAuth callback.

    Processes the authorization code and creates a session.
    """
    logger.info("auth_callback_started", code_length=len(code) if code else 0)

    # Derive frontend URL from the redirect URI (same origin for cookie to work)
    # E.g., https://xxx.ngrok-free.dev/api/v1/auth/callback -> https://xxx.ngrok-free.dev
    redirect_uri = settings.azure_ad_redirect_uri
    frontend_url = (
        redirect_uri.rsplit("/api/", 1)[0]
        if "/api/" in redirect_uri
        else (
            settings.cors_origins[0]
            if settings.cors_origins
            else "http://localhost:6700"
        )
    )
    logger.info("auth_callback_frontend_url", frontend_url=frontend_url)

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

    logger.info("auth_callback_token_response", status=token_response.status_code)

    if token_response.status_code != 200:
        # Redirect to frontend with error
        logger.warning("auth_callback_token_failed", response=token_response.text)
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
    except Exception as e:
        logger.warning(
            "oauth_token_decode_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
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
    # Use secure cookie if redirect URI is HTTPS
    is_https = frontend_url.startswith("https://")
    response = RedirectResponse(url=frontend_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=JWT_EXPIRATION_HOURS * 3600,
    )
    return response


@router.post("/logout")
async def logout(
    current_user: CurrentUser,  # noqa: ARG001
) -> JSONResponse:
    """Log out current user.

    Clears session cookie and returns success message.
    """
    response = JSONResponse(content={"message": "Successfully logged out"})
    response.delete_cookie(
        key="session",
        path="/",
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)
