# Tika Configuration Reference

This document provides a comprehensive reference for all Apache Tika-related environment variables and configuration options in NPD.

## Environment Variables

### All Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TIKA_ENABLED` | No | `false` | Feature flag to enable Tika text extraction for legacy .doc files. Set to `true` to enable .doc support. |
| `TIKA_URL` | No | `http://localhost:9998` | URL of the Tika server. In Docker Compose, this is `http://tika:9998`. |
| `TIKA_TIMEOUT` | No | `60` | Timeout in seconds for text extraction requests. Increase for very large files. |

## Configuration Details

### TIKA_ENABLED

Controls whether the Tika text extraction feature is active.

- **Type**: Boolean
- **Default**: `false`
- **Values**: `true` or `false`

When disabled:
- .doc file uploads are rejected with "unsupported format" error
- No network calls to Tika service
- TikaClient.extract_text() returns `SKIPPED` result

When enabled:
- .doc files are accepted for upload
- Text is extracted via Tika for search indexing
- Requires Tika service to be running

### TIKA_URL

The URL endpoint for the Tika REST API server.

- **Type**: String (URL)
- **Default**: `http://localhost:9998`
- **Docker Default**: `http://tika:9998`

The URL should not include trailing slashes. The TikaClient appends `/tika` for text extraction requests.

### TIKA_TIMEOUT

Maximum time to wait for Tika to extract text from a document.

- **Type**: Integer (seconds)
- **Default**: `60`
- **Recommended**: 60s for files up to 50MB

Large files may require more processing time. The timeout applies to individual HTTP requests to Tika.

## Docker Compose Configuration

### Development/Production Environment

The Tika service is defined in `docker-compose.yml`:

```yaml
services:
  tika:
    image: apache/tika:latest
    container_name: npd-tika
    restart: unless-stopped
    ports:
      - "6706:9998"
    healthcheck:
      test: ["CMD", "bash", "-c", "echo > /dev/tcp/localhost/9998"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

### Resource Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| Memory Limit | 1G | Maximum memory Tika can use (JVM heap + overhead) |
| Memory Reservation | 512M | Guaranteed memory allocation |
| Start Period | 30s | Time allowed for JVM startup before health checks |
| Health Check Interval | 30s | Frequency of health status checks |

### Port Mapping

| Host Port | Container Port | Description |
|-----------|----------------|-------------|
| 6706 | 9998 | Tika REST API endpoint |

The host port 6706 follows the NPD port convention (67XX series).

## Configuration Validation

### Verify Configuration is Loaded

```python
# From backend directory
from app.config import get_settings

settings = get_settings()
print(f"Tika Enabled: {settings.tika_enabled}")
print(f"Tika URL: {settings.tika_url}")
print(f"Tika Timeout: {settings.tika_timeout}")
print(f"Tika Configured: {settings.is_tika_configured}")
```

### Configuration Check Script

```bash
# Quick check script
cd backend
python -c "
from app.config import get_settings
s = get_settings()
print('=== Tika Configuration ===')
print(f'Enabled: {s.tika_enabled}')
print(f'URL: {s.tika_url}')
print(f'Timeout: {s.tika_timeout}s')
print(f'Configured: {s.is_tika_configured}')
"
```

### Verify Tika Service

```bash
# Check if Tika container is running
docker compose ps tika

# Test Tika connectivity (from host)
curl -s http://localhost:6706/tika && echo "Tika is responding"

# Test from within backend container
docker compose exec backend curl -s http://tika:9998/tika
```

## Configuration Property

The following computed property is available:

| Property | Description |
|----------|-------------|
| `is_tika_configured` | Returns `True` if Tika is enabled |

### is_tika_configured Logic

```python
@property
def is_tika_configured(self) -> bool:
    """Check if Tika is enabled and configured."""
    return self.tika_enabled
```

Tika is considered configured when `tika_enabled` is `True`. Unlike SharePoint, Tika does not require credentials - it just needs to be enabled and reachable.

## Complete .env Example

```bash
# =============================================================================
# Apache Tika Configuration (Legacy .doc file support)
# =============================================================================

# Feature flag - set to "true" to enable .doc file text extraction
TIKA_ENABLED=true

# Tika server URL (default for Docker: http://tika:9998)
TIKA_URL=http://tika:9998

# Extraction timeout in seconds (increase for very large files)
TIKA_TIMEOUT=60
```

## Docker Compose Backend Environment

When using Docker Compose, configure the backend service:

```yaml
services:
  backend:
    environment:
      # Apache Tika for .doc extraction
      TIKA_ENABLED: "true"
      TIKA_URL: http://tika:9998
      TIKA_TIMEOUT: "60"
```

## Environment-Specific Configuration

### Development (Local)

```bash
# .env.development
TIKA_ENABLED=true
TIKA_URL=http://localhost:6706  # Host port when running outside Docker
TIKA_TIMEOUT=60
```

### Development (Docker)

```bash
# .env (used by docker-compose)
TIKA_ENABLED=true
TIKA_URL=http://tika:9998  # Docker service name
TIKA_TIMEOUT=60
```

### Production

```bash
# Production .env
TIKA_ENABLED=true
TIKA_URL=http://tika:9998
TIKA_TIMEOUT=120  # Higher timeout for production load
```

### Test Environment

```bash
# Test .env
TIKA_ENABLED=true
TIKA_URL=http://tika-test:9998
TIKA_TIMEOUT=30  # Lower timeout for faster test failures
```

## Troubleshooting Configuration

### "Tika extraction is disabled" Message

Check that `TIKA_ENABLED` is set correctly:

```bash
# Verify environment variable
env | grep TIKA

# Expected output for enabled:
# TIKA_ENABLED=true
```

Common causes:
- `TIKA_ENABLED` not set to `true` (default is `false`)
- Variable not exported to backend container
- Typo in variable name or value

### Environment Variable Not Loading

1. Check `.env` file location (must be in `backend/` directory for local dev)
2. Verify no syntax errors in `.env` file
3. Clear settings cache if running interactively:
   ```python
   from app.config import get_settings
   get_settings.cache_clear()
   settings = get_settings()
   ```

### Tika URL Connection Issues

Verify the URL matches your deployment:

| Deployment | Expected URL |
|------------|--------------|
| Docker Compose | `http://tika:9998` |
| Local dev (Tika in Docker) | `http://localhost:6706` |
| Kubernetes | `http://tika-service:9998` |

## Related Documentation

- [Operations Guide](./operations.md) - Monitoring and troubleshooting
- [Rollback Procedure](./rollback.md) - Disabling Tika integration
- [Research](./research.md) - Technology decisions and benchmarks
- [Specification](./spec.md) - Feature requirements
