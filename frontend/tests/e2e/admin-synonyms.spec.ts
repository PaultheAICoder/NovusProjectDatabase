/**
 * E2E tests for Admin Tag Synonym Management UI.
 * Tests the SynonymManagementCard component on the Admin page.
 *
 * These tests require admin authentication to access the admin page.
 */

import { adminTest, expect } from './fixtures/admin-auth';

adminTest.describe('Admin Synonym Management', () => {
  adminTest.beforeEach(async ({ authenticatedAdminPage }) => {
    await authenticatedAdminPage.goto('/admin');
    // Wait for admin page to load - the h1 heading contains "Admin"
    await expect(
      authenticatedAdminPage.locator('h1').first()
    ).toBeVisible({ timeout: 10000 });
  });

  adminTest.describe('Section Display', () => {
    adminTest(
      'synonym management section is visible',
      async ({ authenticatedAdminPage }) => {
        // Find "Tag Synonyms" heading and verify visible
        const heading = authenticatedAdminPage.getByRole('heading', {
          name: /Tag Synonyms/i,
        });
        await heading.scrollIntoViewIfNeeded();
        await expect(heading).toBeVisible();
      }
    );

    adminTest(
      'shows description text',
      async ({ authenticatedAdminPage }) => {
        // "Manage synonym relationships between tags for improved search"
        const description = authenticatedAdminPage.getByText(
          'Manage synonym relationships between tags for improved search'
        );
        await description.scrollIntoViewIfNeeded();
        await expect(description).toBeVisible();
      }
    );
  });

  adminTest.describe('Action Buttons', () => {
    adminTest(
      'shows Add Synonym button',
      async ({ authenticatedAdminPage }) => {
        // Button: "Add Synonym"
        const addButton = authenticatedAdminPage.getByRole('button', {
          name: /Add Synonym/i,
        });
        await addButton.scrollIntoViewIfNeeded();
        await expect(addButton).toBeVisible();
      }
    );

    adminTest('shows Import button', async ({ authenticatedAdminPage }) => {
      // Button: "Import"
      const importButton = authenticatedAdminPage.getByRole('button', {
        name: /^Import$/i,
      });
      await importButton.scrollIntoViewIfNeeded();
      await expect(importButton).toBeVisible();
    });

    adminTest('shows refresh button', async ({ authenticatedAdminPage }) => {
      // Find synonym section and locate refresh button with SVG icon
      const description = authenticatedAdminPage.getByText(
        'Manage synonym relationships between tags for improved search'
      );
      await description.scrollIntoViewIfNeeded();

      const section = authenticatedAdminPage
        .locator('div')
        .filter({ has: description })
        .first();
      const refreshButton = section
        .locator('button')
        .filter({
          has: authenticatedAdminPage.locator('svg'),
        })
        .first();
      await expect(refreshButton).toBeVisible();
    });
  });

  adminTest.describe('Synonym List Display', () => {
    adminTest(
      'shows empty state or synonym table',
      async ({ authenticatedAdminPage }) => {
        const description = authenticatedAdminPage.getByText(
          'Manage synonym relationships between tags for improved search'
        );
        await description.scrollIntoViewIfNeeded();

        // Empty state: "No synonym relationships found"
        const emptyState = authenticatedAdminPage.getByText(
          'No synonym relationships found'
        );
        // Table should have headers: Primary Tag, Synonym Tag, Confidence, Created, Action
        const synonymTable = authenticatedAdminPage.locator('table').filter({
          hasText: /Primary Tag|Synonym Tag/i,
        });

        await expect(emptyState.or(synonymTable)).toBeVisible();
      }
    );
  });

  adminTest.describe('Create Synonym Dialog', () => {
    adminTest(
      'opens create dialog when Add Synonym clicked',
      async ({ authenticatedAdminPage }) => {
        const addButton = authenticatedAdminPage.getByRole('button', {
          name: /Add Synonym/i,
        });
        await addButton.scrollIntoViewIfNeeded();
        await addButton.click();

        // Dialog should open with title "Create Tag Synonym"
        await expect(
          authenticatedAdminPage.getByRole('heading', {
            name: /Create Tag Synonym/i,
          })
        ).toBeVisible();
      }
    );

    adminTest(
      'create dialog has required fields',
      async ({ authenticatedAdminPage }) => {
        const addButton = authenticatedAdminPage.getByRole('button', {
          name: /Add Synonym/i,
        });
        await addButton.scrollIntoViewIfNeeded();
        await addButton.click();

        // Should have Primary Tag and Synonym Tag select fields (use exact match for labels)
        await expect(
          authenticatedAdminPage.getByLabel('Primary Tag')
        ).toBeVisible();
        await expect(
          authenticatedAdminPage.getByLabel('Synonym Tag')
        ).toBeVisible();

        // Should have Cancel and Create buttons
        await expect(
          authenticatedAdminPage.getByRole('button', { name: /Cancel/i })
        ).toBeVisible();
        await expect(
          authenticatedAdminPage.getByRole('button', { name: /^Create$/i })
        ).toBeVisible();
      }
    );

    adminTest(
      'can close create dialog',
      async ({ authenticatedAdminPage }) => {
        const addButton = authenticatedAdminPage.getByRole('button', {
          name: /Add Synonym/i,
        });
        await addButton.scrollIntoViewIfNeeded();
        await addButton.click();

        await expect(
          authenticatedAdminPage.getByRole('heading', {
            name: /Create Tag Synonym/i,
          })
        ).toBeVisible();

        // Click Cancel
        await authenticatedAdminPage
          .getByRole('button', { name: /Cancel/i })
          .click();

        // Dialog should close
        await expect(
          authenticatedAdminPage.getByRole('heading', {
            name: /Create Tag Synonym/i,
          })
        ).not.toBeVisible();
      }
    );
  });

  adminTest.describe('Import Synonyms Dialog', () => {
    adminTest(
      'opens import dialog when Import clicked',
      async ({ authenticatedAdminPage }) => {
        const importButton = authenticatedAdminPage.getByRole('button', {
          name: /^Import$/i,
        });
        await importButton.scrollIntoViewIfNeeded();
        await importButton.click();

        // Dialog should open with title "Import Synonyms"
        await expect(
          authenticatedAdminPage.getByRole('heading', {
            name: /Import Synonyms/i,
          })
        ).toBeVisible();
      }
    );

    adminTest(
      'import dialog has Paste Text and Upload File tabs',
      async ({ authenticatedAdminPage }) => {
        const importButton = authenticatedAdminPage.getByRole('button', {
          name: /^Import$/i,
        });
        await importButton.scrollIntoViewIfNeeded();
        await importButton.click();

        // Tabs
        await expect(
          authenticatedAdminPage.getByRole('tab', { name: /Paste Text/i })
        ).toBeVisible();
        await expect(
          authenticatedAdminPage.getByRole('tab', { name: /Upload File/i })
        ).toBeVisible();
      }
    );

    adminTest(
      'paste text tab shows textarea',
      async ({ authenticatedAdminPage }) => {
        const importButton = authenticatedAdminPage.getByRole('button', {
          name: /^Import$/i,
        });
        await importButton.scrollIntoViewIfNeeded();
        await importButton.click();

        // Should have CSV Content label and textarea (Paste Text is default tab)
        await expect(
          authenticatedAdminPage.getByText('CSV Content')
        ).toBeVisible();
        await expect(authenticatedAdminPage.locator('textarea')).toBeVisible();
      }
    );

    adminTest(
      'can switch to upload file tab',
      async ({ authenticatedAdminPage }) => {
        const importButton = authenticatedAdminPage.getByRole('button', {
          name: /^Import$/i,
        });
        await importButton.scrollIntoViewIfNeeded();
        await importButton.click();

        // Click Upload File tab
        await authenticatedAdminPage
          .getByRole('tab', { name: /Upload File/i })
          .click();

        // Should show file input (use exact match for label)
        await expect(
          authenticatedAdminPage.getByLabel('CSV File')
        ).toBeVisible();
      }
    );

    adminTest(
      'parse button is disabled when textarea is empty',
      async ({ authenticatedAdminPage }) => {
        const importButton = authenticatedAdminPage.getByRole('button', {
          name: /^Import$/i,
        });
        await importButton.scrollIntoViewIfNeeded();
        await importButton.click();

        // Parse & Preview button should be disabled
        const parseButton = authenticatedAdminPage.getByRole('button', {
          name: /Parse & Preview/i,
        });
        await expect(parseButton).toBeDisabled();
      }
    );

    adminTest(
      'can close import dialog',
      async ({ authenticatedAdminPage }) => {
        const importButton = authenticatedAdminPage.getByRole('button', {
          name: /^Import$/i,
        });
        await importButton.scrollIntoViewIfNeeded();
        await importButton.click();

        await expect(
          authenticatedAdminPage.getByRole('heading', {
            name: /Import Synonyms/i,
          })
        ).toBeVisible();

        // Click Cancel
        await authenticatedAdminPage
          .getByRole('button', { name: /Cancel/i })
          .click();

        // Dialog should close
        await expect(
          authenticatedAdminPage.getByRole('heading', {
            name: /Import Synonyms/i,
          })
        ).not.toBeVisible();
      }
    );
  });

  adminTest.describe('Refresh Functionality', () => {
    adminTest(
      'refresh button triggers data reload',
      async ({ authenticatedAdminPage }) => {
        const description = authenticatedAdminPage.getByText(
          'Manage synonym relationships between tags for improved search'
        );
        await description.scrollIntoViewIfNeeded();

        const section = authenticatedAdminPage
          .locator('div')
          .filter({ has: description })
          .first();
        const refreshButton = section
          .locator('button')
          .filter({
            has: authenticatedAdminPage.locator('svg'),
          })
          .first();

        await refreshButton.click();

        // Should not throw - verify by waiting for network idle
        await authenticatedAdminPage.waitForLoadState('networkidle');
      }
    );
  });
});
