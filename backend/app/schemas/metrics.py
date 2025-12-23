"""Metrics response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class EndpointMetrics(BaseModel):
    """Metrics for a single endpoint."""

    path: str
    method: str
    request_count: int = 0
    error_count: int = 0  # 4xx + 5xx
    error_rate_percent: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_ms: float = 0.0
    max_ms: float = 0.0


class ErrorRateMetrics(BaseModel):
    """Error rate aggregations."""

    total_requests: int = 0
    total_errors: int = 0
    error_4xx_count: int = 0
    error_5xx_count: int = 0
    error_rate_percent: float = 0.0


class DatabaseMetrics(BaseModel):
    """Database connection pool metrics."""

    pool_size: int = Field(..., description="Configured pool size")
    max_overflow: int = Field(..., description="Max overflow connections")
    # Note: Actual usage requires SQLAlchemy pool instrumentation


class CacheMetrics(BaseModel):
    """Cache statistics summary."""

    tag_cache: dict = Field(default_factory=dict)
    org_cache: dict = Field(default_factory=dict)
    dashboard_cache: dict = Field(default_factory=dict)
    search_cache: dict = Field(default_factory=dict)


class SystemMetricsResponse(BaseModel):
    """Complete system metrics response."""

    collected_at: datetime
    uptime_seconds: float
    request_metrics: ErrorRateMetrics
    endpoints: list[EndpointMetrics] = Field(
        default_factory=list,
        description="Per-endpoint metrics, sorted by request count",
    )
    cache: CacheMetrics
    database: DatabaseMetrics
    slow_request_threshold_ms: float = 500.0


class HealthCheckResponse(BaseModel):
    """Enhanced health check response."""

    status: str = Field(..., description="healthy, degraded, or unhealthy")
    version: str = "1.0.0"
    uptime_seconds: float
    database: str = Field(..., description="connected or error message")
    cache: str = Field(..., description="redis, in_memory, or error")
    error_rate_percent: float = 0.0
    avg_response_time_ms: float = 0.0
