"""Tests for admin job API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_current_admin_user
from app.database import get_db
from app.models.job import Job, JobStatus, JobType
from app.models.user import UserRole


def create_mock_job(
    job_id=None,
    job_type=JobType.JIRA_REFRESH,
    status=JobStatus.PENDING,
    attempts=0,
):
    """Create a mock Job object for testing."""
    mock_job = MagicMock(spec=Job)
    mock_job.id = job_id or uuid4()
    mock_job.job_type = job_type
    mock_job.status = status
    mock_job.entity_type = None
    mock_job.entity_id = None
    mock_job.payload = None
    mock_job.result = None
    mock_job.priority = 0
    mock_job.attempts = attempts
    mock_job.max_attempts = 5
    mock_job.error_message = None
    mock_job.error_context = None
    mock_job.created_at = datetime.now(UTC)
    mock_job.started_at = None
    mock_job.completed_at = None
    mock_job.next_retry = datetime.now(UTC)
    mock_job.created_by = None
    return mock_job


def create_test_app_with_admin():
    """Create a test FastAPI app with admin router and mocked dependencies."""
    from app.api.admin import router as admin_router

    app = FastAPI()
    # Note: admin_router already has prefix="/admin", so we add only "/api/v1"
    app.include_router(admin_router, prefix="/api/v1")

    admin_user = MagicMock()
    admin_user.id = uuid4()
    admin_user.is_active = True
    admin_user.role = UserRole.ADMIN

    async def mock_get_db():
        mock_db = AsyncMock()
        yield mock_db

    app.dependency_overrides[get_current_admin_user] = lambda: admin_user
    app.dependency_overrides[get_db] = mock_get_db

    return app, admin_user


class TestListJobs:
    """Tests for GET /api/v1/admin/jobs endpoint."""

    def test_list_jobs_returns_paginated_results(self):
        """Test that list jobs returns paginated results."""
        app, _ = create_test_app_with_admin()
        job_id = uuid4()
        mock_job = create_mock_job(job_id=job_id)

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_all_jobs.return_value = ([mock_job], 1)
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs")

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert "has_more" in data
            assert data["total"] == 1
            assert len(data["items"]) == 1

    def test_list_jobs_filters_by_job_type(self):
        """Test that list jobs filters by job_type parameter."""
        app, _ = create_test_app_with_admin()

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_all_jobs.return_value = ([], 0)
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs?job_type=jira_refresh")

            assert response.status_code == 200
            mock_service.get_all_jobs.assert_called_once()
            call_kwargs = mock_service.get_all_jobs.call_args.kwargs
            assert call_kwargs["job_type"] == JobType.JIRA_REFRESH

    def test_list_jobs_filters_by_status(self):
        """Test that list jobs filters by status parameter."""
        app, _ = create_test_app_with_admin()

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_all_jobs.return_value = ([], 0)
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs?status=failed")

            assert response.status_code == 200
            mock_service.get_all_jobs.assert_called_once()
            call_kwargs = mock_service.get_all_jobs.call_args.kwargs
            assert call_kwargs["status"] == JobStatus.FAILED

    def test_list_jobs_rejects_invalid_job_type(self):
        """Test that list jobs rejects invalid job_type."""
        app, _ = create_test_app_with_admin()

        client = TestClient(app)
        response = client.get("/api/v1/admin/jobs?job_type=invalid")

        assert response.status_code == 400
        assert "Invalid job_type" in response.json()["detail"]

    def test_list_jobs_rejects_invalid_status(self):
        """Test that list jobs rejects invalid status."""
        app, _ = create_test_app_with_admin()

        client = TestClient(app)
        response = client.get("/api/v1/admin/jobs?status=invalid")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]


class TestGetJobStats:
    """Tests for GET /api/v1/admin/jobs/stats endpoint."""

    def test_get_job_stats_returns_counts(self):
        """Test that get job stats returns correct counts."""
        app, _ = create_test_app_with_admin()

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_job_stats.return_value = {
                "pending": 5,
                "in_progress": 2,
                "completed": 100,
                "failed": 3,
                "total": 110,
                "by_type": {
                    "jira_refresh": 50,
                    "bulk_import": 60,
                },
            }
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.get("/api/v1/admin/jobs/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["pending"] == 5
            assert data["in_progress"] == 2
            assert data["completed"] == 100
            assert data["failed"] == 3
            assert data["total"] == 110
            assert data["by_type"]["jira_refresh"] == 50


class TestRetryJob:
    """Tests for POST /api/v1/admin/jobs/{job_id}/retry endpoint."""

    def test_retry_job_resets_status(self):
        """Test that retry job resets job to pending."""
        app, _ = create_test_app_with_admin()
        job_id = uuid4()
        mock_job = create_mock_job(job_id=job_id)

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.manual_retry.return_value = mock_job
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.post(f"/api/v1/admin/jobs/{job_id}/retry")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(job_id)
            assert data["status"] == "pending"

    def test_retry_job_with_reset_attempts(self):
        """Test that retry job passes reset_attempts parameter."""
        app, _ = create_test_app_with_admin()
        job_id = uuid4()
        mock_job = create_mock_job(job_id=job_id, attempts=0)

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.manual_retry.return_value = mock_job
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.post(
                f"/api/v1/admin/jobs/{job_id}/retry?reset_attempts=true"
            )

            assert response.status_code == 200
            mock_service.manual_retry.assert_called_once_with(
                job_id, reset_attempts=True
            )

    def test_retry_job_not_found(self):
        """Test that retry job returns 404 for missing job."""
        app, _ = create_test_app_with_admin()
        job_id = uuid4()

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.manual_retry.return_value = None
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.post(f"/api/v1/admin/jobs/{job_id}/retry")

            assert response.status_code == 404


class TestCancelJob:
    """Tests for DELETE /api/v1/admin/jobs/{job_id} endpoint."""

    def test_cancel_pending_job(self):
        """Test that pending jobs can be cancelled."""
        app, _ = create_test_app_with_admin()
        job_id = uuid4()

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.cancel_job.return_value = True
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.delete(f"/api/v1/admin/jobs/{job_id}")

            assert response.status_code == 204

    def test_cancel_job_not_found_or_not_cancellable(self):
        """Test that cancel returns 404 for missing or non-pending job."""
        app, _ = create_test_app_with_admin()
        job_id = uuid4()

        with patch("app.api.admin.JobService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.cancel_job.return_value = False
            mock_service_class.return_value = mock_service

            client = TestClient(app)
            response = client.delete(f"/api/v1/admin/jobs/{job_id}")

            assert response.status_code == 404
            assert "cannot be cancelled" in response.json()["detail"]
