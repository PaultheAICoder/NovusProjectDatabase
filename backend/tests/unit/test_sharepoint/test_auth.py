"""Tests for SharePoint authentication service."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.sharepoint.auth import (
    GRAPH_DEFAULT_SCOPE,
    GRAPH_FILES_SCOPE,
    SharePointAuthService,
    get_sharepoint_auth,
    reset_sharepoint_auth,
)
from app.core.sharepoint.exceptions import SharePointAuthenticationError


class TestSharePointAuthServiceInit:
    """Tests for SharePointAuthService initialization."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        reset_sharepoint_auth()
        yield
        reset_sharepoint_auth()

    def test_init_creates_msal_app_when_configured(self):
        """Initialization creates MSAL ConfidentialClientApplication when configured."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = True
        mock_settings.sharepoint_client_id = "test-client-id-12345678"
        mock_settings.sharepoint_client_secret = "test-client-secret"
        mock_settings.sharepoint_tenant_id = "test-tenant-id-12345678"
        mock_settings.azure_ad_client_id = ""
        mock_settings.azure_ad_client_secret = ""
        mock_settings.azure_ad_tenant_id = ""

        with (
            patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings),
            patch("msal.ConfidentialClientApplication") as mock_msal_class,
        ):
            service = SharePointAuthService()

            mock_msal_class.assert_called_once_with(
                client_id="test-client-id-12345678",
                client_credential="test-client-secret",
                authority="https://login.microsoftonline.com/test-tenant-id-12345678",
            )
            assert service._msal_app is not None

    def test_init_with_missing_config_does_not_create_msal_app(self):
        """Missing config prevents MSAL app creation."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()
            assert service._msal_app is None

    def test_init_uses_azure_ad_fallback_credentials(self):
        """Falls back to Azure AD credentials when SharePoint-specific not set."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = True
        mock_settings.sharepoint_client_id = ""
        mock_settings.sharepoint_client_secret = ""
        mock_settings.sharepoint_tenant_id = ""
        mock_settings.azure_ad_client_id = "azure-client-id-1234"
        mock_settings.azure_ad_client_secret = "azure-secret"
        mock_settings.azure_ad_tenant_id = "azure-tenant-id-1234"

        with (
            patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings),
            patch("msal.ConfidentialClientApplication") as mock_msal_class,
        ):
            SharePointAuthService()

            mock_msal_class.assert_called_once_with(
                client_id="azure-client-id-1234",
                client_credential="azure-secret",
                authority="https://login.microsoftonline.com/azure-tenant-id-1234",
            )

    def test_is_configured_returns_true_when_valid(self):
        """is_configured returns True when all settings present."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = True
        mock_settings.sharepoint_client_id = "test-client-id"
        mock_settings.sharepoint_client_secret = "test-secret"
        mock_settings.sharepoint_tenant_id = "test-tenant"

        with (
            patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings),
            patch("msal.ConfidentialClientApplication"),
        ):
            service = SharePointAuthService()
            assert service.is_configured is True

    def test_is_configured_returns_false_when_missing(self):
        """is_configured returns False when settings missing."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()
            assert service.is_configured is False


class TestGetAppToken:
    """Tests for app-only (client credentials) token acquisition."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        reset_sharepoint_auth()
        yield
        reset_sharepoint_auth()

    @pytest.fixture
    def mock_configured_service(self):
        """Create a mock configured SharePointAuthService."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = True
        mock_settings.sharepoint_client_id = "test-client-id"
        mock_settings.sharepoint_client_secret = "test-secret"
        mock_settings.sharepoint_tenant_id = "test-tenant"
        mock_settings.azure_ad_client_id = ""
        mock_settings.azure_ad_client_secret = ""
        mock_settings.azure_ad_tenant_id = ""

        with (
            patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings),
            patch("msal.ConfidentialClientApplication") as mock_msal_class,
        ):
            mock_app = MagicMock()
            mock_msal_class.return_value = mock_app
            service = SharePointAuthService()
            yield service, mock_app

    @pytest.mark.asyncio
    async def test_get_app_token_returns_token(self, mock_configured_service):
        """Successful token acquisition returns access token."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "mock_token_12345",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        token = await service.get_app_token()

        assert token == "mock_token_12345"
        mock_app.acquire_token_for_client.assert_called_once_with(
            scopes=GRAPH_DEFAULT_SCOPE
        )

    @pytest.mark.asyncio
    async def test_get_app_token_uses_cached_token(self, mock_configured_service):
        """Token from cache is used when available."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_silent.return_value = {
            "access_token": "cached_token_12345",
            "expires_in": 1800,
            "token_type": "Bearer",
        }

        token = await service.get_app_token()

        assert token == "cached_token_12345"
        mock_app.acquire_token_silent.assert_called_once_with(
            scopes=GRAPH_DEFAULT_SCOPE,
            account=None,
        )
        mock_app.acquire_token_for_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_app_token_acquires_new_when_cache_miss(
        self, mock_configured_service
    ):
        """Acquires new token when cache returns None."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "new_token_12345",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        token = await service.get_app_token()

        assert token == "new_token_12345"
        mock_app.acquire_token_silent.assert_called_once()
        mock_app.acquire_token_for_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_app_token_raises_on_error(self, mock_configured_service):
        """MSAL error raises SharePointAuthenticationError."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials",
        }

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_app_token()

        assert "invalid_client" in str(exc_info.value)
        assert "Invalid client credentials" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_app_token_raises_on_null_result(self, mock_configured_service):
        """Null result from MSAL raises SharePointAuthenticationError."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = None

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_app_token()

        assert "no result from MSAL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_app_token_raises_when_not_configured(self):
        """Raises error when SharePoint is not configured."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_app_token()

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_app_token_raises_on_missing_access_token(
        self, mock_configured_service
    ):
        """Raises error when response missing access_token."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_silent.return_value = None
        mock_app.acquire_token_for_client.return_value = {
            "expires_in": 3600,
            "token_type": "Bearer",
            # Missing access_token
        }

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_app_token()

        assert "access_token not in response" in str(exc_info.value)


