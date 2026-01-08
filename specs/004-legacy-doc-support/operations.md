# Tika Operations Guide

This document provides operational guidance for monitoring, maintaining, and troubleshooting the Apache Tika integration for legacy .doc file support.

## Health Monitoring

### Tika Health Check API

The TikaClient includes a built-in health check method:

```python
from app.services.tika_client import TikaClient

client = TikaClient()
is_healthy = await client.health_check()
# Returns True if Tika responds with HTTP 200
```

**Health Check Behavior:**
- Endpoint: `GET /tika`
- Expected Response: HTTP 200
- Timeout: 5 seconds (hardcoded for health checks)
- Returns `False` if Tika is disabled (`TIKA_ENABLED=false`)

### Container Health Check

Docker Compose includes a healthcheck configuration:

```yaml
healthcheck:
  test: ["CMD", "bash", "-c", "echo > /dev/tcp/localhost/9998"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

This checks TCP connectivity to port 9998 inside the container.

## Monitoring Commands

### Check Tika Container Status

```bash
# View container status
docker compose ps tika

# Expected output when healthy:
# NAME       IMAGE               STATUS                   PORTS
# npd-tika   apache/tika:latest  Up X minutes (healthy)   0.0.0.0:6706->9998/tcp
```

### View Tika Logs

```bash
# View recent logs
docker compose logs tika --tail=100

# Follow logs in real-time
docker compose logs tika -f

# Filter for errors
docker compose logs tika 2>&1 | grep -i error
```

### Test Tika Connectivity

```bash
# From host machine (using mapped port 6706)
curl -s http://localhost:6706/tika
# Response: "This is Tika Server..."

# From backend container
docker compose exec backend curl -s http://tika:9998/tika

# Verbose connection test
curl -v http://localhost:6706/tika
```

### Test Text Extraction

```bash
# Create a test request (using a text file as example)
echo "Hello World" > /tmp/test.txt
curl -X PUT -H "Content-Type: text/plain" \
  -d @/tmp/test.txt \
  http://localhost:6706/tika
# Response: "Hello World"
```

### Monitor Resource Usage

```bash
# View container resource stats
docker stats npd-tika --no-stream

# Expected output:
# CONTAINER   CPU %   MEM USAGE / LIMIT   MEM %
# npd-tika    0.50%   400MiB / 1GiB       39.06%
```

## Performance Benchmarks

Based on Tika documentation and testing:

| File Size | Extraction Time | Memory Usage |
|-----------|-----------------|--------------|
| 100 KB | < 1s | ~50 MB |
| 1 MB | 1-3s | ~100 MB |
| 10 MB | 5-15s | ~300 MB |
| 50 MB | 30-60s | ~500 MB |

### Performance Recommendations

- **Memory Limit**: 1GB provides headroom for large files
- **Timeout**: 60s default handles files up to 50MB
- **Concurrency**: Tika handles concurrent requests but memory usage scales
- **Large Files**: Consider async processing for files > 10MB

## Log Analysis

### TikaClient Log Events

The TikaClient emits structured logs:

| Event | Level | Description |
|-------|-------|-------------|
| `tika_extraction_success` | INFO | Text extraction completed |
| `tika_extraction_skipped` | DEBUG | Tika disabled, extraction skipped |
| `tika_extraction_timeout` | WARNING | Extraction timed out |
| `tika_connection_error_retrying` | WARNING | Connection failed, retrying |
| `tika_connection_error_final` | WARNING | Connection failed after all retries |
| `tika_client_error` | ERROR | HTTP 4xx response |
| `tika_server_error_retrying` | WARNING | HTTP 5xx, retrying |
| `tika_server_error_final` | ERROR | HTTP 5xx after all retries |
| `tika_extraction_error` | ERROR | Unexpected error during extraction |
| `tika_health_check_success` | DEBUG | Health check passed |
| `tika_health_check_failed` | WARNING | Health check failed |
| `tika_health_check_error` | WARNING | Health check error |

### Example Log Queries

```bash
# Find all extraction errors
docker compose logs backend 2>&1 | grep -E "tika_.*error"

# Find successful extractions
docker compose logs backend 2>&1 | grep "tika_extraction_success"

# Find timeout events
docker compose logs backend 2>&1 | grep "tika_extraction_timeout"
```

## Troubleshooting Common Issues

### Issue: Tika Unavailable (Connection Errors)

**Symptoms:**
- `tika_connection_error_final` in logs
- `ExtractionResult.ERROR` with message "Cannot connect to Tika"

**Diagnosis:**
```bash
# Check if container is running
docker compose ps tika

