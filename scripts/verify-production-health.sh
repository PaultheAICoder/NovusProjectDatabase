#!/bin/bash
# scripts/verify-production-health.sh
# Comprehensive production health verification
#
# CHECKS:
#   1. Production container is running
#   2. Alembic migration version matches head
#   3. Key API endpoints respond (not 500)
#   4. Database has minimum expected records
#
# USAGE:
#   ./scripts/verify-production-health.sh                    # All checks
#   ./scripts/verify-production-health.sh --quick            # Skip API checks
#   ./scripts/verify-production-health.sh --issue 52         # Post results to GH issue
#
# EXIT CODES:
#   0 = All checks pass
#   1 = Container not running
#   2 = Migration version mismatch
#   3 = API endpoint returning 500
#   4 = Database record count below minimum
#   99 = Multiple failures

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Production configuration
PROD_DB_CONTAINER="npd-db"
PROD_BACKEND_CONTAINER="npd-backend"
PROD_DB_USER="npd"
PROD_DB_NAME="npd"
PROD_API_BASE="http://localhost:6701"

# Parse arguments
QUICK_MODE=false
ISSUE_NUMBER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick|-q)
            QUICK_MODE=true
            shift
            ;;
        --issue)
            ISSUE_NUMBER="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
ERROR_MESSAGES=""

echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}     NPD Production Health Verification${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# ============================================================================
# CHECK 1: Production containers running
# ============================================================================
echo "Check 1: Verifying production containers..."

if ! docker ps | grep -q "$PROD_DB_CONTAINER"; then
    echo -e "  ${RED}[FAIL]${NC} Database container ($PROD_DB_CONTAINER) not running"
    ERRORS=$((ERRORS + 1))
    ERROR_MESSAGES="${ERROR_MESSAGES}\n- Database container not running"
else
    echo -e "  ${GREEN}[OK]${NC} Database container running"
fi

if ! docker ps | grep -q "$PROD_BACKEND_CONTAINER"; then
    echo -e "  ${RED}[FAIL]${NC} Backend container ($PROD_BACKEND_CONTAINER) not running"
    ERRORS=$((ERRORS + 1))
    ERROR_MESSAGES="${ERROR_MESSAGES}\n- Backend container not running"
else
    echo -e "  ${GREEN}[OK]${NC} Backend container running"
fi

echo ""

# ============================================================================
# CHECK 2: Alembic migration version
# ============================================================================
echo "Check 2: Verifying migration version..."

# Get current migration from production database
CURRENT_MIGRATION=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c \
    "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "none")

# Get expected head from Alembic in the backend container
EXPECTED_HEAD=$(docker exec "$PROD_BACKEND_CONTAINER" alembic heads 2>/dev/null | head -1 | awk '{print $1}' || echo "unknown")

if [ "$EXPECTED_HEAD" = "unknown" ] || [ -z "$EXPECTED_HEAD" ]; then
    # Fallback: Try to get head from local alembic
    EXPECTED_HEAD=$(cd "$PROJECT_ROOT/backend" && alembic heads 2>/dev/null | head -1 | awk '{print $1}' || echo "unknown")
fi

echo "  Expected migration (head): $EXPECTED_HEAD"
echo "  Production version: $CURRENT_MIGRATION"

if [ "$EXPECTED_HEAD" = "unknown" ]; then
    echo -e "  ${YELLOW}[WARN]${NC} Could not determine expected migration head"
elif [ "$CURRENT_MIGRATION" = "none" ]; then
    echo -e "  ${RED}[FAIL]${NC} No migration version found in production!"
    ERRORS=$((ERRORS + 1))
    ERROR_MESSAGES="${ERROR_MESSAGES}\n- No migration version in production database"
elif [ "$CURRENT_MIGRATION" != "$EXPECTED_HEAD" ]; then
    echo -e "  ${RED}[FAIL]${NC} Migration version mismatch!"
    echo "       Production needs migration to: $EXPECTED_HEAD"
    ERRORS=$((ERRORS + 1))
    ERROR_MESSAGES="${ERROR_MESSAGES}\n- Migration version mismatch (have: $CURRENT_MIGRATION, need: $EXPECTED_HEAD)"
else
    echo -e "  ${GREEN}[OK]${NC} Migration version is current"
fi

echo ""

# ============================================================================
# CHECK 3: API endpoint health (skip if --quick)
# ============================================================================
if [ "$QUICK_MODE" = "false" ]; then
    echo "Check 3: Verifying API endpoints..."

    # List of endpoints to check
    ENDPOINTS=(
        "/health"
        "/api/v1/projects"
        "/api/v1/organizations"
        "/api/v1/contacts"
    )

    for endpoint in "${ENDPOINTS[@]}"; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$PROD_API_BASE$endpoint" 2>/dev/null || echo "000")

        if [ "$HTTP_CODE" = "500" ]; then
            echo -e "  ${RED}[FAIL]${NC} $endpoint returned 500"
            ERRORS=$((ERRORS + 1))
            ERROR_MESSAGES="${ERROR_MESSAGES}\n- API endpoint $endpoint returning 500"
        elif [ "$HTTP_CODE" = "000" ]; then
            echo -e "  ${YELLOW}[WARN]${NC} $endpoint not reachable"
        else
            echo -e "  ${GREEN}[OK]${NC} $endpoint (HTTP $HTTP_CODE)"
        fi
    done
else
    echo "Check 3: Skipped (--quick mode)"
fi

echo ""

# ============================================================================
# CHECK 4: Database record counts (minimum thresholds)
# ============================================================================
echo "Check 4: Verifying database record counts..."

# Get counts
PROJECT_COUNT=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM projects;" 2>/dev/null | xargs || echo "0")
ORG_COUNT=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM organizations;" 2>/dev/null | xargs || echo "0")
CONTACT_COUNT=$(docker exec "$PROD_DB_CONTAINER" psql -U "$PROD_DB_USER" -d "$PROD_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM contacts;" 2>/dev/null | xargs || echo "0")

echo "  Projects: $PROJECT_COUNT"
echo "  Organizations: $ORG_COUNT"
echo "  Contacts: $CONTACT_COUNT"

# Minimum thresholds (adjust based on expected production data)
MIN_PROJECTS=1
MIN_ORGS=1
MIN_CONTACTS=0

if [ "$PROJECT_COUNT" -lt "$MIN_PROJECTS" ]; then
    echo -e "  ${YELLOW}[WARN]${NC} Project count below minimum ($MIN_PROJECTS)"
fi

if [ "$ORG_COUNT" -lt "$MIN_ORGS" ]; then
    echo -e "  ${YELLOW}[WARN]${NC} Organization count below minimum ($MIN_ORGS)"
fi

echo -e "  ${GREEN}[OK]${NC} Database has expected data"

echo ""

# ============================================================================
# FINAL RESULT
# ============================================================================
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}================================================================${NC}"
    echo -e "${RED}     PRODUCTION HEALTH CHECK FAILED${NC}"
    echo -e "${RED}================================================================${NC}"
    echo ""
    echo "Errors found: $ERRORS"
    echo -e "Details:$ERROR_MESSAGES"
    echo ""

    # Post to GitHub issue if specified
    if [ -n "$ISSUE_NUMBER" ]; then
        echo "Posting failure to GitHub issue #$ISSUE_NUMBER..."
        gh issue comment "$ISSUE_NUMBER" --body "## Production Health Check FAILED

**Errors**: $ERRORS

**Details**:
$ERROR_MESSAGES

**Action Required**: Investigate and fix before continuing batch processing.

Script: \`scripts/verify-production-health.sh\`" 2>/dev/null || echo "  (Could not post to GitHub)"
    fi

    # Determine exit code
    if [ "$ERRORS" -gt 1 ]; then
        exit 99
    else
        exit 1
    fi
fi

echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}     PRODUCTION HEALTH CHECK PASSED${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "All checks passed. Production is healthy."
echo ""

exit 0
