"""Metrics aggregation service for performance monitoring."""

import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import NamedTuple

from app.core.logging import get_logger

logger = get_logger(__name__)

# Rolling window size for metrics retention
MAX_REQUESTS_PER_ENDPOINT = 1000
STARTUP_TIME = time.time()


class RequestRecord(NamedTuple):
    """Single request timing record."""

    timestamp: float
    duration_ms: float
    status_code: int


@dataclass
class EndpointStats:
    """Stats container for a single endpoint."""

    timings: deque = field(
        default_factory=lambda: deque(maxlen=MAX_REQUESTS_PER_ENDPOINT)
    )
    lock: Lock = field(default_factory=Lock)


class MetricsService:
    """Service for aggregating performance metrics."""

    def __init__(self) -> None:
        self._endpoints: dict[str, EndpointStats] = defaultdict(EndpointStats)
        self._global_lock = Lock()
        self._total_requests = 0
        self._total_errors = 0
        self._error_4xx = 0
        self._error_5xx = 0

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record a request's timing and status."""
        key = f"{method} {path}"
        record = RequestRecord(
            timestamp=time.time(),
            duration_ms=duration_ms,
            status_code=status_code,
        )

        with self._global_lock:
            self._total_requests += 1
            if 400 <= status_code < 500:
                self._error_4xx += 1
                self._total_errors += 1
            elif status_code >= 500:
                self._error_5xx += 1
                self._total_errors += 1

        stats = self._endpoints[key]
        with stats.lock:
            stats.timings.append(record)

    def get_endpoint_metrics(self, top_n: int = 20) -> list[dict]:
        """Get metrics for top N endpoints by request count."""
        results = []

        for key, stats in self._endpoints.items():
            with stats.lock:
                if not stats.timings:
                    continue

                method, path = key.split(" ", 1)
                timings = [r.duration_ms for r in stats.timings]
                errors = sum(1 for r in stats.timings if r.status_code >= 400)

                sorted_timings = sorted(timings)
                n = len(sorted_timings)

                results.append(
                    {
                        "path": path,
                        "method": method,
                        "request_count": n,
                        "error_count": errors,
                        "error_rate_percent": (
                            round((errors / n) * 100, 2) if n > 0 else 0
                        ),
                        "p50_ms": round(self._percentile(sorted_timings, 50), 2),
                        "p95_ms": round(self._percentile(sorted_timings, 95), 2),
                        "p99_ms": round(self._percentile(sorted_timings, 99), 2),
                        "avg_ms": (
                            round(statistics.mean(timings), 2) if timings else 0
                        ),
                        "max_ms": round(max(timings), 2) if timings else 0,
                    }
                )

        # Sort by request count descending
        results.sort(key=lambda x: x["request_count"], reverse=True)
        return results[:top_n]

    def get_error_rates(self) -> dict:
        """Get global error rate statistics."""
        with self._global_lock:
            total = self._total_requests
            errors = self._total_errors
            rate = (errors / total * 100) if total > 0 else 0

            return {
                "total_requests": total,
                "total_errors": errors,
                "error_4xx_count": self._error_4xx,
                "error_5xx_count": self._error_5xx,
                "error_rate_percent": round(rate, 2),
            }

    def get_average_response_time(self) -> float:
        """Get overall average response time."""
        all_timings = []
        for stats in self._endpoints.values():
            with stats.lock:
                all_timings.extend(r.duration_ms for r in stats.timings)

        return round(statistics.mean(all_timings), 2) if all_timings else 0

    def get_uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        return round(time.time() - STARTUP_TIME, 2)

    @staticmethod
    def _percentile(sorted_data: list[float], p: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0
        n = len(sorted_data)
        k = (n - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < n else f
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._global_lock:
            self._endpoints.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._error_4xx = 0
            self._error_5xx = 0


# Singleton instance
_metrics_service: MetricsService | None = None


def get_metrics_service() -> MetricsService:
    """Get or create the global metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
        logger.info("metrics_service_initialized")
    return _metrics_service


def reset_metrics_service() -> None:
    """Reset metrics service (for testing)."""
    global _metrics_service
    if _metrics_service:
        _metrics_service.reset()
    _metrics_service = None
