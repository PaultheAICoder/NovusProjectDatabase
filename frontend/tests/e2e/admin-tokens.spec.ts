/**
 * E2E tests for Admin Token Management UI.
 * Tests the TokenManagementCard component on the Admin page.
 *
 * These tests require admin authentication to access the admin page.
 */

import { adminTest, expect } from './fixtures/admin-auth';

adminTest.describe('Admin Token Management', () => {
  adminTest.beforeEach(async ({ authenticatedAdminPage }) => {
    await authenticatedAdminPage.goto('/admin');
    // Wait for admin page to load - the h1 heading contains "Admin"
    await expect(authenticatedAdminPage.locator('h1').first()).toBeVisible({ timeout: 10000 });
  });

  adminTest.describe('Page Access', () => {
    adminTest(
      'admin page loads with token management section',
      async ({ authenticatedAdminPage }) => {
        // Token management card should be visible
        await expect(
          authenticatedAdminPage.getByRole('heading', { name: /All API Tokens/i })
        ).toBeVisible();
      }
    );

    adminTest(
      'token management card shows description',
      async ({ authenticatedAdminPage }) => {
        await expect(
          authenticatedAdminPage.getByText(
            /View and manage API tokens across all users/i
          )
        ).toBeVisible();
      }
    );
  });

  adminTest.describe('Token List Display', () => {
    adminTest(
      'shows empty state or token table',
      async ({ authenticatedAdminPage }) => {
        // Scroll to token management section using description text
        const tokenDescription = authenticatedAdminPage.getByText('View and manage API tokens across all users');
        await tokenDescription.scrollIntoViewIfNeeded();

        // If no tokens, should show empty state message
        // Note: May need to check for either empty state OR token table
        const emptyState = authenticatedAdminPage.getByText(/No API tokens/i);
        const tokenTable = authenticatedAdminPage
          .locator('table')
          .filter({ hasText: 'Name' });

        // One of these should be visible
        await expect(emptyState.or(tokenTable)).toBeVisible();
      }
    );

    adminTest(
      'shows status filter dropdown',
      async ({ authenticatedAdminPage }) => {
        // Scroll to token management section using description text
        const tokenDescription = authenticatedAdminPage.getByText('View and manage API tokens across all users');
        await tokenDescription.scrollIntoViewIfNeeded();

        // Admin view has status filter - look for "All Statuses" text
        const statusFilter = authenticatedAdminPage.getByText('All Statuses');
        await expect(statusFilter.first()).toBeVisible();
      }
    );

    adminTest('refresh button works', async ({ authenticatedAdminPage }) => {
      // Scroll to token management section using description text
      const tokenDescription = authenticatedAdminPage.getByText('View and manage API tokens across all users');
      await tokenDescription.scrollIntoViewIfNeeded();

      // Find the token section and then find the refresh button within it
      const tokenSection = authenticatedAdminPage.locator('div').filter({
        has: tokenDescription,
      }).first();

      const refreshButton = tokenSection.locator('button').filter({
        has: authenticatedAdminPage.locator('svg'),
      }).first();

      await refreshButton.click();
      // Should not throw error - verify by waiting for network idle
      await authenticatedAdminPage.waitForLoadState('networkidle');
    });
  });

  // Note: Detailed dropdown filter testing is skipped due to complex page structure
  // with multiple similar dropdowns. The core functionality is verified by:
  // 1. Token List Display tests verifying the dropdown exists
  // 2. Manual testing during development
  // Future enhancement: Add data-testid attributes to make selectors more reliable

  adminTest.describe('Admin Token View Restrictions', () => {
    adminTest(
      'admin view does not show create token button',
      async ({ authenticatedAdminPage }) => {
        // Scroll to token management section
        await authenticatedAdminPage
          .getByRole('heading', { name: /All API Tokens/i })
          .scrollIntoViewIfNeeded();

        // Should NOT have "New Token" button in admin view
        // The admin view uses isAdminView={true} which hides the create button
        await expect(
          authenticatedAdminPage.getByRole('button', { name: /New Token/i })
        ).not.toBeVisible();
      }
    );
  });
});
