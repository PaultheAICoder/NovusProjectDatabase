/**
 * Authentication fixtures for Playwright E2E tests.
 *
 * Current Implementation:
 * This fixture provides a base for authenticated testing. Due to Azure AD SSO,
 * full authentication bypass requires one of:
 *   1. A test user with Azure AD test credentials
 *   2. A backend test endpoint that generates test session tokens
 *   3. Using Playwright's storageState to persist auth between tests
 *
 * For now, tests using this fixture will test unauthenticated flows,
 * which redirects to the login page.
 */

import { test as base, Page, expect } from '@playwright/test';

/**
 * Authentication fixture type definitions.
 */
export type AuthFixtures = {
  /**
   * A page instance that has attempted to navigate to the authenticated area.
   * Currently redirects to login since full auth bypass is not implemented.
   */
  authenticatedPage: Page;
};

/**
 * Extended test with authentication fixtures.
 *
 * Usage:
 * ```typescript
 * import { test, expect } from './fixtures/auth';
 *
 * test('authenticated test', async ({ authenticatedPage }) => {
 *   // Test authenticated flows
 * });
 * ```
 */
export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Navigate to app - will redirect to login if not authenticated
    await page.goto('/');

    // For smoke tests, we verify the login page renders
    // Full auth bypass would set session cookies here
    // eslint-disable-next-line react-hooks/rules-of-hooks
    await use(page);
  },
});

export { expect };