# Check container logs for startup errors
docker compose logs tika --tail=50

# Test network connectivity
docker compose exec backend ping -c 3 tika
```

**Solutions:**
1. **Container not running**: `docker compose up -d tika`
2. **Container crashing**: Check logs, may need to increase memory
3. **Network issue**: Verify Docker network configuration
4. **Wrong URL**: Verify `TIKA_URL` configuration

### Issue: Extraction Timeouts (Large Files)

**Symptoms:**
- `tika_extraction_timeout` in logs
- `ExtractionResult.ERROR` with message "Extraction timed out"

**Diagnosis:**
```bash
# Check file size of problematic uploads
docker compose exec backend ls -lh /app/uploads/
```

**Solutions:**
1. **Increase timeout**: Set `TIKA_TIMEOUT=120` for very large files
2. **Check memory**: Large files need more memory, monitor with `docker stats`
3. **Async processing**: Consider background processing for files > 10MB

### Issue: JVM Memory Issues

**Symptoms:**
- Tika container crashes during extraction
- "OutOfMemoryError" in Tika logs
- Container restarts unexpectedly

**Diagnosis:**
```bash
# Check memory usage
docker stats npd-tika --no-stream

# Look for OOM errors in logs
docker compose logs tika 2>&1 | grep -i "memory\|oom"
```

**Solutions:**
1. **Increase memory limit** in docker-compose.yml:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
       reservations:
         memory: 1G
   ```
2. **Restart container**: `docker compose restart tika`

### Issue: Corrupted or Password-Protected Files

**Symptoms:**
- `tika_client_error` with HTTP 422 status
- Empty text extraction result

**Diagnosis:**
- Check the original file - can it be opened in Word?
- Try extracting with Tika directly via curl

**Solutions:**
1. **Corrupted files**: Cannot be fixed; log error and inform user
2. **Password-protected**: NPD does not support encrypted documents
3. **Format issue**: Verify file is actually .doc format (not renamed)

### Issue: Empty Extraction Results

**Symptoms:**
- Extraction succeeds but returns empty or minimal text
- Document appears to have content in Word

**Possible Causes:**
1. **Scanned document**: Image-only PDFs/docs need OCR (not supported)
2. **Drawing objects**: Text in shapes/drawings may not extract
3. **Embedded content**: Text in embedded objects may not extract

**Solutions:**
- Inform users about limitations
- Consider adding OCR support in future version

## Retry Behavior

The TikaClient implements automatic retries for transient failures:

| Error Type | Retry Behavior |
|------------|----------------|
| Connection errors | Retry up to 3 times with exponential backoff |
| HTTP 5xx errors | Retry up to 3 times with exponential backoff |
| HTTP 4xx errors | No retry (client error) |
| Timeout errors | No retry (file is too large or complex) |

**Backoff Schedule:**
- Attempt 1: Immediate
- Attempt 2: 1 second delay
- Attempt 3: 2 seconds delay

## Maintenance Tasks

### Restart Tika Service

```bash
# Graceful restart
docker compose restart tika

# Force recreate
docker compose up -d --force-recreate tika
```

### Update Tika Version

```bash
# Pull latest image
docker compose pull tika

# Recreate with new image
docker compose up -d --force-recreate tika

# Verify new version
docker compose exec tika java -jar /tika-server.jar --version
```

### Clear Tika Cache

Tika Server does not maintain significant cache, but restarting clears any in-memory state:

```bash
docker compose restart tika
```

## Capacity Planning

### Resource Requirements

| Workload | Memory | CPU | Notes |
|----------|--------|-----|-------|
| Light (< 10 docs/day) | 512MB | 0.5 | Default reservation |
| Medium (10-100 docs/day) | 1GB | 1 | Default limit |
| Heavy (100+ docs/day) | 2GB | 2 | Increase limits |

### Scaling Considerations

- Tika is stateless - multiple instances can run behind a load balancer
- Each instance needs its own memory allocation
- Consider Kubernetes with HPA for auto-scaling

## Related Documentation

- [Configuration Reference](./configuration.md) - Environment variables
- [Rollback Procedure](./rollback.md) - Disabling Tika integration
- [Research](./research.md) - Technology decisions
- [Specification](./spec.md) - Feature requirements
