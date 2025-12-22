"""Rate limiting configuration using slowapi."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key - user ID if authenticated, IP address otherwise.

    This provides per-user rate limiting for authenticated requests
    and IP-based limiting for unauthenticated requests.
    """
    # Try to get user ID from session
    session_token = request.cookies.get("session")
    if session_token:
        try:
            from jose import jwt

            payload = jwt.decode(
                session_token,
                settings.secret_key,
                algorithms=["HS256"],
            )
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception as e:
            logger.debug(
                "rate_limit_key_fallback_to_ip",
                error_type=type(e).__name__,
            )

    # Fall back to IP address
    return get_remote_address(request)


# Create the limiter instance
# Note: headers_enabled=False because slowapi 0.1.9 has issues with FastAPI's
# auto-serialization of Pydantic models - it can't inject headers when the
# endpoint returns a Pydantic model directly (not a Response object).
limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=settings.rate_limit_storage_uri,
    headers_enabled=False,  # Disabled due to slowapi compatibility issue
    enabled=settings.rate_limit_enabled,
)


# Pre-defined limit decorators for different endpoint types
def search_limit() -> str:
    """Get search endpoint rate limit."""
    return settings.rate_limit_search


def crud_limit() -> str:
    """Get CRUD endpoint rate limit."""
    return settings.rate_limit_crud


def upload_limit() -> str:
    """Get upload endpoint rate limit."""
    return settings.rate_limit_upload


def admin_limit() -> str:
    """Get admin endpoint rate limit."""
    return settings.rate_limit_admin


def auth_limit() -> str:
    """Get auth endpoint rate limit."""
    return settings.rate_limit_auth


def feedback_limit() -> str:
    """Get feedback endpoint rate limit."""
    return settings.rate_limit_feedback


def webhook_limit() -> str:
    """Get webhook endpoint rate limit."""
    return settings.rate_limit_webhook
