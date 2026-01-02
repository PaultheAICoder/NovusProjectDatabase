# SharePoint Integration Tests

## Purpose

These tests verify SharePoint functionality against a real SharePoint Online environment. They test the complete file lifecycle including upload, download, and delete operations with files of various sizes.

## Prerequisites

1. Azure AD app with SharePoint permissions (Sites.ReadWrite.All)
2. SharePoint site with document library
3. Environment variables configured

## Required Environment Variables

```bash
export SHAREPOINT_ENABLED=true
export SHAREPOINT_SITE_URL="https://your-tenant.sharepoint.com/sites/NPD"
export SHAREPOINT_DRIVE_ID="your-drive-id"
export SHAREPOINT_CLIENT_ID="your-client-id"  # Or use AZURE_AD_CLIENT_ID
export SHAREPOINT_CLIENT_SECRET="your-secret"  # Or use AZURE_AD_CLIENT_SECRET
```

You can optionally set `SHAREPOINT_TENANT_ID` if different from `AZURE_AD_TENANT_ID`.

## Test Categories

### Core Operations
- **TestUploadCycle**: Basic file upload operations
- **TestDownloadCycle**: File download and content verification
- **TestDeleteCycle**: File deletion and cleanup

### Large File Handling
- **TestLargeFileHandling**: Tests for files > 4MB that use chunked upload
  - 5MB file (just above simple upload limit)
  - 10MB file (medium chunked upload)
  - 50MB file (near max file size limit) - marked as `slow`

### Concurrent Operations
- **TestConcurrentOperations**: Parallel upload/download/delete operations

### Migration
- **TestMigrationIntegration**: Local-to-SharePoint migration service testing

### Error Handling
- **TestErrorScenarios**: Error conditions and edge cases

### File Types
- **TestFileTypes**: Different file formats (PDF, DOCX, special characters)

## Running Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run only SharePoint integration tests
pytest tests/integration/test_sharepoint_integration.py -v

# Skip slow tests (50MB uploads)
pytest tests/integration/ -v -m "not slow"

# Run all tests EXCEPT integration
pytest tests/ -m "not integration"

# Run integration tests with coverage
pytest tests/integration/ -v --cov=app.core.sharepoint
```

## CI Configuration

Integration tests are automatically skipped if SharePoint is not configured. The skip condition checks:

```python
not get_settings().is_sharepoint_configured
```

This returns `True` when:
- `SHAREPOINT_ENABLED=true`
- `SHAREPOINT_SITE_URL` is set
- `SHAREPOINT_DRIVE_ID` is set
- Either `SHAREPOINT_CLIENT_ID` or `AZURE_AD_CLIENT_ID` is set
- Either `SHAREPOINT_CLIENT_SECRET` or `AZURE_AD_CLIENT_SECRET` is set

To run in CI, add the required secrets to your CI environment.

## Test Cleanup

All tests clean up after themselves by deleting uploaded files. If a test fails mid-execution, orphaned files may remain in the `/NPD/integration-tests/` folder on SharePoint.

## Test Isolation

Each test uses unique UUIDs for:
- Project IDs (folder names)
- File names

This ensures tests don't interfere with each other even when running in parallel.

## Timeout Considerations

Large file tests (10MB, 50MB) may take 30-60 seconds to complete depending on network conditions. These are marked with `@pytest.mark.slow` for optional filtering.

## Troubleshooting

### Tests Skip Unexpectedly
Check that all required environment variables are set:
```bash
python -c "from app.config import get_settings; print(get_settings().is_sharepoint_configured)"
```

### Authentication Errors
Verify Azure AD app permissions include:
- `Sites.ReadWrite.All` (Application permission)
- Or appropriate delegated permissions

### Rate Limiting
If you see 429 errors, SharePoint may be throttling requests. Wait a few minutes before retrying.
