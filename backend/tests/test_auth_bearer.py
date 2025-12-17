"""Tests for Bearer token authentication support.

Tests the get_user_from_bearer_token function and the Bearer token fallback
in get_current_user.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


class TestGetUserFromBearerToken:
    """Tests for the get_user_from_bearer_token helper function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_authorization_header(self):
        """Returns None when no Authorization header is present."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_db = AsyncMock()

        result = await get_user_from_bearer_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_header_format_no_space(self):
        """Returns None when Authorization header has no space."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "BearerTokenWithNoSpace"}
        mock_db = AsyncMock()

        result = await get_user_from_bearer_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_non_bearer_scheme(self):
        """Returns None when Authorization header uses non-Bearer scheme."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        mock_db = AsyncMock()

        result = await get_user_from_bearer_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_bearer_without_token(self):
        """Returns None when Authorization header is 'Bearer ' without token."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer"}
        mock_db = AsyncMock()

        result = await get_user_from_bearer_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_azure_scheme_raises_http_exception(self):
        """Returns None when azure_scheme raises HTTPException (invalid token)."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer invalid-token"}
        mock_db = AsyncMock()

        with patch("app.core.auth.azure_scheme") as mock_scheme:
            mock_scheme.side_effect = HTTPException(
                status_code=401,
                detail="Invalid token",
            )

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_azure_scheme_returns_none(self):
        """Returns None when azure_scheme returns None."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer some-token"}
        mock_db = AsyncMock()

        with patch("app.core.auth.azure_scheme") as mock_scheme:
            mock_scheme.return_value = None

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_missing_azure_id(self):
        """Returns None when token claims are missing azure_id (oid/sub)."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}
        mock_db = AsyncMock()

        mock_claims = {
            # No oid or sub
            "preferred_username": "test@example.com",
            "name": "Test User",
        }

        with patch("app.core.auth.azure_scheme") as mock_scheme:
            mock_scheme.return_value = mock_claims

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_missing_email(self):
        """Returns None when token claims are missing email."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}
        mock_db = AsyncMock()

        mock_claims = {
            "oid": "test-azure-id",
            "name": "Test User",
            # No email/preferred_username/upn
        }

        with patch("app.core.auth.azure_scheme") as mock_scheme:
            mock_scheme.return_value = mock_claims

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_email_domain_not_allowed(self):
        """Returns None when email domain is not in allowed list."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}
        mock_db = AsyncMock()

        mock_claims = {
            "oid": "test-azure-id",
            "preferred_username": "test@external.com",
            "name": "Test User",
        }

        async def mock_azure_scheme(*args, **kwargs):
            return mock_claims

        with (
            patch("app.core.auth.azure_scheme", side_effect=mock_azure_scheme),
            patch("app.core.auth._is_email_domain_allowed") as mock_domain_check,
        ):
            mock_domain_check.return_value = False

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result is None
            mock_domain_check.assert_called_once_with("test@external.com")

    @pytest.mark.asyncio
    async def test_returns_user_for_valid_bearer_token(self):
        """Returns User object for valid Bearer token."""
        from app.core.auth import get_user_from_bearer_token
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-azure-token"}
        mock_db = AsyncMock()

        mock_claims = {
            "oid": "test-azure-oid",
            "preferred_username": "test@example.com",
            "name": "Test User",
            "roles": ["user"],
        }

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.USER

        async def mock_azure_scheme(*args, **kwargs):
            return mock_claims

        async def mock_get_or_create(*args, **kwargs):
            return mock_user

        with (
            patch("app.core.auth.azure_scheme", side_effect=mock_azure_scheme),
            patch("app.core.auth._is_email_domain_allowed") as mock_domain_check,
            patch("app.core.auth.get_or_create_user", side_effect=mock_get_or_create),
        ):
            mock_domain_check.return_value = True

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_extracts_email_from_upn_claim(self):
        """Falls back to upn claim when preferred_username is missing."""
        from app.core.auth import get_user_from_bearer_token
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}
        mock_db = AsyncMock()

        mock_claims = {
            "oid": "test-azure-oid",
            "upn": "test@example.com",  # Using upn instead of preferred_username
            "name": "Test User",
        }

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.USER

        async def mock_azure_scheme(*args, **kwargs):
            return mock_claims

        captured_kwargs = {}

        async def mock_get_or_create(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_user

        with (
            patch("app.core.auth.azure_scheme", side_effect=mock_azure_scheme),
            patch("app.core.auth._is_email_domain_allowed") as mock_domain_check,
            patch("app.core.auth.get_or_create_user", side_effect=mock_get_or_create),
        ):
            mock_domain_check.return_value = True

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result == mock_user
            assert captured_kwargs["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_extracts_azure_id_from_sub_claim(self):
        """Falls back to sub claim when oid is missing."""
        from app.core.auth import get_user_from_bearer_token
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}
        mock_db = AsyncMock()

        mock_claims = {
            "sub": "test-subject-id",  # Using sub instead of oid
            "preferred_username": "test@example.com",
            "name": "Test User",
        }

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.USER

        async def mock_azure_scheme(*args, **kwargs):
            return mock_claims

        captured_kwargs = {}

        async def mock_get_or_create(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_user

        with (
            patch("app.core.auth.azure_scheme", side_effect=mock_azure_scheme),
            patch("app.core.auth._is_email_domain_allowed") as mock_domain_check,
            patch("app.core.auth.get_or_create_user", side_effect=mock_get_or_create),
        ):
            mock_domain_check.return_value = True

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result == mock_user
            assert captured_kwargs["azure_id"] == "test-subject-id"

    @pytest.mark.asyncio
    async def test_handles_unexpected_exception_gracefully(self):
        """Returns None and logs error for unexpected exceptions."""
        from app.core.auth import get_user_from_bearer_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}
        mock_db = AsyncMock()

        with patch("app.core.auth.azure_scheme") as mock_scheme:
            mock_scheme.side_effect = RuntimeError("Unexpected error")

            result = await get_user_from_bearer_token(mock_request, mock_db)

            assert result is None


class TestGetCurrentUserBearerFallback:
    """Tests for Bearer token fallback in get_current_user."""

    @pytest.mark.asyncio
    async def test_prefers_session_cookie_over_bearer_token(self):
        """Session cookie authentication takes precedence over Bearer token."""
        from app.core.auth import get_current_user
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.cookies = {"session": "valid-session-token"}
        mock_request.headers = {"Authorization": "Bearer valid-bearer-token"}

        session_user = MagicMock()
        session_user.id = uuid4()
        session_user.is_active = True
        session_user.role = UserRole.USER

        bearer_user = MagicMock()
        bearer_user.id = uuid4()
        bearer_user.is_active = True
        bearer_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = session_user
            mock_bearer.return_value = bearer_user

            # Create a mock db session
            mock_db = AsyncMock()

            result = await get_current_user(mock_request, mock_db)

            assert result == session_user
            mock_session.assert_called_once()
            # Bearer should not be called because session succeeded
            mock_bearer.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_bearer_when_no_session(self):
        """Falls back to Bearer token when no valid session cookie."""
        from app.core.auth import get_current_user
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer valid-bearer-token"}

        bearer_user = MagicMock()
        bearer_user.id = uuid4()
        bearer_user.is_active = True
        bearer_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None  # No valid session
            mock_bearer.return_value = bearer_user

            mock_db = AsyncMock()

            result = await get_current_user(mock_request, mock_db)

            assert result == bearer_user
            mock_session.assert_called_once()
            mock_bearer.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_401_when_no_session_and_no_bearer(self):
        """Raises 401 when both session and Bearer auth fail."""
        from app.core.auth import get_current_user

        mock_request = MagicMock()

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_bearer.return_value = None

            mock_db = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, mock_db)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Not authenticated"
            assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_raises_403_for_inactive_session_user(self):
        """Raises 403 when session user is inactive."""
        from app.core.auth import get_current_user

        mock_request = MagicMock()

        inactive_user = MagicMock()
        inactive_user.is_active = False

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = inactive_user

            mock_db = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, mock_db)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "User account is disabled"

    @pytest.mark.asyncio
    async def test_raises_403_for_inactive_bearer_user(self):
        """Raises 403 when Bearer-authenticated user is inactive."""
        from app.core.auth import get_current_user

        mock_request = MagicMock()

        inactive_user = MagicMock()
        inactive_user.is_active = False

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_bearer.return_value = inactive_user

            mock_db = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, mock_db)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "User account is disabled"


class TestBearerTokenIntegration:
    """Integration tests for Bearer token authentication flow."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_accepts_valid_bearer_token(self):
        """Protected endpoints accept valid Bearer tokens."""
        from unittest.mock import patch
        from uuid import uuid4

        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        from app.core.auth import get_current_user
        from app.models.user import UserRole

        # Create a minimal test app
        app = FastAPI()

        @app.get("/test-protected")
        async def protected_endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id), "email": user.email}

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_bearer.return_value = mock_user

            client = TestClient(app)
            response = client.get(
                "/test-protected",
                headers={"Authorization": "Bearer valid-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_protected_endpoint_rejects_invalid_bearer_token(self):
        """Protected endpoints reject invalid Bearer tokens with 401."""
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        from app.core.auth import get_current_user

        app = FastAPI()

        @app.get("/test-protected")
        async def protected_endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id)}

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_bearer.return_value = None  # Invalid token

            client = TestClient(app)
            response = client.get(
                "/test-protected",
                headers={"Authorization": "Bearer invalid-token"},
            )

            assert response.status_code == 401
            assert response.json()["detail"] == "Not authenticated"

    @pytest.mark.asyncio
    async def test_protected_endpoint_works_with_both_auth_methods(self):
        """Same endpoint works with both session cookie and Bearer token."""
        from uuid import uuid4

        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        from app.core.auth import get_current_user
        from app.models.user import UserRole

        app = FastAPI()

        @app.get("/test-protected")
        async def protected_endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id), "email": user.email}

        session_user = MagicMock()
        session_user.id = uuid4()
        session_user.email = "session@example.com"
        session_user.is_active = True
        session_user.role = UserRole.USER

        bearer_user = MagicMock()
        bearer_user.id = uuid4()
        bearer_user.email = "bearer@example.com"
        bearer_user.is_active = True
        bearer_user.role = UserRole.USER

        # Test with session cookie
        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = session_user
            mock_bearer.return_value = None

            client = TestClient(app)
            response = client.get("/test-protected")

            assert response.status_code == 200
            assert response.json()["email"] == "session@example.com"

        # Test with Bearer token
        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_bearer.return_value = bearer_user

            client = TestClient(app)
            response = client.get(
                "/test-protected",
                headers={"Authorization": "Bearer valid-token"},
            )

            assert response.status_code == 200
            assert response.json()["email"] == "bearer@example.com"
