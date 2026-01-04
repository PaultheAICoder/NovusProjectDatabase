"""Tests for configuration security validation."""

import os
from unittest.mock import patch

import pytest

from app.config import Settings


class TestConfigSecurity:
    """Test security-critical configuration validation."""

    def test_production_requires_database_url(self):
        """Production environment must have DATABASE_URL."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="DATABASE_URL is required"),
        ):
            Settings(_env_file=None)

    def test_production_requires_azure_credentials(self):
        """Production environment must have Azure AD credentials."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "",
            "AZURE_AD_CLIENT_ID": "",
            "AZURE_AD_CLIENT_SECRET": "",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="AZURE_AD_TENANT_ID is required"),
        ):
            Settings(_env_file=None)

    def test_production_rejects_placeholder_azure_credentials(self):
        """Production environment rejects 'your-' placeholder values."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "your-tenant-id",
            "AZURE_AD_CLIENT_ID": "your-client-id",
            "AZURE_AD_CLIENT_SECRET": "your-secret",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="AZURE_AD_TENANT_ID is required"),
        ):
            Settings(_env_file=None)

    def test_secret_key_minimum_length(self):
        """Secret key must be at least 32 characters."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "too-short",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="at least 32 characters"),
        ):
            Settings(_env_file=None)

    def test_development_allows_empty_azure(self):
        """Development environment allows empty Azure credentials."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "",
            "AZURE_AD_CLIENT_ID": "",
            "AZURE_AD_CLIENT_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.environment == "development"

    def test_auto_generates_secret_key(self):
        """Empty SECRET_KEY generates secure random key."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert len(settings.secret_key) >= 32

    def test_debug_defaults_to_false(self):
        """Debug should default to False for safety."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.debug is False

    def test_development_provides_default_database_url(self):
        """Development environment provides default DATABASE_URL if empty."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "DATABASE_URL": "",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert "postgresql+asyncpg://" in settings.database_url
            assert "localhost:6702" in settings.database_url

    def test_cors_middleware_not_wildcard(self):
        """CORS middleware should not use wildcard methods/headers."""
        # This is a documentation test - actual CORS config is in main.py
        # Verify the app doesn't have wildcard CORS in production
        from app.main import app

        for middleware in app.user_middleware:
            if (
                hasattr(middleware, "cls")
                and middleware.cls.__name__ == "CORSMiddleware"
            ):
                # Check that wildcards are not used
                # Middleware stores options in kwargs, not options
                kwargs = middleware.kwargs
                assert kwargs.get("allow_methods") != [
                    "*"
                ], "CORS allow_methods should not be wildcard"
                assert kwargs.get("allow_headers") != [
                    "*"
                ], "CORS allow_headers should not be wildcard"
                break


