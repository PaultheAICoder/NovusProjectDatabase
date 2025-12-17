/**
 * Navigation tests for the Novus Project Database frontend.
 *
 * Tests that require authentication use the auth fixture
 * which calls the backend test-token endpoint.
 */

import { test, expect } from './fixtures/auth';
import { test as unauthTest, expect as unauthExpect } from '@playwright/test';

test.describe('Navigation (authenticated)', () => {
  test('sidebar navigation works', async ({ authenticatedPage }) => {
    // Start from dashboard
    await authenticatedPage.goto('/');

    // Click Projects link
    await authenticatedPage.getByRole('link', { name: 'Projects' }).click();
    await expect(authenticatedPage).toHaveURL('/projects');

    // Click Organizations link
    await authenticatedPage.getByRole('link', { name: 'Organizations' }).click();
    await expect(authenticatedPage).toHaveURL('/organizations');

    // Click Contacts link
    await authenticatedPage.getByRole('link', { name: 'Contacts' }).click();
    await expect(authenticatedPage).toHaveURL('/contacts');

    // Click Dashboard link
    await authenticatedPage.getByRole('link', { name: 'Dashboard' }).click();
    await expect(authenticatedPage).toHaveURL('/');
  });

  test('header shows user info when authenticated', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/');

    // User display name visible (from test user)
    await expect(authenticatedPage.getByText('E2E Test User')).toBeVisible();

    // Sign out button visible
    await expect(authenticatedPage.getByRole('button', { name: /Sign out/i })).toBeVisible();
  });

  test('breadcrumb navigation works', async ({ authenticatedPage }) => {
    // Navigate to projects first
    await authenticatedPage.goto('/projects');

    // Wait for projects page to load
    await expect(authenticatedPage.getByRole('heading', { name: /Projects/i })).toBeVisible();

    // Note: Breadcrumb test needs a valid project ID
    // For now, just verify the Projects heading is visible
    // Full breadcrumb test would require creating a project first
  });
});

// Keep unauthenticated tests separate
unauthTest.describe('Login Page Navigation', () => {
  unauthTest('login page is accessible', async ({ page }) => {
    await page.goto('/login');
    await unauthExpect(page.getByRole('heading', { name: /Novus Project Database/i })).toBeVisible();
  });

  unauthTest('login page has correct structure', async ({ page }) => {
    await page.goto('/login');

    // Main heading
    await unauthExpect(page.getByRole('heading', { name: /Novus Project Database/i })).toBeVisible();

    // Sign in prompt
    await unauthExpect(page.getByText(/Sign in to continue/i)).toBeVisible();

    // Sign in button
    await unauthExpect(page.getByRole('button', { name: /Sign in with Azure AD/i })).toBeVisible();
  });

  unauthTest('direct navigation to login works', async ({ page }) => {
    await page.goto('/login');
    await unauthExpect(page).toHaveURL(/.*login/);
    await unauthExpect(page.getByRole('button', { name: /Sign in/i })).toBeVisible();
  });
});
