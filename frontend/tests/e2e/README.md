# E2E Tests

End-to-end tests using Playwright for the Novus Project Database frontend.

## Prerequisites

1. Install Playwright browsers:

   ```bash
   # Install all browsers (chromium, firefox, webkit)
   npx playwright install

   # Or install only chromium for faster setup
   npx playwright install chromium
   ```

2. Start test environment:

   ```bash
   # From project root
   docker compose -f docker-compose.test.yml up -d
   ```

3. Wait for services to be healthy:
   ```bash
   docker compose -f docker-compose.test.yml ps
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

### Tests pass locally but fail in CI

- Check CI has access to test environment
- Verify CI waits for services to be healthy before running tests
- Consider increasing timeouts for CI (configured in playwright.config.ts)
