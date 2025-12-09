/**
 * Smoke tests for the Novus Project Database frontend.
 *
 * These tests verify basic application loading and rendering.
 * They do not require authentication.
 *
 * Note: The app is a SPA, so redirects happen client-side after the
 * React app loads and makes an auth check API call.
 */

import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('app loads without critical errors', async ({ page }) => {
    // Collect console errors
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/');

    // Wait for the login button to appear (indicates redirect completed)
    // The SPA needs time to load, check auth, and redirect
    await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible({
      timeout: 15000,
    });

    // Filter out expected 401 errors (unauthenticated API calls)
    const criticalErrors = errors.filter(
      (e) => !e.includes('401') && !e.includes('Unauthorized') && !e.includes('Failed to fetch')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('login page renders correctly', async ({ page }) => {
    await page.goto('/login');

    // Page title should contain Novus
    await expect(page).toHaveTitle(/Novus/);

    // Login UI elements should be visible
    await expect(page.getByRole('heading', { name: /Novus Project Database/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible();
  });

  test('login page has accessible sign in button', async ({ page }) => {
    await page.goto('/login');

    const signInButton = page.getByRole('button', { name: /Sign in/i });
    await expect(signInButton).toBeVisible();
    await expect(signInButton).toBeEnabled();
  });

  test('app responds to navigation', async ({ page }) => {
    // Start at login
    await page.goto('/login');
    await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible();

    // Try to go to root - should eventually show login button due to redirect
    await page.goto('/');
    await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible({
      timeout: 15000,
    });
  });
});
