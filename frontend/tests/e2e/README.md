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

E2E tests support authenticated flows using a backend test endpoint.

### How It Works

1. The backend exposes `POST /api/v1/auth/test-token` when `E2E_TEST_MODE=true`
2. This endpoint creates a test user and returns a valid session cookie
3. Playwright's `authenticatedPage` fixture calls this endpoint before each test
4. The session cookie persists for the test duration

### Security Model

The test token endpoint has multiple layers of security (defense-in-depth):

1. **Production Hard Block**: The endpoint returns 404 in production environment, regardless of any configuration
2. **E2E_TEST_MODE Guard**: Must be explicitly enabled (defaults to false)
3. **Secret Requirement**: In non-development environments (e.g., staging, CI), a valid `E2E_TEST_SECRET` header must be provided
4. **Rate Limiting**: Subject to standard auth rate limits

This defense-in-depth approach ensures that accidental misconfiguration cannot expose authentication bypass in production.

### Environment Variables

| Variable | Development | Staging/CI | Production |
|----------|-------------|------------|------------|
| E2E_TEST_MODE | Optional | Required | BLOCKED |
| E2E_TEST_SECRET | Not required | Required | N/A |

### Using Authenticated Tests

Import from the auth fixture:

```typescript
import { test, expect } from './fixtures/auth';

test('my authenticated test', async ({ authenticatedPage }) => {
  // Page is already authenticated with test user
  await authenticatedPage.goto('/');
  await expect(authenticatedPage.getByText('E2E Test User')).toBeVisible();
});
```

### Test User Details

- **Display Name**: E2E Test User
- **Email**: e2e-test@example.com
- **Role**: user (not admin)

### Mixing Auth and Unauth Tests

For tests that don't need authentication, import from Playwright directly:

```typescript
import { test as unauthTest, expect } from '@playwright/test';

unauthTest('login page shows button', async ({ page }) => {
  await page.goto('/login');
  // Test unauthenticated flow
});
```

### CI Environment

The test Docker environment (`docker-compose.test.yml`) has both `E2E_TEST_MODE=true` and
`E2E_TEST_SECRET` set, so authenticated tests work automatically in CI.

The CI workflow (`.github/workflows/e2e.yml`) also passes the `E2E_TEST_SECRET` environment
variable to Playwright when running tests.

### Local Development

If running tests against local dev server (not Docker), set the environment variable:

```bash
# In backend .env or export
E2E_TEST_MODE=true
```

## Test Structure

```
tests/e2e/
  fixtures/
    auth.ts        # Authentication fixtures (test-token endpoint)
  smoke.spec.ts    # Basic app loading and rendering tests
  auth.spec.ts     # Authentication flow tests
  navigation.spec.ts # Page navigation tests (uses auth fixture)
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
