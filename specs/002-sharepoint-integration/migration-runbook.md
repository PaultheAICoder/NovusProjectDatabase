# SharePoint Migration Runbook

This runbook provides step-by-step instructions for migrating NPD documents from local filesystem storage to SharePoint Online.

## Overview

The migration process moves all existing documents from the local `uploads/` directory to SharePoint while updating database records with new SharePoint paths. The process is designed to be:

- **Resumable**: If interrupted, re-running continues from where it left off
- **Safe**: Dry-run mode previews changes without modifications
- **Batched**: Documents are processed in configurable batches
- **Monitored**: Progress is reported in real-time

## Pre-Migration Checklist

Complete all items before proceeding with migration:

### Azure AD & SharePoint Setup
- [ ] Azure AD app registration completed with SharePoint permissions ([azure-setup.md](./azure-setup.md))
- [ ] Admin consent granted for `Sites.ReadWrite.All` permission
- [ ] SharePoint site created and accessible ([sharepoint-setup.md](./sharepoint-setup.md))
- [ ] Document library created with proper name
- [ ] Drive ID captured from Graph API
- [ ] Base folder structure (`/NPD/projects`) created
- [ ] App registration added to SharePoint site permissions

### Environment Configuration
- [ ] `SHAREPOINT_ENABLED=true` configured
- [ ] `SHAREPOINT_SITE_URL` set to correct site URL
- [ ] `SHAREPOINT_DRIVE_ID` set to correct drive ID
- [ ] Credentials configured (either SharePoint-specific or Azure AD fallback)
- [ ] Configuration validated (see verification section below)

### Infrastructure
- [ ] Backup of `uploads/` directory taken
- [ ] Database backup taken
- [ ] Sufficient SharePoint storage quota available
- [ ] Network connectivity to SharePoint verified
- [ ] Maintenance window scheduled and communicated

### Go/No-Go Decision
- [ ] All checklist items above completed
- [ ] Dry run executed successfully
- [ ] Rollback plan reviewed

## Pre-Migration Verification

### 1. Verify Configuration

```bash
cd backend
source .venv/bin/activate

# Check configuration is loaded correctly
python -c "
from app.config import get_settings
s = get_settings()
print('=== SharePoint Configuration ===')
print(f'Enabled: {s.sharepoint_enabled}')
print(f'Site URL: {s.sharepoint_site_url}')
print(f'Drive ID: {s.sharepoint_drive_id[:20]}...')
print(f'Base Folder: {s.sharepoint_base_folder}')
print(f'Fully Configured: {s.is_sharepoint_configured}')
if not s.is_sharepoint_configured:
    print('ERROR: SharePoint is not fully configured!')
    exit(1)
print('Configuration OK')
"
```

### 2. Test SharePoint Connectivity

```bash
# This will attempt to connect and list folder contents
python -c "
import asyncio
from app.config import get_settings
from app.core.sharepoint import SharePointStorageAdapter

async def test_connection():
    settings = get_settings()
    adapter = SharePointStorageAdapter(
        drive_id=settings.sharepoint_drive_id,
        base_folder=settings.sharepoint_base_folder,
    )
    try:
        # Test by checking if base folder exists
        exists = await adapter.exists('/')
        print(f'Connection successful! Base folder exists: {exists}')
    except Exception as e:
        print(f'Connection failed: {e}')
        exit(1)
    finally:
        await adapter.close()

asyncio.run(test_connection())
"
```

### 3. Count Documents to Migrate

```bash
# Check how many documents will be migrated
python -c "
import asyncio
from app.database import async_session_maker
from app.services.migration_service import MigrationService

async def count_docs():
    async with async_session_maker() as db:
        service = MigrationService(db=db, local_storage=None, sharepoint_storage=None)
        docs = await service.get_migratable_documents()
        print(f'Documents to migrate: {len(docs)}')

asyncio.run(count_docs())
"
```

