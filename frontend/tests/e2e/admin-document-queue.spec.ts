/**
 * E2E tests for Admin Document Processing Queue UI.
 * Tests the DocumentQueueCard component on the Admin page.
 *
 * These tests require admin authentication to access the admin page.
 */

import { adminTest, expect } from './fixtures/admin-auth';

adminTest.describe('Admin Document Queue', () => {
  adminTest.beforeEach(async ({ authenticatedAdminPage }) => {
    await authenticatedAdminPage.goto('/admin');
    // Wait for the page to load - look for main h1 heading (it contains text "Admin")
    await expect(authenticatedAdminPage.locator('h1').first()).toBeVisible({ timeout: 10000 });
  });

  adminTest.describe('Queue Display', () => {
    adminTest(
      'document queue section is visible',
      async ({ authenticatedAdminPage }) => {
        // Find the Document Processing Queue heading
        const queueHeading = authenticatedAdminPage.getByText('Document Processing Queue', { exact: false });
        await queueHeading.first().scrollIntoViewIfNeeded();
        await expect(queueHeading.first()).toBeVisible();
      }
    );

    adminTest(
      'queue description is visible',
      async ({ authenticatedAdminPage }) => {
        // Find the Document Processing Queue description text
        const description = authenticatedAdminPage.getByText('View and manage document processing operations');
        await description.scrollIntoViewIfNeeded();
        await expect(description).toBeVisible();
      }
    );

    adminTest(
      'shows statistics section with counts',
      async ({ authenticatedAdminPage }) => {
        // Find the Document Queue description
        const queueDescription = authenticatedAdminPage.getByText('View and manage document processing operations');
        await queueDescription.scrollIntoViewIfNeeded();

        // Stats should show processing, pending, failed, completed counts in the header
        const statsArea = authenticatedAdminPage.getByText(/\d+\s*(processing|pending|failed|completed)/i);
        await expect(statsArea.first()).toBeVisible();
      }
    );

    adminTest('shows refresh button', async ({ authenticatedAdminPage }) => {
      // Find the Document Queue description
      const queueDescription = authenticatedAdminPage.getByText('View and manage document processing operations');
      await queueDescription.scrollIntoViewIfNeeded();

      // Find the section containing the description and locate the refresh button
      const queueSection = authenticatedAdminPage.locator('div').filter({
        has: queueDescription,
      }).first();

      // The refresh button has an SVG icon
      const refreshButton = queueSection.locator('button').filter({
        has: authenticatedAdminPage.locator('svg'),
      }).first();
      await expect(refreshButton).toBeVisible();
    });
  });

  adminTest.describe('Status Filtering', () => {
    adminTest(
      'status filter dropdown exists',
      async ({ authenticatedAdminPage }) => {
        // Find the Document Queue description
        const queueDescription = authenticatedAdminPage.getByText('View and manage document processing operations');
        await queueDescription.scrollIntoViewIfNeeded();

        // Verify there's a dropdown with "All Statuses" text visible on the page
        // after scrolling to the Document Queue section
        const statusFilter = authenticatedAdminPage.getByText('All Statuses');
        await expect(statusFilter.first()).toBeVisible();
      }
    );

    // Note: Detailed dropdown filter selection tests are skipped due to complex page structure
    // with multiple similar dropdowns (Sync Queue, Document Queue, Token Management all have
    // "All Statuses" dropdowns). The filter dropdown existence is verified above.
    // Future enhancement: Add data-testid attributes to make selectors more reliable
  });

  adminTest.describe('Empty State', () => {
    adminTest(
      'shows table or empty message when no queue items',
      async ({ authenticatedAdminPage }) => {
        // Find the Document Queue description
        const queueDescription = authenticatedAdminPage.getByText('View and manage document processing operations');
        await queueDescription.scrollIntoViewIfNeeded();

        // Look for the empty state message or a table
        // The empty state message is "No queue items found" per DocumentQueueTable.tsx
        const emptyState = authenticatedAdminPage.getByText('No queue items found');
        const queueTable = authenticatedAdminPage.locator('table').filter({
          hasText: /Document|Operation|Status/i,
        });

        // One of these should be visible
        await expect(emptyState.or(queueTable)).toBeVisible();
      }
    );
  });

  adminTest.describe('Refresh Functionality', () => {
    adminTest(
      'refresh button triggers data reload',
      async ({ authenticatedAdminPage }) => {
        // Find the Document Queue description
        const queueDescription = authenticatedAdminPage.getByText('View and manage document processing operations');
        await queueDescription.scrollIntoViewIfNeeded();

        // Find the section
        const queueSection = authenticatedAdminPage.locator('div').filter({
          has: queueDescription,
        }).first();

        // Find and click refresh button
        const refreshButton = queueSection.locator('button').filter({
          has: authenticatedAdminPage.locator('svg'),
        }).first();

        await refreshButton.click();

        // Should not throw - verify by waiting for network idle
        await authenticatedAdminPage.waitForLoadState('networkidle');
      }
    );
  });
});
