"""Tests for API token authentication support.

Tests the get_user_from_api_token function and the API token fallback
in get_current_user.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


class TestGetUserFromApiToken:
    """Tests for the get_user_from_api_token helper function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_authorization_header(self):
        """Returns None when no Authorization header is present."""
        from app.core.auth import get_user_from_api_token

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_db = AsyncMock()

        result = await get_user_from_api_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_header_format(self):
        """Returns None when Authorization header is malformed."""
        from app.core.auth import get_user_from_api_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "InvalidFormat"}
        mock_db = AsyncMock()

        result = await get_user_from_api_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_non_npd_token(self):
        """Returns None when Bearer token doesn't start with npd_ prefix."""
        from app.core.auth import get_user_from_api_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer some-azure-jwt-token"}
        mock_db = AsyncMock()

        result = await get_user_from_api_token(mock_request, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_api_token(self):
        """Returns None when npd_ token is invalid."""
        from app.core.auth import get_user_from_api_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer npd_invalid_token_12345"}
        mock_db = AsyncMock()

        with patch("app.core.auth.TokenService") as MockTokenService:
            mock_service_instance = AsyncMock()
            mock_service_instance.validate_token.return_value = None
            MockTokenService.return_value = mock_service_instance

            result = await get_user_from_api_token(mock_request, mock_db)

            assert result is None
            mock_service_instance.validate_token.assert_called_once_with(
                "npd_invalid_token_12345"
            )

    @pytest.mark.asyncio
    async def test_returns_user_for_valid_api_token(self):
        """Returns User object for valid npd_ token."""
        from app.core.auth import get_user_from_api_token
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer npd_valid_token_xyz123"}
        mock_db = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.USER

        with patch("app.core.auth.TokenService") as MockTokenService:
            mock_service_instance = AsyncMock()
            mock_service_instance.validate_token.return_value = mock_user
            MockTokenService.return_value = mock_service_instance

            result = await get_user_from_api_token(mock_request, mock_db)

            assert result == mock_user

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        """Returns None when TokenService raises unexpected exception."""
        from app.core.auth import get_user_from_api_token

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer npd_test_token"}
        mock_db = AsyncMock()

        with patch("app.core.auth.TokenService") as MockTokenService:
            MockTokenService.side_effect = RuntimeError("Unexpected error")

            result = await get_user_from_api_token(mock_request, mock_db)

            assert result is None


class TestGetCurrentUserApiTokenFallback:
    """Tests for API token fallback in get_current_user."""

    @pytest.mark.asyncio
    async def test_prefers_session_over_api_token(self):
        """Session cookie takes precedence over API token."""
        from app.core.auth import get_current_user
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.cookies = {"session": "valid-session"}
        mock_request.headers = {"Authorization": "Bearer npd_valid_token"}

        session_user = MagicMock()
        session_user.id = uuid4()
        session_user.is_active = True
        session_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_api_token") as mock_api_token,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = session_user
            mock_db = AsyncMock()

            result = await get_current_user(mock_request, mock_db)

            assert result == session_user
            mock_session.assert_called_once()
            mock_api_token.assert_not_called()
            mock_bearer.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_token_before_azure_bearer(self):
        """API token is tried before Azure AD Bearer token."""
        from app.core.auth import get_current_user
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer npd_valid_token"}

        api_user = MagicMock()
        api_user.id = uuid4()
        api_user.is_active = True
        api_user.role = UserRole.USER

        azure_user = MagicMock()
        azure_user.id = uuid4()
        azure_user.is_active = True
        azure_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_api_token") as mock_api_token,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_api_token.return_value = api_user
            mock_bearer.return_value = azure_user
            mock_db = AsyncMock()

            result = await get_current_user(mock_request, mock_db)

            assert result == api_user
            mock_api_token.assert_called_once()
            mock_bearer.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_azure_when_not_npd_token(self):
        """Falls back to Azure AD when token is not npd_ prefixed."""
        from app.core.auth import get_current_user
        from app.models.user import UserRole

        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer azure-jwt-token"}

        azure_user = MagicMock()
        azure_user.id = uuid4()
        azure_user.is_active = True
        azure_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_api_token") as mock_api_token,
            patch("app.core.auth.get_user_from_bearer_token") as mock_bearer,
        ):
            mock_session.return_value = None
            mock_api_token.return_value = None  # Not an npd_ token
            mock_bearer.return_value = azure_user
            mock_db = AsyncMock()

            result = await get_current_user(mock_request, mock_db)

            assert result == azure_user

    @pytest.mark.asyncio
    async def test_raises_403_for_inactive_api_token_user(self):
        """Raises 403 when API token user is inactive."""
        from app.core.auth import get_current_user

        mock_request = MagicMock()

        inactive_user = MagicMock()
        inactive_user.is_active = False

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_api_token") as mock_api_token,
        ):
            mock_session.return_value = None
            mock_api_token.return_value = inactive_user
            mock_db = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, mock_db)

            assert exc_info.value.status_code == 403
            assert exc_info.value.detail == "User account is disabled"


class TestApiTokenIntegration:
    """Integration tests for API token authentication flow."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_accepts_valid_api_token(self):
        """Protected endpoints accept valid API tokens."""
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        from app.core.auth import get_current_user
        from app.models.user import UserRole

        app = FastAPI()

        @app.get("/test-protected")
        async def protected_endpoint(user=Depends(get_current_user)):
            return {"user_id": str(user.id), "email": user.email}

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.email = "api-user@example.com"
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        with (
            patch("app.core.auth.get_user_from_session") as mock_session,
            patch("app.core.auth.get_user_from_api_token") as mock_api_token,
        ):
            mock_session.return_value = None
            mock_api_token.return_value = mock_user

            client = TestClient(app)
            response = client.get(
                "/test-protected",
                headers={"Authorization": "Bearer npd_test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "api-user@example.com"
