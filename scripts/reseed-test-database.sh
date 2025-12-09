#!/bin/bash
# scripts/reseed-test-database.sh
# Restores test database from most recent production backup
#
# PURPOSE: Ensures test database has current "good" data from production
# before each orchestrate3 cycle
#
# SAFETY: Only targets test database (npd_test on port 6712)
#         NEVER touches production database
#
# CATASTROPHIC FAILURE HANDLING:
#   If the test database has NO TABLES during a normal workflow, this indicates
#   something is seriously wrong (unexpected wipe, wrong database, etc.).
#   The script will HALT and optionally post a comment to the GitHub issue.
#   Use --fresh-start to explicitly allow empty database (first setup or intentional wipe).
#
# USAGE:
#   ./scripts/reseed-test-database.sh                    # Use latest backup
#   ./scripts/reseed-test-database.sh /path/to/backup    # Use specific backup
#   ./scripts/reseed-test-database.sh --force            # Force restore even if populated
#   ./scripts/reseed-test-database.sh --fresh-start      # Allow empty database (first setup)
#   ./scripts/reseed-test-database.sh --issue 123        # Post to GH issue on catastrophic failure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/.backups"

# HARDCODED TEST DATABASE CONFIGURATION - NEVER CHANGE
TEST_DB_USER="npd_test"
TEST_DB_PASSWORD="npd_test_2025"
TEST_DB_NAME="npd_test"
TEST_DB_CONTAINER="npd-db-test"
TEST_DB_PORT="6712"
TEST_WEB_PORT="6710"

# Parse arguments
FORCE_RESTORE=false
FRESH_START=false
ISSUE_NUMBER=""
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force|-f)
            FORCE_RESTORE=true
            shift
            ;;
        --fresh-start)
            FRESH_START=true
            shift
            ;;
        --issue)
            ISSUE_NUMBER="$2"
            shift 2
            ;;
        *)
            if [ -f "$1" ]; then
                BACKUP_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}           NPD Test Database Reseed - Safety Verification${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Verify test container is running
if ! docker ps | grep -q "$TEST_DB_CONTAINER"; then
    echo -e "${RED}ERROR: Test database container not running${NC}"
    echo "  Start with: docker compose -f docker-compose.test.yml up -d"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Test database container is running"

# Find backup file
if [ -z "$BACKUP_FILE" ]; then
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/npd_backup_*.dump 2>/dev/null | head -1)
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}ERROR: No backup file found${NC}"
    echo "  Create backup first: ./scripts/backup-production.sh"
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Backup file: $(basename "$BACKUP_FILE")"
echo ""

# ============================================================================
# CATASTROPHIC FAILURE CHECK: Verify tables exist
# ============================================================================
# In a normal orchestrate3 workflow, the test database should ALREADY have tables
# from previous cycles. An empty database (no tables) is UNEXPECTED and indicates:
#   - Unexpected database wipe
#   - Configuration pointing to wrong database
#   - Container volume issue
#   - Something catastrophically wrong
#
# Use --fresh-start to explicitly allow empty database (first setup or intentional wipe)
# ============================================================================

