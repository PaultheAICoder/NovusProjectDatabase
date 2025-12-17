"""Authentication routes for Azure AD SSO."""

import hmac
from datetime import datetime, timedelta
from secrets import token_urlsafe

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.config import get_settings
from app.core.auth import azure_scheme, get_or_create_user
from app.core.logging import get_logger
from app.core.rate_limit import auth_limit, limiter
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
@limiter.limit(auth_limit)
async def auth_debug(request: Request) -> dict:
    """Debug endpoint showing Azure AD configuration (non-sensitive parts)."""
    return {
        "tenant_id": settings.azure_ad_tenant_id,
        "client_id": settings.azure_ad_client_id,
        "redirect_uri": settings.azure_ad_redirect_uri,
        "client_secret_set": bool(settings.azure_ad_client_secret),
        "allowed_email_domains": settings.allowed_email_domains,
    }


@router.get("/login")
@limiter.limit(auth_limit)
async def login(request: Request) -> RedirectResponse:
    """Initiate Azure AD SSO login.

    Redirects to Azure AD for authentication.
    Generates CSRF state token stored in secure cookie.
    """
    # Generate CSRF state token
    state = token_urlsafe(32)

    # Build Azure AD authorization URL with state
    auth_url = (
        f"https://login.microsoftonline.com/{settings.azure_ad_tenant_id}"
        f"/oauth2/v2.0/authorize"
        f"?client_id={settings.azure_ad_client_id}"
        f"&response_type=code"
        f"&redirect_uri={settings.azure_ad_redirect_uri}"
        f"&scope=openid profile email"
        f"&response_mode=query"
        f"&state={state}"
    )
    logger.info("auth_login_redirect", auth_url=auth_url)

    # Create response with state cookie
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    # Set state cookie (HTTP-only, 5 minute expiry)
    is_https = settings.azure_ad_redirect_uri.startswith("https://")
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=300,  # 5 minutes
        path="/api/v1/auth",
    )

    return response


@router.get("/callback")
@limiter.limit(auth_limit)
async def auth_callback(
    request: Request,
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Azure AD OAuth callback.

    Validates CSRF state and processes the authorization code.
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

    # Validate CSRF state parameter
    expected_state = request.cookies.get("oauth_state")

    if not state or not expected_state:
        logger.warning(
            "auth_callback_missing_state",
            has_param=bool(state),
            has_cookie=bool(expected_state),
        )
        return RedirectResponse(
            url=f"{frontend_url}/login?error=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(state, expected_state):
        logger.warning("auth_callback_state_mismatch")
        return RedirectResponse(
            url=f"{frontend_url}/login?error=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )

    logger.info("auth_callback_state_validated")

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

    # 2. Verify and decode ID token using Azure AD public keys
    try:
        # Get the key ID from token header
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")

        if not kid:
            logger.warning("oauth_token_missing_kid")
            return RedirectResponse(
                url=f"{frontend_url}/login?error=invalid_token",
                status_code=status.HTTP_302_FOUND,
            )

        # Get signing key from Azure AD JWKS
        signing_key = azure_scheme.openid_config.signing_keys.get(kid)

        if not signing_key:
            logger.warning("oauth_token_unknown_kid", kid=kid)
            return RedirectResponse(
                url=f"{frontend_url}/login?error=invalid_token",
                status_code=status.HTTP_302_FOUND,
            )

        # Verify and decode the token
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.azure_ad_client_id,
            issuer=azure_scheme.openid_config.issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )

        logger.info(
            "oauth_token_verified",
            sub=claims.get("sub"),
            iss=claims.get("iss"),
        )

    except jwt.ExpiredSignatureError:
        logger.warning("oauth_token_expired")
        return RedirectResponse(
            url=f"{frontend_url}/login?error=token_expired",
            status_code=status.HTTP_302_FOUND,
        )
    except jwt.JWTClaimsError as e:
        logger.warning("oauth_token_claims_error", error=str(e))
        return RedirectResponse(
            url=f"{frontend_url}/login?error=invalid_token",
            status_code=status.HTTP_302_FOUND,
        )
    except jwt.JWTError as e:
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

    # Delete the one-time state cookie
    response.delete_cookie(
        key="oauth_state",
        path="/api/v1/auth",
    )

    return response


@router.post("/logout")
@limiter.limit(auth_limit)
async def logout(
    request: Request,
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
@limiter.limit(auth_limit)
async def get_current_user_info(
    request: Request,
    current_user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.post("/test-token")
@limiter.limit(auth_limit)
async def create_test_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a test session token for E2E testing.

    SECURITY: Only available when E2E_TEST_MODE=true AND:
    - Environment is not production (hard block)
    - Valid E2E_TEST_SECRET header is provided (except in development)

    This endpoint is for Playwright E2E tests only.
    """
    # Layer 1: Hard block in production - defense in depth
    # This blocks even if e2e_test_mode is accidentally enabled
    if settings.environment == "production":
        logger.warning(
            "e2e_test_token_blocked_production",
            reason="Production environment blocks E2E test endpoint regardless of config",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Layer 2: Check if E2E test mode is enabled
    if not settings.e2e_test_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Layer 3: Validate secret in non-development environments
    if settings.environment != "development":
        provided_secret = request.headers.get("X-E2E-Test-Secret", "")
        if not settings.e2e_test_secret:
            logger.error(
                "e2e_test_token_no_secret_configured",
                environment=settings.environment,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="E2E test mode misconfigured",
            )
        if not hmac.compare_digest(provided_secret, settings.e2e_test_secret):
            logger.warning(
                "e2e_test_token_invalid_secret",
                client_ip=request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid test secret",
            )

    logger.info(
        "e2e_test_token_created",
        environment=settings.environment,
    )

    # Create or get test user
    test_azure_id = "e2e-test-user-00000000-0000-0000-0000-000000000000"
    test_email = "e2e-test@example.com"
    test_display_name = "E2E Test User"

    user = await get_or_create_user(
        db=db,
        azure_id=test_azure_id,
        email=test_email,
        display_name=test_display_name,
        roles=["user"],
    )
    await db.commit()

    # Create session JWT (same as auth_callback)
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

    response = JSONResponse(
        content={
            "message": "Test session created",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
            },
        }
    )
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=False,  # Test environment uses HTTP
        samesite="lax",
        max_age=JWT_EXPIRATION_HOURS * 3600,
    )
    return response
