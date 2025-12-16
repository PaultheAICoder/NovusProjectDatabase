# E2E Tests

End-to-end tests using Playwright for the Novus Project Database frontend.

## Prerequisites

1. Install Playwright browsers:

   ```bash
   # Install chromium only (fastest, matches CI)
   npx playwright install chromium

   # Or install all browsers (chromium, firefox, webkit)
   npx playwright install
   ```

   > **Note**: The CI pipeline only runs chromium tests. Firefox and WebKit are optional for local development.

2. Start test environment:

   ```bash
   # From project root
   docker compose -f docker-compose.test.yml up -d
   ```

3. Wait for services to be healthy:
   ```bash
   docker compose -f docker-compose.test.yml ps
   ```

### Verify Services Before Running Tests

Quick check that all test services are running:

```bash
# Check container status
docker compose -f docker-compose.test.yml ps

# Test backend health
curl -s http://localhost:6711/api/v1/auth/me
# Should return {"detail":"Not authenticated"} (401 is expected)

# Test frontend
curl -s http://localhost:6710 | head -5
# Should return HTML
```

## Running Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run with UI mode (interactive)
npm run test:e2e:ui

# Run specific test file
npm run test:e2e -- smoke.spec.ts

# Run specific browser only
npm run test:e2e -- --project=chromium

# Run with headed browser (visible)
npm run test:e2e -- --headed

# Run in debug mode
npm run test:e2e -- --debug

# Show test report after run
npx playwright show-report
```

## Test Environment

Tests run against the Docker test environment:

- Frontend: http://localhost:6710
- Backend: http://localhost:6711
- Database: localhost:6712

The base URL can be overridden with the `PLAYWRIGHT_BASE_URL` environment variable.

## Authentication

E2E tests run against unauthenticated flows by default. Tests that require
authentication are currently skipped with `test.skip()`.

To implement full auth testing, one of these approaches is needed:

1. **Azure AD Test Credentials**: Create a test user with Azure AD and use Playwright's `storageState` to persist auth
2. **Backend Test Endpoint**: Add a test-only endpoint that generates session tokens
3. **Mock Auth**: Intercept auth requests in tests (limited applicability)

## Test Structure

```
tests/e2e/
  fixtures/
    auth.ts        # Authentication fixtures (placeholder)
  smoke.spec.ts    # Basic app loading and rendering tests
  auth.spec.ts     # Authentication flow tests
  navigation.spec.ts # Page navigation tests (some require auth)
  README.md        # This file
```

## Adding New Tests

1. Create a new `.spec.ts` file in this directory
2. Import test utilities:
   ```typescript
   import { test, expect } from '@playwright/test';
   ```
3. Use `test.describe()` to group related tests
4. Follow existing patterns for page interactions
5. Use role-based selectors when possible (`getByRole`, `getByLabel`)

## Best Practices

- **Selectors**: Prefer `getByRole()`, `getByLabel()`, `getByText()` over CSS selectors
- **Assertions**: Use `expect(locator).toBeVisible()` instead of `expect(locator).toBeTruthy()`
- **Timeouts**: Default timeouts are set in playwright.config.ts; avoid hardcoding
- **Parallelization**: Tests are parallelized by default; ensure tests don't share state
- **Screenshots**: Taken automatically on failure; find them in `test-results/`

## Troubleshooting

### Tests fail with "Navigation timeout"

The test environment may not be running. Start it with:

```bash
docker compose -f docker-compose.test.yml up -d
```

### Tests fail with "Connection refused"

Verify services are healthy:

```bash
docker compose -f docker-compose.test.yml ps
docker compose -f docker-compose.test.yml logs frontend
```

### Browser not installed

Run:

```bash
npx playwright install
```

### Tests fail waiting for app to load (stuck on "Loading...")

The backend container may have crashed or failed to start. Check logs:

```bash
docker compose -f docker-compose.test.yml logs backend-test --tail=50
```

If you see import errors (e.g., `ModuleNotFoundError`), the Docker image needs to be rebuilt:

```bash
# Rebuild backend image with latest dependencies
docker compose -f docker-compose.test.yml build --no-cache backend-test

# Restart the container
docker compose -f docker-compose.test.yml up -d backend-test
```

**When to rebuild**: Always rebuild Docker images after:
- Pulling new changes from main
- Modifying `backend/requirements.txt`
- Adding new Python dependencies

### Tests pass locally but fail in CI

- Check CI has access to test environment
- Verify CI waits for services to be healthy before running tests
- Consider increasing timeouts for CI (configured in playwright.config.ts)
