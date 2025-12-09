/**
 * Navigation tests for the Novus Project Database frontend.
 *
 * Note: Most navigation tests require authentication.
 * Tests that require auth are currently skipped.
 */

import { test, expect } from '@playwright/test';

test.describe('Navigation (requires auth)', () => {
  // These tests require authentication and are skipped until auth bypass is implemented
  test.skip('sidebar navigation works', async ({ page }) => {
    // TODO: Implement when auth bypass is available
    await page.goto('/');

    // Click Projects link
    await page.getByRole('link', { name: 'Projects' }).click();
    await expect(page).toHaveURL('/projects');

    // Click Organizations link
    await page.getByRole('link', { name: 'Organizations' }).click();
    await expect(page).toHaveURL('/organizations');

    // Click Contacts link
    await page.getByRole('link', { name: 'Contacts' }).click();
    await expect(page).toHaveURL('/contacts');

    // Click Dashboard link
    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL('/');
  });

  test.skip('header shows user info when authenticated', async ({ page }) => {
    // TODO: Implement when auth bypass is available
    await page.goto('/');

    // User display name visible
    await expect(page.getByText(/Test User/)).toBeVisible();

    // Sign out button visible
    await expect(page.getByRole('button', { name: /Sign out/i })).toBeVisible();
  });

  test.skip('breadcrumb navigation works', async ({ page }) => {
    // TODO: Implement when auth bypass is available
    await page.goto('/projects/123');

    // Breadcrumb should show Projects link
    await expect(page.getByRole('link', { name: 'Projects' })).toBeVisible();

    // Clicking breadcrumb navigates back
    await page.getByRole('link', { name: 'Projects' }).click();
    await expect(page).toHaveURL('/projects');
  });
});

test.describe('Login Page Navigation', () => {
  test('login page is accessible', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: /Novus Project Database/i })).toBeVisible();
  });

  test('login page has correct structure', async ({ page }) => {
    await page.goto('/login');

    // Main heading
    await expect(page.getByRole('heading', { name: /Novus Project Database/i })).toBeVisible();

    // Sign in prompt
    await expect(page.getByText(/Sign in to continue/i)).toBeVisible();

    // Sign in button
    await expect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible();
  });

  test('direct navigation to login works', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveURL(/.*login/);
    await expect(page.getByRole('button', { name: /Sign in/i })).toBeVisible();
  });
});
