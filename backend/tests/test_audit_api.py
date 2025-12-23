"""Tests for Audit Log Query API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.audit import router as audit_router
from app.api.contacts import router as contacts_router
from app.api.projects import router as projects_router
from app.core.auth import get_current_active_user
from app.database import get_db
from app.models.audit import AuditAction
from app.models.user import UserRole
from app.schemas.audit import AuditLogWithUser, UserSummary


class TestAuditSchemas:
    """Tests for new Audit schemas (UserSummary, AuditLogWithUser)."""

    def test_user_summary_schema(self):
        """UserSummary should validate with id and display_name."""
        user_id = uuid4()
        summary = UserSummary(id=user_id, display_name="John Doe")

        assert summary.id == user_id
        assert summary.display_name == "John Doe"

    def test_audit_log_with_user_all_fields(self):
        """AuditLogWithUser should accept all fields."""
        log_id = uuid4()
        entity_id = uuid4()
        user_id = uuid4()
        now = datetime.now(UTC)

        user_summary = UserSummary(id=user_id, display_name="Jane Doe")

        audit_log = AuditLogWithUser(
            id=log_id,
            entity_type="project",
            entity_id=entity_id,
            action=AuditAction.UPDATE,
            user=user_summary,
            changed_fields={"name": {"old": "Old", "new": "New"}},
            created_at=now,
        )

        assert audit_log.id == log_id
        assert audit_log.entity_type == "project"
        assert audit_log.action == AuditAction.UPDATE
        assert audit_log.user is not None
        assert audit_log.user.display_name == "Jane Doe"
        assert audit_log.changed_fields is not None

    def test_audit_log_with_user_nullable_user(self):
        """AuditLogWithUser should allow user to be None."""
        audit_log = AuditLogWithUser(
            id=uuid4(),
            entity_type="project",
            entity_id=uuid4(),
            action=AuditAction.CREATE,
            user=None,
            changed_fields=None,
            created_at=datetime.now(UTC),
        )

        assert audit_log.user is None


class TestListAuditLogs:
    """Tests for GET /audit endpoint."""

    def _create_app(self):
        """Create test FastAPI app with audit router."""
        app = FastAPI()
        app.include_router(audit_router, prefix="/api/v1")
        return app

    def _create_mock_user(self):
        """Create mock user for auth."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER
        mock_user.display_name = "Test User"
        return mock_user

    def test_list_audit_logs_empty(self):
        """GET /audit returns empty list when no logs exist."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.audit.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get("/api/v1/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_audit_logs_with_entity_type_filter(self):
        """GET /audit?entity_type=project filters by entity type."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=1)

        # Mock audit log
        mock_log = MagicMock()
        mock_log.id = uuid4()
        mock_log.entity_type = "project"
        mock_log.entity_id = uuid4()
        mock_log.action = AuditAction.CREATE
        mock_log.user = None
        mock_log.changed_fields = {"name": {"old": None, "new": "Test"}}
        mock_log.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.audit.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get("/api/v1/audit?entity_type=project")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["entity_type"] == "project"

    def test_list_audit_logs_with_action_filter(self):
        """GET /audit?action=create filters by action."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=1)

        mock_log = MagicMock()
        mock_log.id = uuid4()
        mock_log.entity_type = "contact"
        mock_log.entity_id = uuid4()
        mock_log.action = AuditAction.CREATE
        mock_log.user = None
        mock_log.changed_fields = None
        mock_log.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.audit.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get("/api/v1/audit?action=create")

        assert response.status_code == 200
        data = response.json()
        assert all(item["action"] == "create" for item in data["items"])

    def test_list_audit_logs_includes_user_display_name(self):
        """GET /audit response includes user display_name."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=1)

        # Mock user relationship on audit log
        mock_log_user = MagicMock()
        mock_log_user.id = uuid4()
        mock_log_user.display_name = "John Modifier"

        mock_log = MagicMock()
        mock_log.id = uuid4()
        mock_log.entity_type = "project"
        mock_log.entity_id = uuid4()
        mock_log.action = AuditAction.UPDATE
        mock_log.user = mock_log_user
        mock_log.changed_fields = {"name": {"old": "Old", "new": "New"}}
        mock_log.created_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.audit.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get("/api/v1/audit")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["user"] is not None
        assert data["items"][0]["user"]["display_name"] == "John Modifier"

    def test_list_audit_logs_pagination(self):
        """GET /audit respects pagination parameters."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=50)  # Total count

        # Return 10 items for page_size=10
        mock_logs = []
        for _ in range(10):
            log = MagicMock()
            log.id = uuid4()
            log.entity_type = "project"
            log.entity_id = uuid4()
            log.action = AuditAction.UPDATE
            log.user = None
            log.changed_fields = None
            log.created_at = datetime.now(UTC)
            mock_logs.append(log)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.audit.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get("/api/v1/audit?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 50
        assert data["pages"] == 5


class TestProjectAuditHistory:
    """Tests for GET /projects/{id}/audit endpoint."""

    def _create_app(self):
        """Create test FastAPI app with projects router."""
        app = FastAPI()
        app.include_router(projects_router, prefix="/api/v1")
        return app

    def _create_mock_user(self):
        """Create mock user for auth."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER
        mock_user.display_name = "Test User"
        return mock_user

    def test_project_audit_history_not_found(self):
        """GET /projects/{id}/audit returns 404 for non-existent project."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)  # Project not found

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.projects.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            project_id = uuid4()
            response = client.get(f"/api/v1/projects/{project_id}/audit")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_project_audit_history_success(self):
        """GET /projects/{id}/audit returns audit history for valid project."""
        app = self._create_app()
        mock_user = self._create_mock_user()
        project_id = uuid4()

        # Mock project
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.name = "Test Project"

        # Mock audit logs
        mock_log = MagicMock()
        mock_log.id = uuid4()
        mock_log.entity_type = "project"
        mock_log.entity_id = project_id
        mock_log.action = AuditAction.CREATE
        mock_log.user = None
        mock_log.changed_fields = {"name": {"old": None, "new": "Test Project"}}
        mock_log.created_at = datetime.now(UTC)

        mock_db = AsyncMock()
        # First call: project lookup, Second call: count, Third call: audit logs
        mock_db.scalar = AsyncMock(side_effect=[mock_project, 1])

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.projects.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get(f"/api/v1/projects/{project_id}/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["entity_type"] == "project"
        assert data["items"][0]["entity_id"] == str(project_id)


class TestContactAuditHistory:
    """Tests for GET /contacts/{id}/audit endpoint."""

    def _create_app(self):
        """Create test FastAPI app with contacts router."""
        app = FastAPI()
        app.include_router(contacts_router, prefix="/api/v1")
        return app

    def _create_mock_user(self):
        """Create mock user for auth."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.role = UserRole.USER
        mock_user.display_name = "Test User"
        return mock_user

    def test_contact_audit_history_not_found(self):
        """GET /contacts/{id}/audit returns 404 for non-existent contact."""
        app = self._create_app()
        mock_user = self._create_mock_user()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)  # Contact not found

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.contacts.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            contact_id = uuid4()
            response = client.get(f"/api/v1/contacts/{contact_id}/audit")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_contact_audit_history_success(self):
        """GET /contacts/{id}/audit returns audit history for valid contact."""
        app = self._create_app()
        mock_user = self._create_mock_user()
        contact_id = uuid4()

        # Mock contact
        mock_contact = MagicMock()
        mock_contact.id = contact_id
        mock_contact.name = "John Doe"

        # Mock audit log with user
        mock_log_user = MagicMock()
        mock_log_user.id = uuid4()
        mock_log_user.display_name = "Admin User"

        mock_log = MagicMock()
        mock_log.id = uuid4()
        mock_log.entity_type = "contact"
        mock_log.entity_id = contact_id
        mock_log.action = AuditAction.UPDATE
        mock_log.user = mock_log_user
        mock_log.changed_fields = {"email": {"old": "old@ex.com", "new": "new@ex.com"}}
        mock_log.created_at = datetime.now(UTC)

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(side_effect=[mock_contact, 1])

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def mock_get_db():
            yield mock_db

        async def mock_get_user():
            return mock_user

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_active_user] = mock_get_user

        with patch("app.api.contacts.limiter.limit", lambda _: lambda f: f):
            client = TestClient(app)
            response = client.get(f"/api/v1/contacts/{contact_id}/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["entity_type"] == "contact"
        assert data["items"][0]["user"] is not None
        assert data["items"][0]["user"]["display_name"] == "Admin User"


class TestAuditRouterImports:
    """Tests to verify audit router is properly set up."""

    def test_audit_router_exists(self):
        """Audit router module should be importable."""
        from app.api.audit import router

        assert router is not None
        assert router.prefix == "/audit"

    def test_audit_router_registered_in_main(self):
        """Audit router should be registered in main app."""
        from app.main import app

        route_paths = [route.path for route in app.routes]
        assert any("/api/v1/audit" in path for path in route_paths)

    def test_projects_router_has_audit_endpoint(self):
        """Projects router should have audit sub-route."""
        from app.api.projects import router

        route_paths = [route.path for route in router.routes]
        assert any("/audit" in path for path in route_paths)

    def test_contacts_router_has_audit_endpoint(self):
        """Contacts router should have audit sub-route."""
        from app.api.contacts import router

        route_paths = [route.path for route in router.routes]
        assert any("/audit" in path for path in route_paths)
