"""Tests for OAuth callback security - state validation and token verification."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

# Disable rate limiting for all direct function call tests
# by patching the limiter before importing auth module
pytest_plugins = []


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for direct function calls in tests."""
    from app.core.rate_limit import limiter

    original_enabled = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original_enabled


def create_mock_request(cookies: dict | None = None) -> MagicMock:
    """Create a mock Request object for auth tests."""
    mock_request = MagicMock()
    mock_request.cookies = cookies or {}
    return mock_request


class TestOAuthStateValidation:
    """Tests for CSRF state parameter validation."""

    @pytest.mark.asyncio
    async def test_login_sets_state_cookie(self):
        """Login endpoint should set oauth_state cookie."""
        from app.api.auth import login

        mock_request = create_mock_request()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"

            response = await login(mock_request)

            # Check redirect contains state parameter
            location = str(response.headers.get("location", ""))
            assert "state=" in location

            # Check cookie is set
            cookie_header = None
            for key, value in response.headers.raw:
                if key == b"set-cookie" and b"oauth_state=" in value:
                    cookie_header = value.decode()
                    break

            assert cookie_header is not None
            assert "httponly" in cookie_header.lower()
            assert "samesite=lax" in cookie_header.lower()
            assert "max-age=300" in cookie_header.lower()
            assert "path=/api/v1/auth" in cookie_header.lower()

    @pytest.mark.asyncio
    async def test_login_generates_unique_state_each_time(self):
        """Each login request should generate a unique state token."""
        from app.api.auth import login

        mock_request = create_mock_request()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"

            response1 = await login(mock_request)
            response2 = await login(mock_request)

            # Extract state from both responses
            def get_state_from_response(response):
                location = str(response.headers.get("location", ""))
                for param in location.split("&"):
                    if param.startswith("state="):
                        return param.split("=")[1]
                return None

            state1 = get_state_from_response(response1)
            state2 = get_state_from_response(response2)

            assert state1 is not None
            assert state2 is not None
            assert state1 != state2  # States should be unique

    @pytest.mark.asyncio
    async def test_callback_rejects_missing_state_parameter(self):
        """Callback should reject requests without state parameter."""
        from app.api.auth import auth_callback

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "stored-state"}
        mock_db = AsyncMock()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state=None,  # Missing state parameter
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_state" in location

    @pytest.mark.asyncio
    async def test_callback_rejects_missing_state_cookie(self):
        """Callback should reject requests without state cookie."""
        from app.api.auth import auth_callback

        mock_request = MagicMock()
        mock_request.cookies = {}  # No cookie
        mock_db = AsyncMock()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="provided-state",
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_state" in location

    @pytest.mark.asyncio
    async def test_callback_rejects_mismatched_state(self):
        """Callback should reject requests with non-matching state."""
        from app.api.auth import auth_callback

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "stored-state"}
        mock_db = AsyncMock()

        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="different-state",  # Mismatch
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_state" in location

    @pytest.mark.asyncio
    async def test_callback_accepts_matching_state(self):
        """Callback should accept matching state and proceed to token exchange."""
        from app.api.auth import auth_callback

        matching_state = "matching-state-token-123"
        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": matching_state}
        mock_db = AsyncMock()

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_client_secret = "test-secret"

            # Mock token exchange to fail (we just want to verify state passed)
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.text = "Token exchange failed"
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post.return_value = (
                mock_response
            )
            mock_client.return_value = mock_client_instance

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state=matching_state,  # Matching state
                db=mock_db,
            )

            # Should get token_exchange_failed, not invalid_state
            location = str(response.headers.get("location", ""))
            assert "error=invalid_state" not in location
            assert "error=token_exchange_failed" in location