## Phase 1: Dry Run

A dry run previews the migration without making any changes.

### Execute Dry Run

```bash
cd backend
source .venv/bin/activate

# Run migration in dry-run mode
python -m app.scripts.migrate_to_sharepoint --dry-run
```

### Expected Output

```
Found 150 documents to migrate
DRY RUN MODE - No changes will be made
Progress: 150/150 (100.0%) - Success: 150, Failed: 0, Skipped: 0

=== Migration Summary ===
Total documents: 150
Successfully migrated: 150
Failed: 0
Skipped: 0
```

### Analyze Dry Run Results

- **Success**: Documents that would be migrated successfully
- **Failed**: Documents with errors (check error details)
- **Skipped**: Documents already migrated or with missing files

### Go/No-Go Decision

| Condition | Decision |
|-----------|----------|
| 100% success, 0 failed | **GO** - Proceed to Phase 2 |
| <5% failed, errors understood | **GO** with caution - Proceed, plan to address failures |
| >5% failed | **NO-GO** - Investigate and resolve issues |
| Configuration errors | **NO-GO** - Fix configuration first |

## Phase 2: Production Migration

### 2.1 Start Migration

```bash
cd backend
source .venv/bin/activate

# Start migration with recommended batch size
python -m app.scripts.migrate_to_sharepoint --batch-size 50
```

### 2.2 Batch Size Recommendations

| Document Count | Recommended Batch Size |
|----------------|------------------------|
| < 100 | 20 |
| 100 - 500 | 50 |
| 500 - 1000 | 50-100 |
| > 1000 | 100 |

Larger batch sizes are faster but use more memory and risk losing more progress if interrupted.

### 2.3 Monitor Progress

The script outputs real-time progress:
```
Progress: 75/150 (50.0%) - Success: 73, Failed: 2, Skipped: 0
```

### 2.4 Handle Interruption

If migration is interrupted (Ctrl+C, network failure, etc.):

1. The current batch's progress is lost, but committed batches are preserved
2. Simply re-run the migration command - it will resume from last committed state:
   ```bash
   python -m app.scripts.migrate_to_sharepoint --batch-size 50
   ```

### 2.5 Expected Duration

| Document Count | Estimated Time |
|----------------|----------------|
| 100 | 5-10 minutes |
| 500 | 20-40 minutes |
| 1000 | 45-90 minutes |
| 5000 | 4-8 hours |

Times vary based on document sizes and network conditions.

## Phase 3: Post-Migration Verification

### 3.1 Verify Document Counts

```bash
# Count documents in database with SharePoint paths
python -c "
import asyncio
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import Document

async def count():
    async with async_session_maker() as db:
        # Total documents
        total = await db.scalar(select(func.count(Document.id)))
        # Documents on SharePoint
        sharepoint = await db.scalar(
            select(func.count(Document.id))
            .where(Document.file_path.like('/NPD/%'))
        )
        # Documents still local
        local = await db.scalar(
            select(func.count(Document.id))
            .where(~Document.file_path.like('/NPD/%'))
        )
        print(f'Total documents: {total}')
        print(f'On SharePoint: {sharepoint}')
        print(f'Still local: {local}')

asyncio.run(count())
"
```

### 3.2 Spot-Check Document Access

Test that documents are accessible via the UI:

1. Log in to NPD application
2. Navigate to a project with documents
3. Click on a document to download
4. Verify the document opens correctly

### 3.3 Test Upload Functionality

1. Navigate to a project
2. Upload a new test document
3. Verify it appears in the document list
4. Download the test document to verify it saved correctly

### 3.4 Verify SharePoint Contents

Use Graph Explorer to verify files exist in SharePoint:
```
GET https://graph.microsoft.com/v1.0/drives/{drive-id}/root:/NPD/projects:/children
```

## Phase 4: Cleanup (Optional)

After successful verification, you may clean up local storage.

