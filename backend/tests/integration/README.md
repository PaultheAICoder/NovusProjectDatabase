# Integration Tests

## Overview

This directory contains integration tests that require external services. These tests are automatically skipped if the required services are not configured.

---

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

---

# Tika Integration Tests (DOC File Extraction)

## Purpose

These tests verify Apache Tika integration for extracting text from legacy .doc files (Word 97-2003 format). The tests cover:

- Tika server connectivity and health checks
- .doc file text extraction
- Error handling for corrupted files
- Timeout handling

## Prerequisites

1. Apache Tika server running (via Docker or standalone)
2. Environment variables configured

## Required Environment Variables

```bash
export TIKA_ENABLED=true
export TIKA_URL=http://localhost:6706  # Or your Tika server URL
export TIKA_TIMEOUT=60  # Timeout in seconds
```

## Starting the Tika Container

Using Docker Compose (recommended):

```bash
cd /home/pbrown/Novus-db
docker compose up tika -d
```

Or standalone Docker:

```bash
docker run -d -p 9998:9998 apache/tika:latest
```

## Running Tika Integration Tests

```bash
# Set environment
export TIKA_ENABLED=true
export TIKA_URL=http://localhost:6706

# Run tests
pytest tests/integration/test_doc_extraction.py -v

# Run with verbose output
pytest tests/integration/test_doc_extraction.py -v -s
```

## Test Categories

### TestTikaConnection
- Health check verification
- Basic extraction response validation

### TestDocExtraction
- Minimal OLE document extraction
- Corrupted file handling
- Empty file handling
- MIME type mismatch handling

### TestDocExtractionTimeout
- Timeout behavior testing (marked as `slow`)

### TestDocUploadFlow
- MIME type acceptance verification
- File type mapping
- Full processor flow with mock

### TestTikaClientConfiguration
- Configuration validation

## Skipping Tests

```bash
# Skip all integration tests
pytest tests/ -m "not integration"

# Skip slow tests (includes timeout tests)
pytest tests/integration/ -m "not slow"

# Run only Tika tests
pytest tests/integration/test_doc_extraction.py -v
```

## Test Fixtures

The tests use fixtures from `tests/fixtures/doc_fixtures.py`:

- `get_minimal_ole_doc()` - Minimal valid OLE header for MIME detection
- `get_corrupted_doc()` - Truncated/invalid OLE data
- `get_text_file_claiming_doc_mime()` - Plain text (MIME mismatch testing)
- `get_empty_file()` - Empty content
- `get_random_binary()` - Random binary data

Note: These are minimal fixtures for testing error handling and MIME detection. For full text extraction tests with real .doc content, you need actual Word 97-2003 documents.

## Troubleshooting

### Tests Skip Unexpectedly

Check that Tika is configured:

```bash
python -c "from app.config import get_settings; print(get_settings().is_tika_configured)"
```

### Connection Errors

Verify Tika container is running:

```bash
docker ps | grep tika
curl http://localhost:6706/tika  # Should return "Hello from Tika..."
```

### Timeout Issues

The default timeout is 60 seconds. For very large files, you may need to increase `TIKA_TIMEOUT`.

---

# Document ACL Integration Tests

## Purpose

These tests verify document-level access control integration with the permission system.

## Running

```bash
pytest tests/integration/test_document_acl.py -v
```
