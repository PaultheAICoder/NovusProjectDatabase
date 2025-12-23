# Performance Monitoring and Metrics

This document describes the performance monitoring capabilities implemented in the Novus Project Database.

## Overview

The system provides comprehensive performance monitoring through:
- Request timing middleware
- In-memory metrics aggregation
- Enhanced health check endpoint
- Admin metrics API endpoint

## Key Metrics

### 1. Response Times

Tracked per-endpoint with the following percentiles:
- **P50** - 50th percentile (median) response time in milliseconds
- **P95** - 95th percentile response time
- **P99** - 99th percentile response time
- **Average** - Mean response time
- **Max** - Maximum observed response time

### 2. Error Rates

Aggregated at both global and per-endpoint levels:
- **Total Requests** - Count of all requests processed
- **Total Errors** - Count of 4xx and 5xx responses
- **4xx Count** - Client errors (bad requests, not found, etc.)
- **5xx Count** - Server errors
- **Error Rate %** - Percentage of requests resulting in errors

### 3. Cache Statistics

Available for each cache type:
- **Tag Cache** - Frequently accessed tags
- **Organization Cache** - Organization lookup cache
- **Dashboard Cache** - Dashboard aggregation data
- **Search Cache** - Search result caching

Stats include: hits, misses, hit rate, entries count, type (redis/in_memory).

### 4. Database Pool

Connection pool configuration:
- **Pool Size** - Configured connection pool size
- **Max Overflow** - Maximum additional connections allowed

## Endpoints

### Health Check - `GET /health`

Returns system health status with key metrics:

```json
{
  "status": "healthy|degraded",
  "version": "1.0.0",
  "uptime_seconds": 3600.0,
  "database": "connected",
  "cache": "redis",
  "error_rate_percent": 0.5,
  "avg_response_time_ms": 45.2
}
```

**Status determination:**
- `healthy` - Error rate < 5% AND average response time < 1000ms
- `degraded` - Error rate >= 5% OR average response time >= 1000ms

### Admin Metrics - `GET /api/v1/admin/metrics`

Returns detailed system metrics (admin authentication required):

```json
{
  "collected_at": "2025-12-23T12:00:00Z",
  "uptime_seconds": 3600.0,
  "request_metrics": {
    "total_requests": 10000,
    "total_errors": 50,
    "error_4xx_count": 40,
    "error_5xx_count": 10,
    "error_rate_percent": 0.5
  },
  "endpoints": [
    {
      "path": "/api/v1/projects",
      "method": "GET",
      "request_count": 500,
      "error_count": 5,
      "error_rate_percent": 1.0,
      "p50_ms": 45.0,
      "p95_ms": 120.0,
      "p99_ms": 250.0,
      "avg_ms": 55.0,
      "max_ms": 500.0
    }
  ],
  "cache": {
    "tag_cache": {"hits": 1000, "misses": 50, "hit_rate": 0.95},
    "org_cache": {},
    "dashboard_cache": {},
    "search_cache": {}
  },
  "database": {
    "pool_size": 5,
    "max_overflow": 10
  },
  "slow_request_threshold_ms": 500.0
}
```

Query parameter:
- `top_endpoints` (int, 1-100, default 20): Number of top endpoints to return

## Response Headers

All responses include a timing header:
- `X-Response-Time-Ms`: Request processing time in milliseconds

## Logging

### Request Timing Logs

All requests are logged with timing information:
- **Normal requests**: Logged at DEBUG level
- **Slow requests (>500ms)**: Logged at WARNING level with `slow_request` event

### Search Service Logs

Search queries have additional timing:
- **Slow searches (>500ms)**: Logged at WARNING level with `slow_search_query` event

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SLOW_REQUEST_THRESHOLD_MS` | 500 | Threshold for slow request warnings |
| `MAX_REQUESTS_PER_ENDPOINT` | 1000 | Rolling window size for metrics |

## Architecture

```
Request
   |
   v
TimingMiddleware -----> MetricsService (singleton)
   |                         |
   v                         v
Application              In-memory storage
   |                    (thread-safe deque)
   v
Response + X-Response-Time-Ms header
```

The MetricsService uses:
- Thread-safe data structures for concurrent access
- Bounded deques to limit memory usage
- On-demand percentile calculation

## Related Files

- `backend/app/middleware/timing.py` - Request timing middleware
- `backend/app/services/metrics_service.py` - Metrics aggregation service
- `backend/app/schemas/metrics.py` - Pydantic response schemas
- `backend/app/main.py` - Health endpoint, middleware registration
- `backend/app/api/admin.py` - Admin metrics endpoint