### 4.1 Wait Period

**Recommended**: Wait 1-2 weeks after migration before cleanup to ensure no issues are discovered.

### 4.2 Archive Local Files

Rather than deleting, archive the local uploads directory:

```bash
# Create dated archive
tar -czvf uploads-backup-$(date +%Y%m%d).tar.gz uploads/

# Move archive to safe location
mv uploads-backup-*.tar.gz /backup/location/

# Verify archive is readable
tar -tzvf /backup/location/uploads-backup-*.tar.gz | head
```

### 4.3 Clear Local Storage (Optional)

Only after verifying the archive:

```bash
# Remove migrated files (keep directory structure)
rm -rf uploads/*

# Or remove entire directory if not needed
rm -rf uploads/
```

## Troubleshooting

### Common Errors

#### "Authentication failed" or "Token acquisition failed"

**Cause**: Invalid or expired credentials

**Solution**:
1. Verify client ID and secret are correct
2. Check if client secret has expired in Azure AD
3. Ensure admin consent has been granted
4. Verify tenant ID is correct

#### "Drive not found" or "404 Not Found"

**Cause**: Invalid drive ID or site URL

**Solution**:
1. Re-verify drive ID via Graph Explorer
2. Check site URL format (no trailing slash)
3. Ensure site and library still exist

#### "Access denied" or "403 Forbidden"

**Cause**: Insufficient permissions

**Solution**:
1. Verify app has `Sites.ReadWrite.All` permission
2. Check that admin consent was granted
3. Verify app was added to SharePoint site permissions

#### "File not found" on local storage

**Cause**: File exists in database but not on disk

**Solution**:
1. These files are marked as "skipped" during migration
2. Investigate why file is missing (accidental deletion, backup issue)
3. May need to remove orphaned database records

#### "Rate limited" or "429 Too Many Requests"

**Cause**: Too many API requests to SharePoint

**Solution**:
1. Reduce batch size
2. Add delays between batches
3. Wait and retry

### Resume After Failure

If migration fails partway through:

1. Check error message and resolve root cause
2. Re-run migration command - it automatically resumes:
   ```bash
   python -m app.scripts.migrate_to_sharepoint --batch-size 50
   ```

### Partial Rollback

If you need to rollback specific documents to local storage:

1. This is not currently automated
2. Manual steps:
   - Download document from SharePoint
   - Save to local `uploads/` directory with original path
   - Update database record to point to local path
3. Consider implementing reverse migration if needed frequently

### Full Rollback

See [rollback.md](./rollback.md) for complete rollback procedures.

## Post-Migration Monitoring

### Week 1

- Monitor application logs for SharePoint errors
- Check user feedback for document access issues
- Verify upload functionality works for new documents

### Week 2-4

- Review SharePoint storage usage
- Monitor for any performance issues
- Gather user feedback

### Ongoing

- Monitor client secret expiration dates
- Track SharePoint API usage and costs (if applicable)
- Regular backups of database

## Communication Templates

### Pre-Migration Notice

```
Subject: Scheduled Maintenance: Document Storage Migration

NPD will undergo scheduled maintenance on [DATE] from [TIME] to [TIME].

During this time:
- Document uploads will be temporarily unavailable
- Existing documents will remain accessible for viewing

This maintenance will improve document storage reliability and performance.

No action is required from users.
```

### Post-Migration Notice

```
Subject: Document Storage Migration Complete

The scheduled maintenance for NPD has been completed successfully.

All features are now available. If you experience any issues accessing
documents, please contact [SUPPORT CONTACT].

Thank you for your patience.
```

## Related Documentation

- [Azure AD Setup](./azure-setup.md) - App registration and permissions
- [SharePoint Setup](./sharepoint-setup.md) - Site and library configuration
- [Configuration Reference](./configuration.md) - Environment variables
- [Rollback Procedure](./rollback.md) - How to disable SharePoint if needed
