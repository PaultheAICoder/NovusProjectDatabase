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
