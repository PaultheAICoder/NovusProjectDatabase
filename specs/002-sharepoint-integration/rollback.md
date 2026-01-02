# SharePoint Integration Rollback Procedure

This document provides procedures for rolling back SharePoint integration if issues are encountered after deployment.

## When to Rollback

Consider initiating a rollback when:

### Critical Issues (Immediate Rollback)

- **Authentication failures**: Unable to obtain tokens, all document operations failing
- **Data corruption**: Documents corrupted during upload/download
- **Complete service outage**: SharePoint unreachable with no ETA for resolution
- **Security incident**: Suspected unauthorized access or data breach

### Performance Issues (Evaluate First)

- **Consistent high latency**: Document operations taking >10 seconds regularly
- **Frequent rate limiting**: Repeated HTTP 429 errors impacting users
- **Intermittent failures**: >5% of document operations failing

### Operational Issues (Plan Rollback)

- **Upcoming SharePoint maintenance**: Extended downtime announced
- **Cost concerns**: Unexpected API usage or storage costs
- **Compliance requirements**: Need to move data back on-premises

## Rollback Decision Matrix

| Issue Severity | User Impact | Recommended Action |
|----------------|-------------|-------------------|
| Critical | All users affected | Immediate Quick Rollback (Option A) |
| High | Many users affected | Quick Rollback within 1 hour |
| Medium | Some users affected | Evaluate, plan rollback if no fix |
| Low | Few users affected | Monitor, fix if possible |

## Rollback Options

### Option A: Quick Rollback (Disable SharePoint)

**Time**: 5 minutes
**Impact**: New uploads go to local storage; existing SharePoint files remain accessible (read-only)
**Use when**: Immediate action needed, temporary solution

#### Steps

1. **Update environment configuration**:
   ```bash
   # In your .env file or environment
   SHAREPOINT_ENABLED=false
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
   print(f'SharePoint enabled: {s.sharepoint_enabled}')
   print(f'Expected: False')
   "
   ```

4. **Test new upload**:
   - Upload a test document via the UI
   - Verify it's saved to local `uploads/` directory

#### What Happens

- New document uploads go to local filesystem
- Existing documents on SharePoint remain accessible (hybrid mode)
- Database still references SharePoint paths for previously migrated documents

#### Limitations

- Does not migrate files back to local storage
- Hybrid state may cause confusion
- Some documents on SharePoint, some local

### Option B: Hybrid Mode (Monitor and Evaluate)

**Time**: 5 minutes
**Impact**: Maintains current state while investigating
**Use when**: Issue is intermittent, need time to diagnose

#### Steps

1. **Enable enhanced logging**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **Monitor for specific errors**:
   ```bash
   # Watch logs for SharePoint errors
   docker compose logs -f backend | grep -E "sharepoint|graph"
   ```

3. **Collect metrics**:
   - Document operation success/failure rates
   - Average latency
   - Error messages

4. **Make informed decision**:
   - If issues persist: Proceed to Option A or C
   - If issues resolve: Continue monitoring

### Option C: Full Rollback (Migrate Back to Local)

**Time**: Varies (depends on document count)
**Impact**: All documents returned to local storage
**Use when**: Long-term decision to abandon SharePoint

#### Prerequisites

- Sufficient local storage space
- Maintenance window scheduled
- User communication sent

#### Steps

1. **Disable SharePoint for new uploads first** (Option A steps)

2. **Export document list**:
   ```bash
   cd backend
   python -c "
   import asyncio
   from sqlalchemy import select
   from app.database import async_session_maker
   from app.models import Document

   async def export():
       async with async_session_maker() as db:
           result = await db.execute(
               select(Document.id, Document.file_path, Document.project_id)
               .where(Document.file_path.like('/NPD/%'))
           )
           docs = result.all()
           for doc in docs:
               print(f'{doc.id},{doc.file_path},{doc.project_id}')

   asyncio.run(export())
   " > sharepoint_documents.csv
   ```

3. **Download documents from SharePoint**:

   This requires a custom script (not currently implemented):
   ```bash
   # Conceptual - needs implementation
   python -m app.scripts.migrate_from_sharepoint --dry-run
   python -m app.scripts.migrate_from_sharepoint
   ```

   **Alternative manual approach**:
   - Use SharePoint UI to download all files
   - Use OneDrive sync client to sync folder locally
   - Copy files to appropriate local paths

4. **Update database records**:
   ```sql
   -- Update paths from SharePoint to local
   UPDATE documents
   SET file_path = REPLACE(file_path, '/NPD/projects/', 'uploads/projects/')
   WHERE file_path LIKE '/NPD/%';
   ```

5. **Verify migration**:
   - Spot-check document access
   - Verify file counts match

6. **Clean up SharePoint** (optional, after verification):
   - Remove files from SharePoint if no longer needed
   - Remove app permissions if not needed

## Post-Rollback Verification

### Verify Local Storage

```bash
# Check documents are being saved locally
ls -la uploads/projects/

# Check recent uploads
find uploads/ -type f -mmin -30
```

### Verify Application Functionality

1. **Upload test**: Upload a new document, verify it saves locally
2. **Download test**: Download an existing document
3. **Search test**: Search for a document, verify it's found

### Monitor for Issues

```bash
# Watch for errors in logs
docker compose logs -f backend | grep -E "error|ERROR|exception"
```

## Communication Templates

### Initiating Rollback

```
Subject: URGENT: Document Storage Rollback Initiated

We are experiencing issues with our document storage system and are
initiating a rollback to the previous configuration.

Current Status:
- Document uploads may be temporarily unavailable
- Existing documents remain accessible
- We are working to restore full functionality

We will provide an update within [TIMEFRAME].

Please contact [SUPPORT CONTACT] for urgent document needs.
```

### Rollback Complete

```
Subject: Document Storage Rollback Complete

The document storage rollback has been completed successfully.

Status:
- All document features are now available
- New documents will be saved to [local/alternative] storage
- No action required from users

If you experience any issues, please contact [SUPPORT CONTACT].
```

### Post-Mortem Communication

```
Subject: Document Storage Issue - Post-Mortem Summary

Summary:
On [DATE], we experienced issues with our SharePoint document storage
integration. A rollback was initiated at [TIME] and completed at [TIME].

Impact:
- [X] users were affected
- Document uploads were unavailable for [DURATION]
- No data loss occurred

Root Cause:
[DESCRIPTION]

Actions Taken:
1. [ACTION 1]
2. [ACTION 2]

Preventive Measures:
1. [MEASURE 1]
2. [MEASURE 2]

Next Steps:
[DESCRIPTION OF PATH FORWARD]
```

## Prevention and Preparation

### Before Go-Live

- [ ] Test rollback procedure in staging environment
- [ ] Document current state (document counts, storage usage)
- [ ] Verify local storage is available and accessible
- [ ] Have rollback commands ready

### Ongoing

- [ ] Monitor SharePoint health dashboard
- [ ] Track client secret expiration dates
- [ ] Regular backup verification
- [ ] Keep rollback documentation updated

## Recovery After Rollback

If you need to re-enable SharePoint after a rollback:

1. **Resolve root cause** of the original issue
2. **Test fix** in non-production environment
3. **Plan migration window**
4. **Follow migration runbook** ([migration-runbook.md](./migration-runbook.md))
5. **Monitor closely** for recurrence

## Related Documentation

- [Azure AD Setup](./azure-setup.md) - App registration and permissions
- [SharePoint Setup](./sharepoint-setup.md) - Site and library configuration
- [Configuration Reference](./configuration.md) - Environment variables
- [Migration Runbook](./migration-runbook.md) - Production migration steps
