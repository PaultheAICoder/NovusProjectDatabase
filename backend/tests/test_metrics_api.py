"""Tests for metrics API endpoints."""

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


class TestMetricsAPI:
    """Tests for /api/v1/admin/metrics endpoint."""

    def test_health_endpoint_returns_status(self):
        """Test that health endpoint returns expected fields."""
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "uptime_seconds" in data
        assert "cache" in data
        assert "version" in data
        assert "error_rate_percent" in data
        assert "avg_response_time_ms" in data

    def test_health_endpoint_status_is_healthy_or_degraded(self):
        """Test that status is one of expected values."""
        client = TestClient(app)

        response = client.get("/health")
        data = response.json()

        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_endpoint_version_format(self):
        """Test that version is in expected format."""
        client = TestClient(app)

        response = client.get("/health")
        data = response.json()

        # Version should be semver-like
        assert "." in data["version"]

    def test_health_endpoint_uptime_is_positive(self):
        """Test that uptime is a positive number."""
        client = TestClient(app)

        response = client.get("/health")
        data = response.json()

        assert data["uptime_seconds"] >= 0

    def test_health_endpoint_error_rate_is_percentage(self):
        """Test that error rate is a valid percentage."""
        client = TestClient(app)

        response = client.get("/health")
        data = response.json()

        assert 0 <= data["error_rate_percent"] <= 100

    def test_timing_header_added_to_response(self):
        """Test that X-Response-Time-Ms header is present."""
        client = TestClient(app)

        response = client.get("/health")

        assert "X-Response-Time-Ms" in response.headers
        # Should be parseable as float
        timing = float(response.headers["X-Response-Time-Ms"])
        assert timing >= 0

    def test_root_endpoint_has_timing_header(self):
        """Test that root endpoint also has timing header."""
        client = TestClient(app)

        response = client.get("/")

        assert "X-Response-Time-Ms" in response.headers
