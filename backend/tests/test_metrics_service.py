"""Tests for metrics service."""

import time

from app.services.metrics_service import (
    MetricsService,
    get_metrics_service,
    reset_metrics_service,
)


class TestMetricsService:
    """Tests for MetricsService class."""

    def setup_method(self):
        """Reset metrics before each test."""
        reset_metrics_service()

    def teardown_method(self):
        """Reset metrics after each test."""
        reset_metrics_service()

    def test_record_request_tracks_timing(self):
        """Test that record_request stores timing data."""
        service = MetricsService()

        service.record_request(
            method="GET",
            path="/api/v1/projects",
            status_code=200,
            duration_ms=50.0,
        )

        endpoints = service.get_endpoint_metrics()
        assert len(endpoints) == 1
        assert endpoints[0]["path"] == "/api/v1/projects"
        assert endpoints[0]["method"] == "GET"
        assert endpoints[0]["request_count"] == 1

    def test_record_request_tracks_errors(self):
        """Test that 4xx and 5xx responses are counted as errors."""
        service = MetricsService()

        # Record successful request
        service.record_request("GET", "/test", 200, 10.0)
        # Record 4xx error
        service.record_request("GET", "/test", 404, 10.0)
        # Record 5xx error
        service.record_request("GET", "/test", 500, 10.0)

        error_rates = service.get_error_rates()
        assert error_rates["total_requests"] == 3
        assert error_rates["total_errors"] == 2
        assert error_rates["error_4xx_count"] == 1
        assert error_rates["error_5xx_count"] == 1

    def test_percentile_calculation(self):
        """Test P50/P95/P99 calculation."""
        service = MetricsService()

        # Record 100 requests with known timings
        for i in range(100):
            service.record_request("GET", "/test", 200, float(i + 1))

        endpoints = service.get_endpoint_metrics()
        assert len(endpoints) == 1

        # P50 should be around 50ms
        assert 49 <= endpoints[0]["p50_ms"] <= 51
        # P95 should be around 95ms
        assert 94 <= endpoints[0]["p95_ms"] <= 96
        # P99 should be around 99ms
        assert 98 <= endpoints[0]["p99_ms"] <= 100

    def test_multiple_endpoints_tracked_separately(self):
        """Test that different endpoints are tracked independently."""
        service = MetricsService()

        service.record_request("GET", "/api/v1/projects", 200, 10.0)
        service.record_request("POST", "/api/v1/projects", 201, 20.0)
        service.record_request("GET", "/api/v1/search", 200, 30.0)

        endpoints = service.get_endpoint_metrics()
        assert len(endpoints) == 3

    def test_error_rate_percent_calculation(self):
        """Test error rate percentage is calculated correctly."""
        service = MetricsService()

        # 10 requests, 2 errors = 20%
        for _ in range(8):
            service.record_request("GET", "/test", 200, 10.0)
        service.record_request("GET", "/test", 404, 10.0)
        service.record_request("GET", "/test", 500, 10.0)

        error_rates = service.get_error_rates()
        assert error_rates["error_rate_percent"] == 20.0

    def test_singleton_accessor(self):
        """Test get_metrics_service returns same instance."""
        service1 = get_metrics_service()
        service2 = get_metrics_service()

        assert service1 is service2

    def test_reset_clears_all_data(self):
        """Test that reset clears all metrics."""
        service = MetricsService()

        service.record_request("GET", "/test", 200, 10.0)
        service.reset()

        endpoints = service.get_endpoint_metrics()
        error_rates = service.get_error_rates()

        assert len(endpoints) == 0
        assert error_rates["total_requests"] == 0

    def test_uptime_increases(self):
        """Test uptime tracking."""
        service = MetricsService()

        uptime1 = service.get_uptime_seconds()
        time.sleep(0.1)
        uptime2 = service.get_uptime_seconds()

        assert uptime2 > uptime1

    def test_top_n_endpoints(self):
        """Test that get_endpoint_metrics respects top_n parameter."""
        service = MetricsService()

        # Create 5 endpoints with varying request counts
        for i in range(5):
            for _ in range(i + 1):
                service.record_request("GET", f"/endpoint{i}", 200, 10.0)

        # Should return top 3
        endpoints = service.get_endpoint_metrics(top_n=3)
        assert len(endpoints) == 3
        # Highest count should be first
        assert endpoints[0]["request_count"] >= endpoints[1]["request_count"]

    def test_average_response_time(self):
        """Test average response time calculation."""
        service = MetricsService()

        # Record 4 requests with known times
        service.record_request("GET", "/test1", 200, 10.0)
        service.record_request("GET", "/test1", 200, 20.0)
        service.record_request("GET", "/test2", 200, 30.0)
        service.record_request("GET", "/test2", 200, 40.0)

        avg = service.get_average_response_time()
        # Average should be (10+20+30+40)/4 = 25
        assert avg == 25.0

    def test_empty_service_returns_defaults(self):
        """Test that empty service returns sensible defaults."""
        service = MetricsService()

        endpoints = service.get_endpoint_metrics()
        error_rates = service.get_error_rates()
        avg = service.get_average_response_time()

        assert len(endpoints) == 0
        assert error_rates["total_requests"] == 0
        assert error_rates["error_rate_percent"] == 0
        assert avg == 0

    def test_max_ms_calculation(self):
        """Test max response time is tracked correctly."""
        service = MetricsService()

        service.record_request("GET", "/test", 200, 10.0)
        service.record_request("GET", "/test", 200, 100.0)
        service.record_request("GET", "/test", 200, 50.0)

        endpoints = service.get_endpoint_metrics()
        assert endpoints[0]["max_ms"] == 100.0

    def test_endpoint_error_rate(self):
        """Test per-endpoint error rate calculation."""
        service = MetricsService()

        # 4 requests, 1 error = 25%
        service.record_request("GET", "/test", 200, 10.0)
        service.record_request("GET", "/test", 200, 10.0)
        service.record_request("GET", "/test", 200, 10.0)
        service.record_request("GET", "/test", 500, 10.0)

        endpoints = service.get_endpoint_metrics()
        assert endpoints[0]["error_count"] == 1
        assert endpoints[0]["error_rate_percent"] == 25.0
