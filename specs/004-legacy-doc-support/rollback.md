# Tika Integration Rollback Procedure

This document provides procedures for rolling back the Apache Tika integration if issues are encountered after deployment.

## When to Rollback

Consider initiating a rollback when:

### Critical Issues (Immediate Rollback)

- **Service crashes**: Tika container repeatedly crashing, affecting backend stability
- **Data corruption**: Document text being corrupted during extraction
- **Security incident**: Suspected vulnerability or unauthorized access via Tika
- **Complete unavailability**: Tika unreachable with no ETA for resolution

### Performance Issues (Evaluate First)

- **Consistent high latency**: Document uploads taking >30 seconds regularly
- **Resource exhaustion**: Tika consuming excessive memory, affecting other services
- **Queue backlog**: Documents queuing faster than extraction can process

### Operational Issues (Plan Rollback)

- **Maintenance window**: Extended Tika maintenance needed
- **Version incompatibility**: Tika update breaks extraction
- **Resource constraints**: Need to free up container resources

## Rollback Decision Matrix

| Issue Severity | User Impact | Recommended Action |
|----------------|-------------|-------------------|
| Critical | All .doc uploads failing | Immediate Quick Rollback (Option A) |
| High | Many extraction failures | Quick Rollback within 1 hour |
| Medium | Slow extractions | Evaluate, plan rollback if no fix |
| Low | Occasional issues | Monitor, fix if possible |

## Rollback Options

### Option A: Quick Rollback (Disable Tika)

**Time**: 5 minutes
**Impact**: .doc files rejected at upload; existing documents unaffected
**Use when**: Immediate action needed, temporary solution

#### Steps

1. **Update environment configuration**:
   ```bash
   # In your .env file or environment
   TIKA_ENABLED=false
   ```

2. **Restart backend service**:
   ```bash
   # Docker
   docker compose restart backend

   # Or systemd
   sudo systemctl restart npd-backend

   # Or manual
   pkill -f uvicorn && uvicorn app.main:app --host 0.0.0.0 --port 6701
   ```

3. **Verify rollback**:
   ```bash
   cd backend
   python -c "
   from app.config import get_settings
   s = get_settings()
   print(f'Tika enabled: {s.tika_enabled}')
   print(f'Expected: False')
   "
   ```

4. **Test behavior**:
   - Attempt to upload a .doc file
   - Verify it's rejected with "unsupported format" message
   - Verify other file types (.pdf, .docx) still work

#### What Happens

When `TIKA_ENABLED=false`:
- .doc files are rejected at upload with "unsupported format" error
- TikaClient.extract_text() returns `SKIPPED` result without network call
- Existing documents in database remain unchanged
- Previously extracted text remains indexed and searchable
- No data loss occurs

#### Limitations

- New .doc files cannot be uploaded until re-enabled
- Does not process any backlog of failed extractions

### Option B: Monitor Mode (Keep Tika, Increase Logging)

**Time**: 5 minutes
**Impact**: Maintains current state while investigating
**Use when**: Issue is intermittent, need time to diagnose

#### Steps

1. **Enable debug logging**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **Restart backend**:
   ```bash
   docker compose restart backend
   ```

3. **Monitor for specific errors**:
   ```bash
   # Watch logs for Tika errors
   docker compose logs -f backend | grep -E "tika_"
   ```

4. **Collect metrics**:
   - Extraction success/failure rates
   - Average extraction time
   - Error messages and patterns

5. **Make informed decision**:
   - If issues persist: Proceed to Option A or C
   - If issues resolve: Continue monitoring, reduce log level

### Option C: Full Removal (Stop Tika Container)

**Time**: 10 minutes
**Impact**: Tika container stopped, resources freed
**Use when**: Long-term decision to disable .doc support, resource recovery needed

#### Steps

1. **Disable Tika first** (Option A steps 1-3)

2. **Stop Tika container**:
   ```bash
   docker compose stop tika
   ```

3. **Remove Tika container** (optional):
   ```bash
   docker compose rm tika
   ```

4. **Comment out Tika service** in docker-compose.yml (optional):
   ```yaml
   # Commented out for rollback
   # tika:
   #   image: apache/tika:latest
   #   ...
   ```

5. **Verify resources freed**:
   ```bash
   docker ps  # Tika should not appear
   docker stats --no-stream  # Memory should be freed
   ```

## Post-Rollback Verification

### Verify Backend Functionality

