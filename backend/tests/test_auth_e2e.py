"""Tests for E2E test authentication endpoint."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for direct function calls in tests."""
    from app.core.rate_limit import limiter

    original_enabled = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original_enabled


def create_mock_request(
    headers: dict | None = None, client_ip: str = "127.0.0.1"
) -> MagicMock:
    """Create a mock Request object for auth tests."""
    mock_request = MagicMock()
    mock_request.cookies = {}
    mock_request.headers = MagicMock()
    mock_request.headers.get = lambda key, default="": (headers or {}).get(key, default)
    mock_request.client = MagicMock()
    mock_request.client.host = client_ip
    return mock_request


class TestE2EAuthEndpoint:
    """Tests for POST /api/v1/auth/test-token."""

    def test_endpoint_disabled_by_default(self) -> None:
        """Test token endpoint should return 404 when E2E_TEST_MODE is false."""
        from app.config import Settings

        settings = Settings()
        assert settings.e2e_test_mode is False

    @pytest.mark.asyncio
    async def test_endpoint_returns_404_when_disabled(self) -> None:
        """Endpoint should return 404, not 401/403, when disabled."""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.api.auth import create_test_token

        mock_db = AsyncMock()
        mock_request = create_mock_request()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.e2e_test_mode = False

            with pytest.raises(HTTPException) as exc_info:
                await create_test_token(request=mock_request, admin=False, db=mock_db)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Not found"

    @pytest.mark.asyncio
    async def test_endpoint_creates_session_when_enabled_in_dev(self) -> None:
        """Endpoint should create valid session cookie when enabled in development."""
        from unittest.mock import AsyncMock, MagicMock

        from app.api.auth import create_test_token
        from app.models.user import UserRole

        mock_db = AsyncMock()
        mock_request = create_mock_request()

        # Mock user object
        mock_user = MagicMock()
        mock_user.id = "test-user-id-123"
        mock_user.email = "e2e-test@example.com"
        mock_user.display_name = "E2E Test User"
        mock_user.role = UserRole.USER

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.get_or_create_user") as mock_get_user,
        ):
            mock_settings.environment = "development"
            mock_settings.e2e_test_mode = True
            mock_settings.e2e_test_secret = ""  # Not required in dev
            mock_get_user.return_value = mock_user

            response = await create_test_token(
                request=mock_request, admin=False, db=mock_db
            )

            # Verify response content
            assert response.status_code == 200

            # Verify get_or_create_user was called with test user data
            mock_get_user.assert_called_once()
            call_kwargs = mock_get_user.call_args.kwargs
            assert (
                call_kwargs["azure_id"]
                == "e2e-test-user-00000000-0000-0000-0000-000000000000"
            )
            assert call_kwargs["email"] == "e2e-test@example.com"
            assert call_kwargs["display_name"] == "E2E Test User"

            # Verify session cookie is set
            # The cookie is set in response headers
            cookie_header = None
            for key, value in response.headers.raw:
                if key == b"set-cookie":
                    cookie_header = value.decode()
                    break

            assert cookie_header is not None
            assert "session=" in cookie_header
            assert "httponly" in cookie_header.lower()


class TestE2EAuthEndpointSecurity:
    """Tests for E2E test token endpoint security hardening."""

    @pytest.mark.asyncio
    async def test_endpoint_blocked_in_production(self) -> None:
        """Endpoint should return 404 in production regardless of e2e_test_mode."""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.api.auth import create_test_token

        mock_db = AsyncMock()
        mock_request = create_mock_request()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.e2e_test_mode = True  # Even if accidentally enabled

            with pytest.raises(HTTPException) as exc_info:
                await create_test_token(request=mock_request, admin=False, db=mock_db)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Not found"

    @pytest.mark.asyncio
    async def test_endpoint_requires_secret_in_staging(self) -> None:
        """Endpoint should require valid secret in staging environment."""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.api.auth import create_test_token

        mock_db = AsyncMock()
        mock_request = create_mock_request(headers={})  # No secret provided

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.environment = "staging"
            mock_settings.e2e_test_mode = True
            mock_settings.e2e_test_secret = "valid-secret"

            with pytest.raises(HTTPException) as exc_info:
                await create_test_token(request=mock_request, admin=False, db=mock_db)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid test secret"

    @pytest.mark.asyncio
    async def test_endpoint_returns_500_when_secret_not_configured(self) -> None:
        """Endpoint should return 500 when secret is required but not configured."""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.api.auth import create_test_token

        mock_db = AsyncMock()
        mock_request = create_mock_request(headers={"X-E2E-Test-Secret": "some-secret"})

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.environment = "staging"
            mock_settings.e2e_test_mode = True
            mock_settings.e2e_test_secret = ""  # Not configured

            with pytest.raises(HTTPException) as exc_info:
                await create_test_token(request=mock_request, admin=False, db=mock_db)

            assert exc_info.value.status_code == 500
            assert exc_info.value.detail == "E2E test mode misconfigured"

    @pytest.mark.asyncio
    async def test_endpoint_accepts_valid_secret(self) -> None:
        """Endpoint should accept request with valid secret in non-dev environment."""
        from unittest.mock import AsyncMock, MagicMock

        from app.api.auth import create_test_token
        from app.models.user import UserRole

        mock_db = AsyncMock()
        mock_request = create_mock_request(
            headers={"X-E2E-Test-Secret": "valid-secret"}
        )

        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "e2e-test@example.com"
        mock_user.display_name = "E2E Test User"
        mock_user.role = UserRole.USER

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.get_or_create_user") as mock_get_user,
        ):
            mock_settings.environment = "staging"
            mock_settings.e2e_test_mode = True
            mock_settings.e2e_test_secret = "valid-secret"
            mock_get_user.return_value = mock_user

            response = await create_test_token(
                request=mock_request, admin=False, db=mock_db
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_endpoint_skips_secret_in_development(self) -> None:
        """Endpoint should not require secret in development environment."""
        from unittest.mock import AsyncMock, MagicMock

        from app.api.auth import create_test_token
        from app.models.user import UserRole

        mock_db = AsyncMock()
        mock_request = create_mock_request(headers={})  # No secret

        mock_user = MagicMock()
        mock_user.id = "test-user-id"
        mock_user.email = "e2e-test@example.com"
        mock_user.display_name = "E2E Test User"
        mock_user.role = UserRole.USER

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.get_or_create_user") as mock_get_user,
        ):
            mock_settings.environment = "development"
            mock_settings.e2e_test_mode = True
            mock_settings.e2e_test_secret = ""  # No secret required in dev
            mock_get_user.return_value = mock_user

            response = await create_test_token(
                request=mock_request, admin=False, db=mock_db
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_endpoint_rejects_invalid_secret(self) -> None:
        """Endpoint should reject request with invalid secret."""
        from unittest.mock import AsyncMock

        from fastapi import HTTPException

        from app.api.auth import create_test_token

        mock_db = AsyncMock()
        mock_request = create_mock_request(
            headers={"X-E2E-Test-Secret": "wrong-secret"}
        )

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.environment = "staging"
            mock_settings.e2e_test_mode = True
            mock_settings.e2e_test_secret = "correct-secret"

            with pytest.raises(HTTPException) as exc_info:
                await create_test_token(request=mock_request, admin=False, db=mock_db)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Invalid test secret"