class TestGetDelegatedToken:
    """Tests for delegated (OBO) token acquisition."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        reset_sharepoint_auth()
        yield
        reset_sharepoint_auth()

    @pytest.fixture
    def mock_configured_service(self):
        """Create a mock configured SharePointAuthService."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = True
        mock_settings.sharepoint_client_id = "test-client-id"
        mock_settings.sharepoint_client_secret = "test-secret"
        mock_settings.sharepoint_tenant_id = "test-tenant"
        mock_settings.azure_ad_client_id = ""
        mock_settings.azure_ad_client_secret = ""
        mock_settings.azure_ad_tenant_id = ""

        with (
            patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings),
            patch("msal.ConfidentialClientApplication") as mock_msal_class,
        ):
            mock_app = MagicMock()
            mock_msal_class.return_value = mock_app
            service = SharePointAuthService()
            yield service, mock_app

    @pytest.mark.asyncio
    async def test_get_delegated_token_returns_token(self, mock_configured_service):
        """Successful OBO flow returns access token."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_on_behalf_of.return_value = {
            "access_token": "delegated_token_12345",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        token = await service.get_delegated_token("user_assertion_token")

        assert token == "delegated_token_12345"
        mock_app.acquire_token_on_behalf_of.assert_called_once_with(
            user_assertion="user_assertion_token",
            scopes=GRAPH_FILES_SCOPE,
        )

    @pytest.mark.asyncio
    async def test_get_delegated_token_raises_on_invalid_assertion(
        self, mock_configured_service
    ):
        """Invalid user assertion raises error."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_on_behalf_of.return_value = {
            "error": "invalid_grant",
            "error_description": "AADSTS50013: Assertion is not valid",
        }

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_delegated_token("invalid_assertion")

        assert "invalid_grant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_delegated_token_raises_on_empty_assertion(
        self, mock_configured_service
    ):
        """Empty user assertion raises error."""
        service, _ = mock_configured_service

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_delegated_token("")

        assert "User assertion token is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_delegated_token_raises_when_not_configured(self):
        """Raises error when SharePoint is not configured."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_delegated_token("user_assertion")

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_delegated_token_handles_scope_error(
        self, mock_configured_service
    ):
        """Scope/permission errors are handled."""
        service, mock_app = mock_configured_service
        mock_app.acquire_token_on_behalf_of.return_value = {
            "error": "invalid_scope",
            "error_description": "AADSTS70011: The provided scope is invalid",
        }

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            await service.get_delegated_token("user_assertion")

        assert "invalid_scope" in str(exc_info.value)


class TestHandleAuthResult:
    """Tests for MSAL result processing."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        reset_sharepoint_auth()
        yield
        reset_sharepoint_auth()

    def test_handle_auth_result_extracts_token(self):
        """Valid result extracts access_token."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()

        result = {
            "access_token": "test_token_abc123",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        token = service._handle_auth_result(result, "app_only")
        assert token == "test_token_abc123"

    def test_handle_auth_result_raises_on_error_response(self):
        """Error in result raises SharePointAuthenticationError."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()

        result = {
            "error": "unauthorized_client",
            "error_description": "Client not authorized",
        }

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            service._handle_auth_result(result, "app_only")

        assert "unauthorized_client" in str(exc_info.value)

    def test_handle_auth_result_raises_on_none(self):
        """None result raises SharePointAuthenticationError."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            service._handle_auth_result(None, "delegated")

        assert "no result from MSAL" in str(exc_info.value)

    def test_handle_auth_result_raises_on_missing_token(self):
        """Result without access_token raises SharePointAuthenticationError."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service = SharePointAuthService()

        result = {
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        with pytest.raises(SharePointAuthenticationError) as exc_info:
            service._handle_auth_result(result, "app_only")

        assert "access_token not in response" in str(exc_info.value)


class TestGetSharePointAuth:
    """Tests for module-level singleton."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        reset_sharepoint_auth()
        yield
        reset_sharepoint_auth()

    def test_get_sharepoint_auth_returns_same_instance(self):
        """Singleton pattern returns same instance."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service1 = get_sharepoint_auth()
            service2 = get_sharepoint_auth()

            assert service1 is service2

    def test_reset_sharepoint_auth_clears_singleton(self):
        """reset_sharepoint_auth clears the singleton."""
        mock_settings = MagicMock()
        mock_settings.is_sharepoint_configured = False

        with patch("app.core.sharepoint.auth.get_settings", return_value=mock_settings):
            service1 = get_sharepoint_auth()
            reset_sharepoint_auth()
            service2 = get_sharepoint_auth()

            assert service1 is not service2


class TestGraphScopes:
    """Tests for Graph API scope constants."""

    def test_graph_default_scope_format(self):
        """GRAPH_DEFAULT_SCOPE is properly formatted."""
        assert ["https://graph.microsoft.com/.default"] == GRAPH_DEFAULT_SCOPE

    def test_graph_files_scope_format(self):
        """GRAPH_FILES_SCOPE is properly formatted."""
        assert ["https://graph.microsoft.com/Files.ReadWrite.All"] == GRAPH_FILES_SCOPE