```bash
# Check backend is running
docker compose ps backend

# Test API health
curl http://localhost:6701/health

# Test document upload (non-.doc)
curl -X POST http://localhost:6701/api/v1/projects/1/documents \
  -F "file=@test.pdf"
```

### Verify .doc Files Rejected

```bash
# Attempt .doc upload (should fail)
curl -X POST http://localhost:6701/api/v1/projects/1/documents \
  -F "file=@test.doc"

# Expected response: 400 Bad Request, "unsupported format"
```

### Verify Existing Documents Accessible

1. Search for content that was extracted from .doc files
2. Download previously uploaded .doc files
3. Verify search results include historical .doc content

### Monitor for Issues

```bash
# Watch for errors in logs
docker compose logs -f backend | grep -E "error|ERROR|exception"
```

## Communication Templates

### Initiating Rollback

```
Subject: Document Processing Maintenance - .doc Upload Temporarily Disabled

We are temporarily disabling .doc file uploads due to a technical issue
with our document processing service.

Current Status:
- .doc file uploads are temporarily unavailable
- All other file types (.pdf, .docx, .xlsx) work normally
- Existing documents remain accessible

Impact:
- New .doc files cannot be uploaded until service is restored
- This does not affect previously uploaded documents

We are working to resolve this issue and will provide an update within [TIMEFRAME].

Workaround:
- Convert .doc files to .docx format before uploading
- Use Microsoft Word or LibreOffice to save as .docx

Please contact [SUPPORT CONTACT] for urgent needs.
```

### Rollback Complete

```
Subject: .doc Upload Service Restored

The document processing service has been restored. .doc file uploads
are now working normally.

Status:
- All document features are available
- .doc file uploads are accepted
- No action required from users

If you experience any issues, please contact [SUPPORT CONTACT].
```

### Extended Outage Communication

```
Subject: .doc Upload Service - Extended Maintenance

Summary:
.doc file upload support will remain disabled while we address
a technical issue with our document processing infrastructure.

Timeline:
- Service disabled: [DATE/TIME]
- Expected resolution: [DATE/TIME]

Impact:
- .doc files cannot be uploaded until restored
- Alternative: Convert to .docx format before uploading
- Existing .doc documents remain accessible

We will send an update when service is restored.
```

## Prevention and Preparation

### Before Go-Live

- [ ] Test rollback procedure in staging environment
- [ ] Document current state (Tika version, configuration)
- [ ] Verify backend works correctly with Tika disabled
- [ ] Have rollback commands ready

### Ongoing

- [ ] Monitor Tika health and resource usage
- [ ] Set up alerts for extraction failures
- [ ] Regular Tika container updates
- [ ] Keep rollback documentation updated

## Recovery After Rollback

If you need to re-enable Tika after a rollback:

### Re-enable Steps

1. **Resolve root cause** of the original issue

2. **Test fix** in non-production environment

3. **Start Tika container** (if stopped):
   ```bash
   docker compose up -d tika
   ```

4. **Verify Tika health**:
   ```bash
   curl http://localhost:6706/tika
   ```

5. **Re-enable in configuration**:
   ```bash
   TIKA_ENABLED=true
   ```

6. **Restart backend**:
   ```bash
   docker compose restart backend
   ```

7. **Test .doc upload**:
   - Upload a test .doc file
   - Verify extraction succeeds
   - Verify search indexes the content

8. **Monitor closely** for recurrence:
   ```bash
   docker compose logs -f backend | grep tika_
   ```

### Reprocessing Failed Documents

If documents failed during the outage:

1. Identify affected documents (check upload error logs)
2. Request users re-upload affected .doc files
3. Or implement admin tool to requeue failed extractions

## Impact Summary

### What Changes on Rollback

| Component | Before Rollback | After Rollback |
|-----------|----------------|----------------|
| .doc uploads | Accepted | Rejected |
| Text extraction | Active | Disabled |
| Search indexing | Includes .doc content | Existing only |
| Tika container | Running | Running (Option A) or Stopped (Option C) |

### What Does NOT Change on Rollback

- Existing documents remain in database
- Previously extracted text remains searchable
- Download of existing .doc files still works
- Other file formats unaffected
- No data loss

## Related Documentation

- [Configuration Reference](./configuration.md) - Environment variables
- [Operations Guide](./operations.md) - Monitoring and troubleshooting
- [Research](./research.md) - Technology decisions
- [Specification](./spec.md) - Feature requirements
