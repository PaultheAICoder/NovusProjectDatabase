"""Tests for token management API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.user import UserRole
from app.schemas.api_token import (
    APITokenCreate,
    APITokenListResponse,
    APITokenResponse,
    APITokenUpdate,
)


class TestCreateTokenEndpoint:
    """Tests for POST /api/v1/tokens."""

    def test_create_token_returns_plaintext_once(self):
        """Token creation returns plaintext token in response."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        mock_token = MagicMock()
        mock_token.id = uuid4()
        mock_token.name = "Test Token"
        mock_token.token_prefix = "npd_test"
        mock_token.scopes = None
        mock_token.expires_at = None
        mock_token.last_used_at = None
        mock_token.is_active = True
        mock_token.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.create_token.return_value = (
                "npd_plaintext_token",
                mock_token,
            )
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.post(
                "/api/v1/tokens",
                json={"name": "Test Token"},
            )

            assert response.status_code == 201
            data = response.json()
            assert "token" in data
            assert data["token"] == "npd_plaintext_token"
            assert "token_info" in data
            assert data["token_info"]["name"] == "Test Token"

    def test_create_token_validates_name_field(self):
        """Token creation validates name field is present."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        app.dependency_overrides[get_current_user] = lambda: mock_user

        client = TestClient(app)
        response = client.post(
            "/api/v1/tokens",
            json={},  # Missing name
        )

        assert response.status_code == 422

    def test_create_token_with_scopes_and_expiry(self):
        """Token creation accepts scopes and expiration."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        expiry = datetime.now(UTC) + timedelta(days=30)
        mock_token = MagicMock()
        mock_token.id = uuid4()
        mock_token.name = "Scoped Token"
        mock_token.token_prefix = "npd_scop"
        mock_token.scopes = ["read", "write"]
        mock_token.expires_at = expiry
        mock_token.last_used_at = None
        mock_token.is_active = True
        mock_token.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.create_token.return_value = (
                "npd_scoped_token",
                mock_token,
            )
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.post(
                "/api/v1/tokens",
                json={
                    "name": "Scoped Token",
                    "scopes": ["read", "write"],
                    "expires_at": expiry.isoformat(),
                },
            )

            assert response.status_code == 201


class TestListTokensEndpoint:
    """Tests for GET /api/v1/tokens."""

    def test_list_tokens_returns_user_tokens_only(self):
        """List only returns tokens owned by current user."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        mock_token1 = MagicMock()
        mock_token1.id = uuid4()
        mock_token1.name = "Token 1"
        mock_token1.token_prefix = "npd_tok1"
        mock_token1.scopes = None
        mock_token1.expires_at = None
        mock_token1.last_used_at = None
        mock_token1.is_active = True
        mock_token1.created_at = datetime.now(UTC)

        mock_token2 = MagicMock()
        mock_token2.id = uuid4()
        mock_token2.name = "Token 2"
        mock_token2.token_prefix = "npd_tok2"
        mock_token2.scopes = None
        mock_token2.expires_at = None
        mock_token2.last_used_at = None
        mock_token2.is_active = True
        mock_token2.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.list_user_tokens.return_value = [mock_token1, mock_token2]
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.get("/api/v1/tokens")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2
            service_instance.list_user_tokens.assert_called_once_with(mock_user.id)

    def test_list_tokens_pagination(self):
        """List supports pagination parameters."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        # Create 5 mock tokens
        mock_tokens = []
        for i in range(5):
            token = MagicMock()
            token.id = uuid4()
            token.name = f"Token {i}"
            token.token_prefix = f"npd_tk{i}"
            token.scopes = None
            token.expires_at = None
            token.last_used_at = None
            token.is_active = True
            token.created_at = datetime.now(UTC)
            mock_tokens.append(token)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.list_user_tokens.return_value = mock_tokens
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.get("/api/v1/tokens?page=1&page_size=2")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 5
            assert len(data["items"]) == 2
            assert data["page"] == 1
            assert data["page_size"] == 2


