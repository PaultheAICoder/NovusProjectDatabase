"""Request timing middleware for performance monitoring."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

SLOW_REQUEST_THRESHOLD_MS = 500  # Configurable threshold


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing and log slow requests."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Track request timing and record to metrics service."""
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Get metrics service and record
        from app.services.metrics_service import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        # Log timing
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.warning("slow_request", **log_data)
        else:
            logger.debug("request_timing", **log_data)

        # Add timing header for debugging
        response.headers["X-Response-Time-Ms"] = str(round(duration_ms, 2))

        return response
