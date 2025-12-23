"""Tests for timing middleware."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.timing import SLOW_REQUEST_THRESHOLD_MS, TimingMiddleware


class TestTimingMiddleware:
    """Tests for TimingMiddleware class."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/test"
        return request

    @pytest.fixture
    def mock_response(self):
        """Create mock response."""
        response = MagicMock(spec=Response)
        response.status_code = 200
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_adds_timing_header(self, mock_request, mock_response):
        """Test that X-Response-Time-Ms header is added."""

        async def call_next(request):
            return mock_response

        # Patch at the source module where it's imported
        with patch(
            "app.services.metrics_service.get_metrics_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            middleware = TimingMiddleware(MagicMock())
            result = await middleware.dispatch(mock_request, call_next)

            assert "X-Response-Time-Ms" in result.headers

    @pytest.mark.asyncio
    async def test_records_to_metrics_service(self, mock_request, mock_response):
        """Test that request is recorded in metrics service."""

        async def call_next(request):
            return mock_response

        with patch(
            "app.services.metrics_service.get_metrics_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            middleware = TimingMiddleware(MagicMock())
            await middleware.dispatch(mock_request, call_next)

            mock_service.record_request.assert_called_once()
            call_args = mock_service.record_request.call_args
            assert call_args.kwargs["method"] == "GET"
            assert call_args.kwargs["path"] == "/api/v1/test"
            assert call_args.kwargs["status_code"] == 200

    @pytest.mark.asyncio
    async def test_slow_request_threshold_configured(self):
        """Test that slow request threshold constant is defined."""
        assert SLOW_REQUEST_THRESHOLD_MS == 500

    @pytest.mark.asyncio
    async def test_timing_is_positive(self, mock_request, mock_response):
        """Test that recorded timing is a positive number."""

        async def call_next(request):
            return mock_response

        with patch(
            "app.services.metrics_service.get_metrics_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            middleware = TimingMiddleware(MagicMock())
            await middleware.dispatch(mock_request, call_next)

            call_args = mock_service.record_request.call_args
            assert call_args.kwargs["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_header_value_is_float_string(self, mock_request, mock_response):
        """Test that header value is a properly formatted float string."""

        async def call_next(request):
            return mock_response

        with patch(
            "app.services.metrics_service.get_metrics_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            middleware = TimingMiddleware(MagicMock())
            result = await middleware.dispatch(mock_request, call_next)

            # Should be parseable as float
            timing_value = float(result.headers["X-Response-Time-Ms"])
            assert timing_value >= 0
