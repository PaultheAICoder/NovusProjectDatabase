#!/bin/bash
#
# Fix sync enum case mismatch
#
# This script fixes a data issue where sync_status and sync_direction columns
# have lowercase values (e.g., 'pending') but SQLAlchemy expects uppercase
# enum member names (e.g., 'PENDING').
#
# Root cause: Migration 019_add_sync_tracking.py originally used lowercase
# server_default values, but SQLAlchemy SAEnum(native_enum=False) expects
# uppercase enum member names by default.
#
# Usage:
#   ./scripts/fix-sync-enum-case.sh [production|test]
#
# Default: production database on port 6702

set -e

TARGET="${1:-production}"

if [ "$TARGET" = "production" ]; then
    CONTAINER="npd-db"
    DB="npd"
    echo "Fixing PRODUCTION database..."
elif [ "$TARGET" = "test" ]; then
    CONTAINER="npd-db-test"
    DB="npd_test"
    echo "Fixing TEST database..."
else
    echo "Usage: $0 [production|test]"
    exit 1
fi

echo "Target: $CONTAINER / $DB"
echo ""

# Check current values
echo "Current sync_status values in organizations:"
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "SELECT DISTINCT sync_status FROM organizations;" 2>/dev/null || echo "(table may not exist)"

echo ""
echo "Current sync_status values in contacts:"
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "SELECT DISTINCT sync_status FROM contacts;" 2>/dev/null || echo "(table may not exist)"

echo ""
echo "Applying fixes..."

# Fix sync_status values (lowercase -> uppercase)
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "
UPDATE organizations SET sync_status = 'PENDING' WHERE sync_status = 'pending';
UPDATE organizations SET sync_status = 'SYNCED' WHERE sync_status = 'synced';
UPDATE organizations SET sync_status = 'CONFLICT' WHERE sync_status = 'conflict';
UPDATE organizations SET sync_status = 'DISABLED' WHERE sync_status = 'disabled';

UPDATE contacts SET sync_status = 'PENDING' WHERE sync_status = 'pending';
UPDATE contacts SET sync_status = 'SYNCED' WHERE sync_status = 'synced';
UPDATE contacts SET sync_status = 'CONFLICT' WHERE sync_status = 'conflict';
UPDATE contacts SET sync_status = 'DISABLED' WHERE sync_status = 'disabled';
"

# Fix sync_direction values (lowercase -> uppercase)
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "
UPDATE organizations SET sync_direction = 'BIDIRECTIONAL' WHERE sync_direction = 'bidirectional';
UPDATE organizations SET sync_direction = 'NPD_TO_MONDAY' WHERE sync_direction = 'npd_to_monday';
UPDATE organizations SET sync_direction = 'MONDAY_TO_NPD' WHERE sync_direction = 'monday_to_npd';
UPDATE organizations SET sync_direction = 'NONE' WHERE sync_direction = 'none';

UPDATE contacts SET sync_direction = 'BIDIRECTIONAL' WHERE sync_direction = 'bidirectional';
UPDATE contacts SET sync_direction = 'NPD_TO_MONDAY' WHERE sync_direction = 'npd_to_monday';
UPDATE contacts SET sync_direction = 'MONDAY_TO_NPD' WHERE sync_direction = 'monday_to_npd';
UPDATE contacts SET sync_direction = 'NONE' WHERE sync_direction = 'none';
"

# Update default values
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "
ALTER TABLE organizations ALTER COLUMN sync_status SET DEFAULT 'PENDING';
ALTER TABLE organizations ALTER COLUMN sync_direction SET DEFAULT 'BIDIRECTIONAL';
ALTER TABLE contacts ALTER COLUMN sync_status SET DEFAULT 'PENDING';
ALTER TABLE contacts ALTER COLUMN sync_direction SET DEFAULT 'BIDIRECTIONAL';
"

echo ""
echo "Fix complete. Verifying..."
echo ""
echo "Organizations sync_status values:"
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "SELECT DISTINCT sync_status, sync_direction FROM organizations;"
echo ""
echo "Contacts sync_status values:"
docker exec "$CONTAINER" psql -U npd -d "$DB" -c "SELECT DISTINCT sync_status, sync_direction FROM contacts;"
