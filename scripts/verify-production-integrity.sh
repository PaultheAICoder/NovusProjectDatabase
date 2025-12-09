#!/bin/bash
# scripts/verify-production-integrity.sh
# Verifies production database was not modified during orchestrate3 cycle
#
# USAGE:
#   ./scripts/verify-production-integrity.sh <expected_projects> <expected_documents> <expected_orgs> <expected_users>
#
# RETURNS:
#   0 = Success (counts match)
#   1 = Failure (counts differ - CRITICAL ERROR)

set -e

EXPECTED_PROJECTS="${1:-0}"
EXPECTED_DOCUMENTS="${2:-0}"
EXPECTED_ORGS="${3:-0}"
EXPECTED_USERS="${4:-0}"

# Production database configuration
PROD_DB_CONTAINER="npd-db"
PROD_DB_USER="npd"
PROD_DB_NAME="npd"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "================================================================"
echo "NPD Production Database Integrity Verification"
echo "================================================================"
echo ""

# Verify production container is running
if ! docker ps | grep -q "$PROD_DB_CONTAINER"; then
    echo -e "${RED}ERROR: Production database container not running${NC}"
    exit 1
fi

# Get current counts
ACTUAL_PROJECTS=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c "SELECT COUNT(*) FROM projects;" 2>/dev/null | xargs || echo "0")
ACTUAL_DOCUMENTS=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs || echo "0")
ACTUAL_ORGS=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c "SELECT COUNT(*) FROM organizations;" 2>/dev/null | xargs || echo "0")
ACTUAL_USERS=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | xargs || echo "0")

echo "Expected vs Actual:"
echo "  Projects:      $EXPECTED_PROJECTS -> $ACTUAL_PROJECTS"
echo "  Documents:     $EXPECTED_DOCUMENTS -> $ACTUAL_DOCUMENTS"
echo "  Organizations: $EXPECTED_ORGS -> $ACTUAL_ORGS"
echo "  Users:         $EXPECTED_USERS -> $ACTUAL_USERS"
echo ""

# Compare
ERRORS=0

if [ "$ACTUAL_PROJECTS" != "$EXPECTED_PROJECTS" ]; then
    echo -e "${RED}CRITICAL: Project count changed! ($EXPECTED_PROJECTS -> $ACTUAL_PROJECTS)${NC}"
    ERRORS=$((ERRORS + 1))
fi

if [ "$ACTUAL_DOCUMENTS" != "$EXPECTED_DOCUMENTS" ]; then
    echo -e "${RED}CRITICAL: Document count changed! ($EXPECTED_DOCUMENTS -> $ACTUAL_DOCUMENTS)${NC}"
    ERRORS=$((ERRORS + 1))
fi

if [ "$ACTUAL_ORGS" != "$EXPECTED_ORGS" ]; then
    echo -e "${RED}CRITICAL: Organization count changed! ($EXPECTED_ORGS -> $ACTUAL_ORGS)${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Note: Users may increase during normal operation (new logins), only flag if DECREASED
if [ "$ACTUAL_USERS" -lt "$EXPECTED_USERS" ]; then
    echo -e "${RED}CRITICAL: User count DECREASED! ($EXPECTED_USERS -> $ACTUAL_USERS)${NC}"
    ERRORS=$((ERRORS + 1))
elif [ "$ACTUAL_USERS" != "$EXPECTED_USERS" ]; then
    echo -e "${YELLOW}NOTE: User count increased ($EXPECTED_USERS -> $ACTUAL_USERS)${NC}"
    echo "  This is expected if new users logged in during the cycle."
fi

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo -e "${RED}================================================================${NC}"
    echo -e "${RED}INTEGRITY CHECK FAILED${NC}"
    echo -e "${RED}================================================================${NC}"
    echo ""
    echo "PRODUCTION DATABASE MAY HAVE BEEN MODIFIED!"
    echo "DO NOT commit or push until this is investigated."
    echo ""
    exit 1
fi

echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}Production database integrity verified${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "Database unchanged during orchestrate3 cycle"
echo ""
exit 0
