/* eslint-disable react-hooks/rules-of-hooks */
/**
 * Authentication fixtures for Playwright E2E tests.
 *
 * Uses backend test-token endpoint to create authenticated sessions.
 * This approach:
 * - Only works when backend has E2E_TEST_MODE=true
 * - Creates real session cookies (same as production auth)
 * - Persists auth via Playwright's cookie handling
 *
 * Note: ESLint react-hooks/rules-of-hooks is disabled for this file because
 * Playwright's `use()` function is incorrectly detected as a React hook.
 */

import { test as base, Page, expect } from '@playwright/test';

/**
 * Authentication fixture type definitions.
 */
export type AuthFixtures = {
  /**
   * A page instance with authenticated session.
   */
  authenticatedPage: Page;
};

/**
 * Authenticate a page by calling the test-token endpoint.
 */
async function authenticate(page: Page): Promise<void> {
  // Get base URL from Playwright config or use default test URL
  const pages = page.context().pages();
  let baseURL = 'http://localhost:6710';

  if (pages.length > 0 && pages[0]) {
    const currentUrl = pages[0].url();
    if (currentUrl && currentUrl.startsWith('http')) {
      baseURL = new URL(currentUrl).origin;
    }
  }

  // Call test-token endpoint to get session cookie
  const response = await page.request.post(`${baseURL}/api/v1/auth/test-token`);

  if (!response.ok()) {
    const status = response.status();
    if (status === 404) {
      throw new Error(
        'Test token endpoint not found. Ensure E2E_TEST_MODE=true in backend environment.'
      );
    }
    throw new Error(`Failed to authenticate: ${status} ${response.statusText()}`);
  }

  // Cookie is automatically stored by Playwright
}

/**
 * Extended test with authentication fixtures.
 *
 * Usage:
 * ```typescript
 * import { test, expect } from './fixtures/auth';
 *
 * test('authenticated test', async ({ authenticatedPage }) => {
 *   await authenticatedPage.goto('/');
 *   // Page is now authenticated
 * });
 * ```
 */
export const test = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Authenticate before providing page
    await authenticate(page);

    // Navigate to app - should now be authenticated
    await page.goto('/');

    // Verify authentication worked by checking for user display name
    // (wait a bit for React to render)
    await page.waitForSelector('text=E2E Test User', { timeout: 10000 }).catch(() => {
      // If display name not found, auth may have failed silently
      console.warn('Warning: User display name not found after authentication');
    });

    await use(page);
  },
});

export { expect };