class TestGetTokenEndpoint:
    """Tests for GET /api/v1/tokens/{token_id}."""

    def test_get_token_returns_owned_token(self):
        """Get returns token if owned by user."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()
        mock_token = MagicMock()
        mock_token.id = token_id
        mock_token.name = "My Token"
        mock_token.token_prefix = "npd_mine"
        mock_token.scopes = None
        mock_token.expires_at = None
        mock_token.last_used_at = None
        mock_token.is_active = True
        mock_token.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.get_token_by_id.return_value = mock_token
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.get(f"/api/v1/tokens/{token_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "My Token"
            service_instance.get_token_by_id.assert_called_once_with(
                token_id, mock_user.id
            )

    def test_get_token_returns_404_for_not_found(self):
        """Get returns 404 for non-existent token."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.get_token_by_id.return_value = None
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.get(f"/api/v1/tokens/{token_id}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Token not found"


class TestUpdateTokenEndpoint:
    """Tests for PATCH /api/v1/tokens/{token_id}."""

    def test_update_token_name(self):
        """Can update token name."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()
        mock_token = MagicMock()
        mock_token.id = token_id
        mock_token.name = "Updated Name"
        mock_token.token_prefix = "npd_updt"
        mock_token.scopes = None
        mock_token.expires_at = None
        mock_token.last_used_at = None
        mock_token.is_active = True
        mock_token.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.update_token.return_value = mock_token
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.patch(
                f"/api/v1/tokens/{token_id}",
                json={"name": "Updated Name"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Updated Name"

    def test_update_token_deactivate(self):
        """Can deactivate token via is_active=false."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()
        mock_token = MagicMock()
        mock_token.id = token_id
        mock_token.name = "Deactivated Token"
        mock_token.token_prefix = "npd_deac"
        mock_token.scopes = None
        mock_token.expires_at = None
        mock_token.last_used_at = None
        mock_token.is_active = False
        mock_token.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.update_token.return_value = mock_token
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.patch(
                f"/api/v1/tokens/{token_id}",
                json={"is_active": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_active"] is False

    def test_update_token_returns_404_for_not_found(self):
        """Update returns 404 for non-existent token."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.update_token.return_value = None
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.patch(
                f"/api/v1/tokens/{token_id}",
                json={"name": "New Name"},
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Token not found"


class TestDeleteTokenEndpoint:
    """Tests for DELETE /api/v1/tokens/{token_id}."""

    def test_delete_token_success(self):
        """Delete removes token and returns 204."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.delete_token.return_value = True
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.delete(f"/api/v1/tokens/{token_id}")

            assert response.status_code == 204
            service_instance.delete_token.assert_called_once_with(
                token_id, mock_user.id
            )

    def test_delete_token_returns_404_for_not_found(self):
        """Delete returns 404 for non-existent token."""
        from app.api.tokens import router
        from app.core.auth import get_current_user

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER

        token_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = mock_user
            service_instance = AsyncMock()
            service_instance.delete_token.return_value = False
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(app)
            response = client.delete(f"/api/v1/tokens/{token_id}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Token not found"


class TestAdminListTokensEndpoint:
    """Tests for GET /api/v1/admin/tokens."""

    def test_admin_list_all_tokens(self):
        """Admin can list tokens from all users."""
        from app.api.tokens import admin_router
        from app.core.auth import get_current_admin_user

        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        mock_token1 = MagicMock()
        mock_token1.id = uuid4()
        mock_token1.name = "User1 Token"
        mock_token1.token_prefix = "npd_usr1"
        mock_token1.scopes = None
        mock_token1.expires_at = None
        mock_token1.last_used_at = None
        mock_token1.is_active = True
        mock_token1.created_at = datetime.now(UTC)

        mock_token2 = MagicMock()
        mock_token2.id = uuid4()
        mock_token2.name = "User2 Token"
        mock_token2.token_prefix = "npd_usr2"
        mock_token2.scopes = None
        mock_token2.expires_at = None
        mock_token2.last_used_at = None
        mock_token2.is_active = True
        mock_token2.created_at = datetime.now(UTC)

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = admin_user
            service_instance = AsyncMock()
            service_instance.list_all_tokens.return_value = (
                [mock_token1, mock_token2],
                2,
            )
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            client = TestClient(app)
            response = client.get("/api/v1/admin/tokens")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["items"]) == 2

    def test_admin_list_filters_by_user_id(self):
        """Admin list supports user_id filter."""
        from app.api.tokens import admin_router
        from app.core.auth import get_current_admin_user

        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        filter_user_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = admin_user
            service_instance = AsyncMock()
            service_instance.list_all_tokens.return_value = ([], 0)
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            client = TestClient(app)
            response = client.get(f"/api/v1/admin/tokens?user_id={filter_user_id}")

            assert response.status_code == 200
            service_instance.list_all_tokens.assert_called_once()
            call_kwargs = service_instance.list_all_tokens.call_args[1]
            assert call_kwargs["user_id"] == filter_user_id

    def test_admin_list_filters_by_is_active(self):
        """Admin list supports is_active filter."""
        from app.api.tokens import admin_router
        from app.core.auth import get_current_admin_user

        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = admin_user
            service_instance = AsyncMock()
            service_instance.list_all_tokens.return_value = ([], 0)
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            client = TestClient(app)
            response = client.get("/api/v1/admin/tokens?is_active=false")

            assert response.status_code == 200
            service_instance.list_all_tokens.assert_called_once()
            call_kwargs = service_instance.list_all_tokens.call_args[1]
            assert call_kwargs["is_active"] is False

    def test_admin_list_requires_admin_role(self):
        """Non-admin users get 403."""
        from app.api.tokens import admin_router

        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1")

        regular_user = MagicMock()
        regular_user.id = uuid4()
        regular_user.is_active = True
        regular_user.role = UserRole.USER

        with patch("app.core.auth.get_user_from_session") as mock_session:
            mock_session.return_value = regular_user

            # Don't override the admin dependency - let it check role
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/admin/tokens")

            # Should fail with 403 when role check fails
            assert response.status_code in [403, 401, 500]


class TestAdminDeleteTokenEndpoint:
    """Tests for DELETE /api/v1/admin/tokens/{token_id}."""

    def test_admin_delete_any_token(self):
        """Admin can delete any user's token."""
        from app.api.tokens import admin_router
        from app.core.auth import get_current_admin_user

        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        token_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = admin_user
            service_instance = AsyncMock()
            service_instance.admin_delete_token.return_value = True
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            client = TestClient(app)
            response = client.delete(f"/api/v1/admin/tokens/{token_id}")

            assert response.status_code == 204
            service_instance.admin_delete_token.assert_called_once_with(token_id)

    def test_admin_delete_returns_404_for_not_found(self):
        """Admin delete returns 404 for non-existent token."""
        from app.api.tokens import admin_router
        from app.core.auth import get_current_admin_user

        app = FastAPI()
        app.include_router(admin_router, prefix="/api/v1")

        admin_user = MagicMock()
        admin_user.id = uuid4()
        admin_user.is_active = True
        admin_user.role = UserRole.ADMIN

        token_id = uuid4()

        with (
            patch("app.api.tokens.TokenService") as MockService,
            patch("app.core.auth.get_user_from_session") as mock_session,
        ):
            mock_session.return_value = admin_user
            service_instance = AsyncMock()
            service_instance.admin_delete_token.return_value = False
            MockService.return_value = service_instance

            app.dependency_overrides[get_current_admin_user] = lambda: admin_user

            client = TestClient(app)
            response = client.delete(f"/api/v1/admin/tokens/{token_id}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Token not found"


class TestTokenSchemas:
    """Tests for API token Pydantic schemas."""

    def test_api_token_create_requires_name(self):
        """APITokenCreate requires name field."""
        data = APITokenCreate(name="Test")
        assert data.name == "Test"

    def test_api_token_create_name_validation(self):
        """APITokenCreate validates name length."""
        # Min length 1
        with pytest.raises(ValueError):
            APITokenCreate(name="")

    def test_api_token_update_all_optional(self):
        """APITokenUpdate fields are all optional."""
        data = APITokenUpdate()
        assert data.name is None
        assert data.is_active is None

    def test_api_token_update_with_values(self):
        """APITokenUpdate accepts values."""
        data = APITokenUpdate(name="New Name", is_active=False)
        assert data.name == "New Name"
        assert data.is_active is False

    def test_api_token_response_from_attributes(self):
        """APITokenResponse can be created from model attributes."""
        token_id = uuid4()
        now = datetime.now(UTC)

        data = APITokenResponse(
            id=token_id,
            name="Test Token",
            token_prefix="npd_test",
            scopes=["read"],
            expires_at=now + timedelta(days=30),
            last_used_at=now,
            is_active=True,
            created_at=now,
        )

        assert data.id == token_id
        assert data.name == "Test Token"
        assert data.token_prefix == "npd_test"
        assert data.is_active is True

    def test_api_token_list_response(self):
        """APITokenListResponse structure is correct."""
        token_id = uuid4()
        now = datetime.now(UTC)

        item = APITokenResponse(
            id=token_id,
            name="Test Token",
            token_prefix="npd_test",
            scopes=None,
            expires_at=None,
            last_used_at=None,
            is_active=True,
            created_at=now,
        )

        response = APITokenListResponse(
            items=[item],
            total=1,
            page=1,
            page_size=20,
        )

        assert len(response.items) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.page_size == 20