TABLE_COUNT=$(docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d "$TEST_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | xargs || echo "0")

if [ "$TABLE_COUNT" = "0" ]; then
    if [ "$FRESH_START" = "true" ]; then
        echo -e "${YELLOW}WARNING: Test database has NO TABLES${NC}"
        echo "  --fresh-start flag provided, proceeding with restore..."
        echo ""
    else
        echo ""
        echo -e "${RED}================================================================${NC}"
        echo -e "${RED}        CATASTROPHIC FAILURE: Test database has NO TABLES${NC}"
        echo -e "${RED}================================================================${NC}"
        echo ""
        echo "This should NOT happen during a normal orchestrate3 workflow cycle."
        echo "The test database should already have tables from previous cycles."
        echo ""
        echo "Possible causes:"
        echo "  - Database was unexpectedly wiped"
        echo "  - Configuration pointing to wrong database"
        echo "  - Container volume was deleted"
        echo "  - First-time setup (use --fresh-start if intentional)"
        echo ""
        echo "To proceed intentionally with an empty database:"
        echo "  ./scripts/reseed-test-database.sh --fresh-start"
        echo ""

        # Post to GitHub issue if available
        if [ -n "$ISSUE_NUMBER" ]; then
            echo "Posting failure notice to GitHub issue #$ISSUE_NUMBER..."
            gh issue comment "$ISSUE_NUMBER" --body "## WORKFLOW HALTED: Test Database Catastrophic Failure

The reseed script found **NO TABLES** in the test database. This is unexpected during a normal workflow cycle.

**Action Required**: Investigate why the test database is empty before continuing.

- If this is intentional (first setup or refresh), re-run with \`--fresh-start\` flag
- If unexpected, check container volumes and database configuration

Script: \`scripts/reseed-test-database.sh\`
Container: \`$TEST_DB_CONTAINER\`
Database: \`$TEST_DB_NAME\`" 2>/dev/null || echo "  (Could not post to GitHub issue)"
        fi

        echo -e "${RED}WORKFLOW HALTED - Do not proceed until investigated${NC}"
        exit 99
    fi
else
    echo -e "${GREEN}[OK]${NC} Test database has $TABLE_COUNT tables"
fi

# Check current test database status
CURRENT_COUNT=$(docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d "$TEST_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM projects;" 2>/dev/null | xargs || echo "0")

THRESHOLD=5
echo "Current test database: $CURRENT_COUNT projects"

SKIP_RESTORE=false
if [ "$FORCE_RESTORE" = "true" ]; then
    echo -e "${YELLOW}Force restore requested${NC}"
elif [ "$CURRENT_COUNT" -ge "$THRESHOLD" ]; then
    echo -e "${GREEN}Database already populated - skipping restore${NC}"
    echo "  Use --force to override"
    SKIP_RESTORE=true
else
    echo "Database needs restoration"
fi
echo ""

if [ "$SKIP_RESTORE" = "false" ]; then
    echo "Restoring test database from backup..."

    # Terminate existing connections
    docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TEST_DB_NAME' AND pid <> pg_backend_pid();" \
        >/dev/null 2>&1 || true

    # Drop and recreate database
    docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $TEST_DB_NAME;" >/dev/null 2>&1
    docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d postgres -c "CREATE DATABASE $TEST_DB_NAME OWNER $TEST_DB_USER;" >/dev/null 2>&1

    # Copy backup file to container and restore
    docker cp "$BACKUP_FILE" "$TEST_DB_CONTAINER":/tmp/restore.dump
    docker exec "$TEST_DB_CONTAINER" pg_restore -U "$TEST_DB_USER" -d "$TEST_DB_NAME" \
        --no-owner --no-privileges /tmp/restore.dump 2>/dev/null || true
    docker exec "$TEST_DB_CONTAINER" rm -f /tmp/restore.dump

    echo -e "${GREEN}[OK]${NC} Restore complete"
fi

# Verify final state
FINAL_PROJECT_COUNT=$(docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d "$TEST_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM projects;" 2>/dev/null | xargs || echo "0")
FINAL_DOCUMENT_COUNT=$(docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d "$TEST_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs || echo "0")
FINAL_ORG_COUNT=$(docker exec "$TEST_DB_CONTAINER" psql -U "$TEST_DB_USER" -d "$TEST_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM organizations;" 2>/dev/null | xargs || echo "0")

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}NPD Test Database Ready${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "  Database: $TEST_DB_NAME (port $TEST_DB_PORT)"
echo "  Projects: $FINAL_PROJECT_COUNT"
echo "  Documents: $FINAL_DOCUMENT_COUNT"
echo "  Organizations: $FINAL_ORG_COUNT"
echo "  Access: http://localhost:$TEST_WEB_PORT"
echo ""