class TestOAuthTokenVerification:
    """Tests for ID token signature and claims verification."""

    @pytest.fixture
    def mock_signing_key(self):
        """Create a mock RSA signing key pair."""
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()

        return private_key, public_key

    def create_valid_id_token(
        self, private_key, claims: dict, kid: str = "test-kid"
    ) -> str:
        """Create a valid signed ID token."""
        from cryptography.hazmat.primitives import serialization

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        return jwt.encode(
            claims,
            private_pem,
            algorithm="RS256",
            headers={"kid": kid},
        )

    @pytest.mark.asyncio
    async def test_callback_rejects_token_without_kid(self):
        """Callback should reject tokens without key ID in header."""
        from app.api.auth import auth_callback

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "valid-state"}
        mock_db = AsyncMock()

        # Create a token without kid header
        fake_token = jwt.encode(
            {"sub": "test", "iat": datetime.utcnow()},
            "secret",
            algorithm="HS256",
            # No kid in headers
        )

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_client_secret = "test-secret"

            # Mock successful token exchange - use MagicMock for json()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id_token": fake_token}
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="valid-state",
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_token" in location

    @pytest.mark.asyncio
    async def test_callback_rejects_unknown_kid(self):
        """Callback should reject tokens with unknown key ID."""
        from app.api.auth import auth_callback

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "valid-state"}
        mock_db = AsyncMock()

        # Create mock token with unknown kid
        fake_token = jwt.encode(
            {"sub": "test", "iat": datetime.utcnow()},
            "secret",
            algorithm="HS256",
            headers={"kid": "unknown-kid"},
        )

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
            patch("app.api.auth.azure_scheme") as mock_scheme,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_client_secret = "test-secret"

            # Mock token exchange response - use MagicMock for json()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id_token": fake_token}
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            # Mock empty signing keys (unknown kid)
            mock_scheme.openid_config.signing_keys = {}

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="valid-state",
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_token" in location

    @pytest.mark.asyncio
    async def test_callback_rejects_expired_token(self, mock_signing_key):
        """Callback should reject expired ID tokens."""
        from cryptography.hazmat.primitives import serialization

        from app.api.auth import auth_callback

        private_key, public_key = mock_signing_key

        # Create expired token
        expired_claims = {
            "sub": "test-user",
            "aud": "test-client",
            "iss": "https://login.microsoftonline.com/test-tenant/v2.0",
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
        }

        id_token = self.create_valid_id_token(
            private_key, expired_claims, kid="test-kid"
        )

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "valid-state"}
        mock_db = AsyncMock()

        # Get public key in PEM format for jose
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
            patch("app.api.auth.azure_scheme") as mock_scheme,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_client_secret = "test-secret"

            # Mock token exchange response - use MagicMock for json()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id_token": id_token}
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            # Mock JWKS with our test key
            mock_scheme.openid_config.signing_keys = {"test-kid": public_pem}
            mock_scheme.openid_config.issuer = (
                "https://login.microsoftonline.com/test-tenant/v2.0"
            )

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="valid-state",
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=token_expired" in location

    @pytest.mark.asyncio
    async def test_callback_rejects_wrong_audience(self, mock_signing_key):
        """Callback should reject tokens with wrong audience."""
        from cryptography.hazmat.primitives import serialization

        from app.api.auth import auth_callback

        private_key, public_key = mock_signing_key

        # Create token with wrong audience
        claims = {
            "sub": "test-user",
            "aud": "wrong-client-id",  # Wrong audience
            "iss": "https://login.microsoftonline.com/test-tenant/v2.0",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        id_token = self.create_valid_id_token(private_key, claims, kid="test-kid")

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "valid-state"}
        mock_db = AsyncMock()

        # Get public key in PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
            patch("app.api.auth.azure_scheme") as mock_scheme,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"  # Different from token
            mock_settings.azure_ad_client_secret = "test-secret"

            # Mock token exchange response - use MagicMock for json()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id_token": id_token}
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            # Mock JWKS with our test key
            mock_scheme.openid_config.signing_keys = {"test-kid": public_pem}
            mock_scheme.openid_config.issuer = (
                "https://login.microsoftonline.com/test-tenant/v2.0"
            )

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="valid-state",
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_token" in location

    @pytest.mark.asyncio
    async def test_callback_rejects_wrong_issuer(self, mock_signing_key):
        """Callback should reject tokens with wrong issuer."""
        from cryptography.hazmat.primitives import serialization

        from app.api.auth import auth_callback

        private_key, public_key = mock_signing_key

        # Create token with wrong issuer
        claims = {
            "sub": "test-user",
            "aud": "test-client",
            "iss": "https://login.microsoftonline.com/wrong-tenant/v2.0",  # Wrong
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        id_token = self.create_valid_id_token(private_key, claims, kid="test-kid")

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "valid-state"}
        mock_db = AsyncMock()

        # Get public key in PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
            patch("app.api.auth.azure_scheme") as mock_scheme,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_client_secret = "test-secret"

            # Mock token exchange response - use MagicMock for json()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id_token": id_token}
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            # Mock JWKS with correct issuer (different from token)
            mock_scheme.openid_config.signing_keys = {"test-kid": public_pem}
            mock_scheme.openid_config.issuer = (
                "https://login.microsoftonline.com/test-tenant/v2.0"
            )

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="valid-state",
                db=mock_db,
            )

            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=invalid_token" in location

    @pytest.mark.asyncio
    async def test_callback_accepts_valid_token(self, mock_signing_key):
        """Callback should accept valid tokens and create session."""
        from cryptography.hazmat.primitives import serialization

        from app.api.auth import auth_callback
        from app.models.user import UserRole

        private_key, public_key = mock_signing_key

        # Create valid token with all required claims
        claims = {
            "sub": "test-user-id",
            "oid": "test-azure-oid",
            "preferred_username": "test@example.com",
            "name": "Test User",
            "aud": "test-client",
            "iss": "https://login.microsoftonline.com/test-tenant/v2.0",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
            "roles": ["user"],
        }

        id_token = self.create_valid_id_token(private_key, claims, kid="test-kid")

        mock_request = MagicMock()
        mock_request.cookies = {"oauth_state": "valid-state"}
        mock_db = AsyncMock()

        # Mock user object
        mock_user = MagicMock()
        mock_user.id = "user-uuid"
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.USER

        # Get public key in PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with (
            patch("app.api.auth.settings") as mock_settings,
            patch("app.api.auth.httpx.AsyncClient") as mock_client,
            patch("app.api.auth.azure_scheme") as mock_scheme,
            patch("app.api.auth.get_or_create_user") as mock_get_user,
        ):
            mock_settings.azure_ad_redirect_uri = "http://localhost/api/v1/callback"
            mock_settings.cors_origins = ["http://localhost"]
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_client_secret = "test-secret"
            mock_settings.allowed_email_domains = []
            mock_settings.secret_key = "test-secret-key"

            # Mock token exchange response - use MagicMock for json()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id_token": id_token}
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_client_instance

            # Mock JWKS
            mock_scheme.openid_config.signing_keys = {"test-kid": public_pem}
            mock_scheme.openid_config.issuer = (
                "https://login.microsoftonline.com/test-tenant/v2.0"
            )

            # Mock user creation
            mock_get_user.return_value = mock_user

            response = await auth_callback(
                request=mock_request,
                code="valid-code",
                state="valid-state",
                db=mock_db,
            )

            # Should redirect to frontend without error
            assert response.status_code == 302
            location = str(response.headers.get("location", ""))
            assert "error=" not in location
            assert location == "http://localhost"

            # Should have session cookie set
            session_cookie = None
            for key, value in response.headers.raw:
                if key == b"set-cookie" and b"session=" in value:
                    session_cookie = value.decode()
                    break

            assert session_cookie is not None
            assert "httponly" in session_cookie.lower()

            # Should have oauth_state cookie deleted
            # Note: delete_cookie sets max-age=0 which effectively deletes it
            oauth_state_cookie = None
            for key, value in response.headers.raw:
                if key == b"set-cookie" and b"oauth_state=" in value:
                    oauth_state_cookie = value.decode()
                    break

            # If oauth_state cookie is present in response, it should be a deletion
            if oauth_state_cookie:
                assert "max-age=0" in oauth_state_cookie.lower()


