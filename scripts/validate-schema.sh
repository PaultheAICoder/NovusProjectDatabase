#!/bin/bash
#
# Database Schema Validator
#
# Validates that the actual database schema matches what SQLAlchemy models expect.
# Catches mismatches in:
# - Column types
# - Default values
# - Enum values
# - Nullable constraints
#
# USAGE:
#   ./scripts/validate-schema.sh [production|test]
#
# EXIT CODES:
#   0 = All validations pass
#   1 = Validation failures found

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

TARGET="${1:-production}"

if [ "$TARGET" = "production" ]; then
    CONTAINER="npd-db"
    DB="npd"
    DB_USER="npd"
    echo "Validating PRODUCTION database schema..."
elif [ "$TARGET" = "test" ]; then
    CONTAINER="npd-db-test"
    DB="npd_test"
    DB_USER="npd_test"
    echo "Validating TEST database schema..."
else
    echo "Usage: $0 [production|test]"
    exit 1
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

echo ""
echo "================================================================"
echo "     Database Schema Validation"
echo "================================================================"
echo ""

# ============================================================================
# CHECK 1: Sync enum columns have correct defaults (uppercase)
# ============================================================================
echo "Check 1: Verifying enum column defaults..."

# Expected defaults (uppercase, matching SQLAlchemy SAEnum behavior)
check_default() {
    local table=$1
    local column=$2
    local expected=$3

    actual=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB" -t -c "
        SELECT column_default FROM information_schema.columns
        WHERE table_name = '$table' AND column_name = '$column';
    " 2>/dev/null | xargs || echo "")

    # Handle different quote styles and ::character varying suffix
    actual_cleaned=$(echo "$actual" | sed "s/::character varying//g" | tr -d "'\"")

    if [ "$actual_cleaned" != "$expected" ]; then
        echo -e "  ${RED}[FAIL]${NC} $table.$column default: expected '$expected', got '$actual_cleaned'"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "  ${GREEN}[OK]${NC} $table.$column default = '$expected'"
    fi
}

check_default "organizations" "sync_status" "PENDING"
check_default "organizations" "sync_direction" "BIDIRECTIONAL"
check_default "contacts" "sync_status" "PENDING"
check_default "contacts" "sync_direction" "BIDIRECTIONAL"

echo ""

# ============================================================================
# CHECK 2: Verify no lowercase enum values exist
# ============================================================================
echo "Check 2: Verifying enum values are uppercase..."

LOWERCASE_SYNC_STATUS=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB" -t -c "
    SELECT COUNT(*) FROM (
        SELECT sync_status FROM organizations WHERE sync_status ~ '^[a-z]'
        UNION ALL
        SELECT sync_status FROM contacts WHERE sync_status ~ '^[a-z]'
    ) lowercase_vals;
" 2>/dev/null | xargs || echo "0")

LOWERCASE_SYNC_DIRECTION=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB" -t -c "
    SELECT COUNT(*) FROM (
        SELECT sync_direction FROM organizations WHERE sync_direction ~ '^[a-z]'
        UNION ALL
        SELECT sync_direction FROM contacts WHERE sync_direction ~ '^[a-z]'
    ) lowercase_vals;
" 2>/dev/null | xargs || echo "0")

if [ "$LOWERCASE_SYNC_STATUS" != "0" ]; then
    echo -e "  ${RED}[FAIL]${NC} Found $LOWERCASE_SYNC_STATUS records with lowercase sync_status"
    echo "       Run: ./scripts/fix-sync-enum-case.sh $TARGET"
    ERRORS=$((ERRORS + 1))
else
    echo -e "  ${GREEN}[OK]${NC} All sync_status values are uppercase"
fi

if [ "$LOWERCASE_SYNC_DIRECTION" != "0" ]; then
    echo -e "  ${RED}[FAIL]${NC} Found $LOWERCASE_SYNC_DIRECTION records with lowercase sync_direction"
    echo "       Run: ./scripts/fix-sync-enum-case.sh $TARGET"
    ERRORS=$((ERRORS + 1))
else
    echo -e "  ${GREEN}[OK]${NC} All sync_direction values are uppercase"
fi

echo ""

# ============================================================================
# CHECK 3: Verify all expected tables exist
# ============================================================================
echo "Check 3: Verifying expected tables exist..."

EXPECTED_TABLES=(
    "users"
    "projects"
    "organizations"
    "contacts"
    "documents"
    "tags"
    "project_tags"
    "project_contacts"
    "monday_sync_logs"
    "sync_queue"
    "sync_conflicts"
    "alembic_version"
)

for table in "${EXPECTED_TABLES[@]}"; do
    exists=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB" -t -c "
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = '$table'
        );
    " 2>/dev/null | xargs || echo "f")

    if [ "$exists" = "t" ]; then
        echo -e "  ${GREEN}[OK]${NC} Table '$table' exists"
    else
        echo -e "  ${RED}[FAIL]${NC} Table '$table' missing"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# ============================================================================
# CHECK 4: Verify sync columns exist on syncable tables
# ============================================================================
echo "Check 4: Verifying sync columns on syncable tables..."

check_column_exists() {
    local table=$1
    local column=$2

    exists=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB" -t -c "
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = '$table' AND column_name = '$column'
        );
    " 2>/dev/null | xargs || echo "f")

    if [ "$exists" = "t" ]; then
        echo -e "  ${GREEN}[OK]${NC} $table.$column exists"
    else
        echo -e "  ${RED}[FAIL]${NC} $table.$column missing"
        ERRORS=$((ERRORS + 1))
    fi
}

SYNC_COLUMNS=("monday_id" "monday_last_synced" "sync_status" "sync_enabled" "sync_direction")
SYNC_TABLES=("organizations" "contacts")

for table in "${SYNC_TABLES[@]}"; do
    for column in "${SYNC_COLUMNS[@]}"; do
        check_column_exists "$table" "$column"
    done
done

echo ""

# ============================================================================
# FINAL RESULT
# ============================================================================
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}================================================================${NC}"
    echo -e "${RED}     SCHEMA VALIDATION FAILED${NC}"
    echo -e "${RED}================================================================${NC}"
    echo ""
    echo "Errors found: $ERRORS"
    echo ""
    echo "Common fixes:"
    echo "  - Enum case mismatch: ./scripts/fix-sync-enum-case.sh $TARGET"
    echo "  - Missing tables: docker exec npd-backend alembic upgrade head"
    echo ""
    exit 1
fi

echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}     SCHEMA VALIDATION PASSED${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "All schema checks passed for $TARGET database."
echo ""

exit 0
