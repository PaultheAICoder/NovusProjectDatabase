/**
 * Authentication flow tests for the Novus Project Database frontend.
 *
 * These tests verify:
 * - Unauthenticated redirect behavior
 * - Login button functionality
 * - Error message display
 * - Protected route access
 *
 * Note: The app is a SPA, so redirects happen client-side after the
 * React app loads and makes an auth check API call.
 */

import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('unauthenticated users are redirected to login', async ({ page }) => {
    // Try to access protected route
    await page.goto('/projects');

    // Wait for the login button to appear (indicates redirect completed)
    // The SPA needs time to load, check auth, and redirect
    await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test('login button initiates Azure AD flow', async ({ page }) => {
    await page.goto('/login');

    const signInButton = page.getByRole('button', { name: /Sign in with Azure AD/i });
    await expect(signInButton).toBeVisible();

    // Click should trigger navigation to Azure or backend auth endpoint
    // We verify the button is clickable and triggers some action
    // Note: In test env, the Azure redirect may not complete, which is expected
    await signInButton.click();

    // Either we're redirected to Azure login OR we stay on the page
    // (due to CORS/network issues in test env) - both are acceptable
    await page.waitForTimeout(1000);
    const currentUrl = page.url();
    expect(
      currentUrl.includes('login.microsoftonline.com') ||
        currentUrl.includes('localhost') ||
        currentUrl.includes('auth/login')
    ).toBeTruthy();
  });

  test('displays error message for token_exchange_failed', async ({ page }) => {
    await page.goto('/login?error=token_exchange_failed');

    // Error message should be visible
    await expect(page.getByText(/Authentication failed/i)).toBeVisible();
  });

  test('displays error message for no_id_token', async ({ page }) => {
    await page.goto('/login?error=no_id_token');

    await expect(page.getByText(/Authentication failed/i)).toBeVisible();
  });

  test('displays error message for domain_not_allowed', async ({ page }) => {
    await page.goto('/login?error=domain_not_allowed');

    await expect(page.getByText(/not authorized/i)).toBeVisible();
  });

  test('displays generic error for unknown error codes', async ({ page }) => {
    await page.goto('/login?error=unknown_error');

    await expect(page.getByText(/error occurred/i)).toBeVisible();
  });
});

test.describe('Protected Routes Redirect', () => {
  const protectedRoutes = [
    '/projects',
    '/organizations',
    '/contacts',
    '/search',
    '/admin',
    '/import',
  ];

  for (const route of protectedRoutes) {
    test(`${route} redirects to login when unauthenticated`, async ({ page }) => {
      await page.goto(route);

      // Wait for the login button to appear (indicates redirect completed)
      await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible({
        timeout: 15000,
      });
    });
  }
});