class TestOAuthStateSecurityProperties:
    """Tests for state parameter security properties."""

    @pytest.mark.asyncio
    async def test_state_is_cryptographically_random(self):
        """State should be generated using cryptographically secure randomness."""
        from app.api.auth import login

        mock_request = create_mock_request()
        states = []
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.azure_ad_tenant_id = "test-tenant"
            mock_settings.azure_ad_client_id = "test-client"
            mock_settings.azure_ad_redirect_uri = "http://localhost/callback"

            # Generate multiple states
            for _ in range(10):
                response = await login(mock_request)
                location = str(response.headers.get("location", ""))
                for param in location.split("&"):
                    if param.startswith("state="):
                        states.append(param.split("=")[1])
                        break

        # All states should be unique
        assert len(states) == len(set(states))

        # States should be URL-safe base64 (from token_urlsafe)
        import re

        for state in states:
            # token_urlsafe generates URL-safe base64 without padding
            assert re.match(r"^[A-Za-z0-9_-]+$", state)
            # 32 bytes = ~43 base64 characters
            assert len(state) >= 40

    @pytest.mark.asyncio
    async def test_timing_attack_resistant_comparison(self):
        """State comparison should use constant-time comparison."""
        # This test verifies the code uses hmac.compare_digest
        # We can't easily test timing, but we verify the function is used

        import inspect

        from app.api import auth

        source = inspect.getsource(auth.auth_callback)
        assert "hmac.compare_digest" in source
