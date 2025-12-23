/* eslint-disable react-hooks/rules-of-hooks */
/**
 * Admin authentication fixtures for Playwright E2E tests.
 *
 * Uses backend test-token endpoint with admin=true to create admin sessions.
 * This approach:
 * - Only works when backend has E2E_TEST_MODE=true
 * - Creates real session cookies (same as production auth)
 * - Creates user with admin role for testing admin-only features
 *
 * Note: ESLint react-hooks/rules-of-hooks is disabled for this file because
 * Playwright's `use()` function is incorrectly detected as a React hook.
 */

import { test as base, Page, expect } from '@playwright/test';

/**
 * Admin authentication fixture type definitions.
 */
export type AdminAuthFixtures = {
  /**
   * A page instance with authenticated admin session.
   */
  authenticatedAdminPage: Page;
};

/**
 * Authenticate a page as admin by calling the test-token endpoint with admin=true.
 *
 * Security: The endpoint requires X-E2E-Test-Secret header in non-development
 * environments. The secret is read from E2E_TEST_SECRET environment variable.
 */
async function authenticateAdmin(page: Page): Promise<void> {
  // Get base URL from Playwright config or use default test URL
  const pages = page.context().pages();
  let baseURL = 'http://localhost:6710';

  if (pages.length > 0 && pages[0]) {
    const currentUrl = pages[0].url();
    if (currentUrl && currentUrl.startsWith('http')) {
      baseURL = new URL(currentUrl).origin;
    }
  }

  // Get test secret from environment (optional in development)
  const testSecret = process.env.E2E_TEST_SECRET || '';

  // Call test-token endpoint with admin=true to get admin session cookie
  const response = await page.request.post(
    `${baseURL}/api/v1/auth/test-token?admin=true`,
    {
      headers: {
        'X-E2E-Test-Secret': testSecret,
      },
    }
  );

  if (!response.ok()) {
    const status = response.status();
    if (status === 404) {
      throw new Error(
        'Test token endpoint not found. Ensure E2E_TEST_MODE=true in backend environment.'
      );
    }
    if (status === 401) {
      throw new Error(
        'Test token authentication failed. Ensure E2E_TEST_SECRET is set correctly in environment.'
      );
    }
    throw new Error(
      `Failed to authenticate as admin: ${status} ${response.statusText()}`
    );
  }

  // Cookie is automatically stored by Playwright
}

/**
 * Extended test with admin authentication fixtures.
 *
 * Usage:
 * ```typescript
 * import { adminTest, expect } from './fixtures/admin-auth';
 *
 * adminTest('admin can access admin page', async ({ authenticatedAdminPage }) => {
 *   await authenticatedAdminPage.goto('/admin');
 *   // Page is now authenticated as admin
 * });
 * ```
 */
export const adminTest = base.extend<AdminAuthFixtures>({
  authenticatedAdminPage: async ({ page }, use) => {
    // Authenticate as admin before providing page
    await authenticateAdmin(page);

    // Navigate to app - should now be authenticated as admin
    await page.goto('/');

    // Verify admin authentication worked by checking for admin user display name
    // (wait a bit for React to render)
    await page
      .waitForSelector('text=E2E Admin User', { timeout: 10000 })
      .catch(() => {
        // If display name not found, auth may have failed silently
        console.warn(
          'Warning: Admin user display name not found after authentication'
        );
      });

    await use(page);
  },
});

export { expect };