class TestProductionUnsafeDefaultsValidation:
    """Tests for production-unsafe defaults validation (CORS localhost, memory rate limiting)."""

    def test_production_rejects_localhost_cors_origins(self):
        """Production environment rejects localhost in CORS origins."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
            "CORS_ORIGINS": '["http://localhost:6700"]',
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="CORS_ORIGINS contains localhost"),
        ):
            Settings(_env_file=None)

    def test_production_allows_non_localhost_cors_origins(self):
        """Production environment allows non-localhost CORS origins."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
            "CORS_ORIGINS": '["https://app.novuslabs.com"]',
            "RATE_LIMIT_STORAGE_URI": "redis://localhost:6379",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.cors_origins == ["https://app.novuslabs.com"]

    def test_production_rejects_memory_rate_limit_storage(self):
        """Production environment rejects in-memory rate limit storage."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
            "CORS_ORIGINS": '["https://app.novuslabs.com"]',
            "RATE_LIMIT_STORAGE_URI": "memory://",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="RATE_LIMIT_STORAGE_URI is 'memory://'"),
        ):
            Settings(_env_file=None)

    def test_production_allows_redis_rate_limit_storage(self):
        """Production environment allows Redis rate limit storage."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
            "CORS_ORIGINS": '["https://app.novuslabs.com"]',
            "RATE_LIMIT_STORAGE_URI": "redis://localhost:6379",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.rate_limit_storage_uri == "redis://localhost:6379"

    def test_production_allows_memory_when_rate_limit_disabled(self):
        """Production allows memory storage when rate limiting is disabled."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
            "CORS_ORIGINS": '["https://app.novuslabs.com"]',
            "RATE_LIMIT_ENABLED": "false",
            "RATE_LIMIT_STORAGE_URI": "memory://",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.rate_limit_enabled is False
            assert settings.rate_limit_storage_uri == "memory://"


class TestE2ETestModeConfigSecurity:
    """Tests for E2E test mode configuration security validation."""

    def test_production_rejects_e2e_test_mode(self):
        """Production environment must reject e2e_test_mode=true."""
        env = {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "AZURE_AD_TENANT_ID": "test-tenant",
            "AZURE_AD_CLIENT_ID": "test-client",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
            "CORS_ORIGINS": '["https://app.novuslabs.com"]',
            "RATE_LIMIT_STORAGE_URI": "redis://localhost:6379",
            "E2E_TEST_MODE": "true",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(
                ValueError, match="E2E_TEST_MODE cannot be enabled in production"
            ),
        ):
            Settings(_env_file=None)

    def test_staging_requires_e2e_test_secret(self):
        """Staging environment requires E2E_TEST_SECRET when E2E_TEST_MODE is true."""
        env = {
            "ENVIRONMENT": "staging",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "E2E_TEST_MODE": "true",
            "E2E_TEST_SECRET": "",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="E2E_TEST_SECRET is required"),
        ):
            Settings(_env_file=None)

    def test_staging_allows_e2e_mode_with_secret(self):
        """Staging environment allows E2E_TEST_MODE with a secret."""
        env = {
            "ENVIRONMENT": "staging",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
            "SECRET_KEY": "a" * 32,
            "E2E_TEST_MODE": "true",
            "E2E_TEST_SECRET": "valid-test-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.e2e_test_mode is True
            assert settings.e2e_test_secret == "valid-test-secret"

    def test_development_allows_e2e_mode_without_secret(self):
        """Development environment allows E2E_TEST_MODE without secret."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "E2E_TEST_MODE": "true",
            "E2E_TEST_SECRET": "",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.e2e_test_mode is True
            assert settings.e2e_test_secret == ""

    def test_e2e_test_mode_defaults_to_false(self):
        """E2E test mode should default to False."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.e2e_test_mode is False


class TestSharePointConfigSecurity:
    """Tests for SharePoint configuration validation."""

    def test_sharepoint_disabled_by_default(self):
        """SharePoint should be disabled by default."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.sharepoint_enabled is False

    def test_is_sharepoint_configured_requires_all_settings(self):
        """is_sharepoint_configured requires enabled + site + drive + credentials."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "SHAREPOINT_ENABLED": "true",
            "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/NPD",
            "SHAREPOINT_DRIVE_ID": "b!xxxxx",
            "AZURE_AD_CLIENT_ID": "test-client-id",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.is_sharepoint_configured is True

    def test_is_sharepoint_configured_false_when_disabled(self):
        """is_sharepoint_configured returns False when disabled."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "SHAREPOINT_ENABLED": "false",
            "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/NPD",
            "SHAREPOINT_DRIVE_ID": "b!xxxxx",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.is_sharepoint_configured is False

    def test_is_sharepoint_configured_false_without_site_url(self):
        """is_sharepoint_configured returns False without site URL."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "SHAREPOINT_ENABLED": "true",
            "SHAREPOINT_SITE_URL": "",
            "SHAREPOINT_DRIVE_ID": "b!xxxxx",
            "AZURE_AD_CLIENT_ID": "test-client-id",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.is_sharepoint_configured is False

    def test_sharepoint_uses_azure_creds_by_default(self):
        """SharePoint can use Azure AD credentials when SP-specific not set."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "SHAREPOINT_ENABLED": "true",
            "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/NPD",
            "SHAREPOINT_DRIVE_ID": "b!xxxxx",
            # Note: Using Azure AD creds, not SharePoint-specific
            "AZURE_AD_CLIENT_ID": "test-client-id",
            "AZURE_AD_CLIENT_SECRET": "test-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.is_sharepoint_configured is True

    def test_sharepoint_can_use_own_credentials(self):
        """SharePoint can use its own credentials separate from Azure AD."""
        env = {
            "ENVIRONMENT": "development",
            "SECRET_KEY": "a" * 32,
            "SHAREPOINT_ENABLED": "true",
            "SHAREPOINT_SITE_URL": "https://contoso.sharepoint.com/sites/NPD",
            "SHAREPOINT_DRIVE_ID": "b!xxxxx",
            "SHAREPOINT_CLIENT_ID": "sp-client-id",
            "SHAREPOINT_CLIENT_SECRET": "sp-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
            assert settings.is_sharepoint_configured is True
