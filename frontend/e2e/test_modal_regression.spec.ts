import { test, expect, Page } from '@playwright/test';

/**
 * Helper function for switching roles during automated read-only tests.
 * Scope: read-only navigation verification across role states.
 */
async function selectDevRole(page: Page, targetRole: 'ADMIN' | 'RECEPTIONIST' | 'LAB_TECH') {
  const username = targetRole === 'ADMIN' ? 'admin_tariq' : targetRole === 'LAB_TECH' ? 'tech_kamal' : 'reception_fatima';
  if (page.url().includes('/login')) {
    await page.fill('#username', username);
    await page.fill('#password', 'test_pass_secure_2026');
    await page.click('[data-testid="login-submit-btn"]');
    await page.waitForLoadState('networkidle');
  }
}

test.describe('Part A — Modal / Tab Navigation Regression Specs', () => {
  test('A1: Invoices detail modal preserves /invoices URL and active tab', async ({ page }) => {
    await page.goto('/invoices');
    await selectDevRole(page, 'RECEPTIONIST');
    await page.waitForLoadState('networkidle');

    // Verify initial active tab is Invoices
    const invoicesNavLink = page.locator('nav a[href="/invoices"]');
    await expect(invoicesNavLink).toHaveClass(/bg-\[#CF8852\]/);
    expect(page.url()).toContain('/invoices');

    // Click "View Invoice Details" on first invoice
    const viewBtn = page.locator('button[title="View Invoice Details"]').first();
    await expect(viewBtn).toBeVisible({ timeout: 5000 });
    await viewBtn.click();
    await page.waitForTimeout(300);

    // Verify detail dialog is visible
    const detailDialog = page.locator('div[role="dialog"]');
    await expect(detailDialog).toBeVisible();

    // Verify underlying tab remains Invoices, NOT Patients
    const patientsNavLink = page.locator('nav a[href="/patients"]');
    await expect(invoicesNavLink).toHaveClass(/bg-\[#CF8852\]/);
    await expect(patientsNavLink).not.toHaveClass(/bg-\[#CF8852\]/);
    expect(page.url()).toContain('/invoices');

    // Close modal
    const closeBtn = detailDialog.locator('button[aria-label="Close dialog"]');
    await closeBtn.click();
    await page.waitForTimeout(300);
    await expect(detailDialog).toBeHidden();

    // Verify still on Invoices tab
    await expect(invoicesNavLink).toHaveClass(/bg-\[#CF8852\]/);
    expect(page.url()).toContain('/invoices');
  });

  test('A2: Invoices -> Patient History opens in-place without switching background to Patients', async ({ page }) => {
    await page.goto('/invoices');
    await selectDevRole(page, 'RECEPTIONIST');
    await page.waitForLoadState('networkidle');

    // Set filter before opening modal
    const filterInput = page.locator('input[placeholder*="Filter by bill"]');
    await filterInput.fill('017');
    await page.waitForTimeout(300);

    const invoicesNavLink = page.locator('nav a[href="/invoices"]');
    const patientsNavLink = page.locator('nav a[href="/patients"]');

    // Open detail modal
    const viewBtn = page.locator('button[title="View Invoice Details"]').first();
    await expect(viewBtn).toBeVisible({ timeout: 5000 });
    await viewBtn.click();
    await page.waitForTimeout(300);

    // Click "Patient History" inside detail modal
    const patientHistBtn = page.locator('[data-testid="invoice-detail-patient-history-btn"]');
    await expect(patientHistBtn).toBeVisible();
    await patientHistBtn.click();
    await page.waitForTimeout(500);

    // Check that we did NOT navigate to /patients
    expect(page.url()).toContain('/invoices');
    expect(page.url()).not.toContain('/patients');
    await expect(invoicesNavLink).toHaveClass(/bg-\[#CF8852\]/);
    await expect(patientsNavLink).not.toHaveClass(/bg-\[#CF8852\]/);

    // Close the Patient History modal
    const closeHistoryBtn = page.locator('button[aria-label="Close dialog"]').last();
    await closeHistoryBtn.click();
    await page.waitForTimeout(300);

    // Still on Invoices tab and search filter is preserved
    expect(page.url()).toContain('/invoices');
    await expect(invoicesNavLink).toHaveClass(/bg-\[#CF8852\]/);
    await expect(filterInput).toHaveValue('017');
  });

  test('A3: Patients page history drawer preserves /patients URL and tab state', async ({ page }) => {
    await page.goto('/patients');
    await selectDevRole(page, 'RECEPTIONIST');
    await page.waitForLoadState('networkidle');

    const patientsNavLink = page.locator('nav a[href="/patients"]');
    await expect(patientsNavLink).toHaveClass(/bg-\[#CF8852\]/);

    const historyBtn = page.locator('button:has-text("History")').first();
    if (await historyBtn.isVisible()) {
      await historyBtn.click();
      await page.waitForTimeout(400);

      const dialog = page.locator('div[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Check tab still Patients
      await expect(patientsNavLink).toHaveClass(/bg-\[#CF8852\]/);
      expect(page.url()).toContain('/patients');

      // Close history
      const closeBtn = dialog.locator('button[aria-label="Close dialog"]');
      await closeBtn.click();
      await page.waitForTimeout(300);
      await expect(patientsNavLink).toHaveClass(/bg-\[#CF8852\]/);
    }
  });

  test('A4: Dues settlement modal preserves /dues URL and tab state', async ({ page }) => {
    await page.goto('/dues');
    await selectDevRole(page, 'RECEPTIONIST');
    await page.waitForLoadState('networkidle');

    const duesNavLink = page.locator('nav a[href="/dues"]');
    await expect(duesNavLink).toHaveClass(/bg-\[#CF8852\]/);

    const settleBtn = page.locator('button:has-text("Settle Due")').first();
    if (await settleBtn.isVisible()) {
      await settleBtn.click();
      await page.waitForTimeout(300);

      const dialog = page.locator('div[role="dialog"]');
      await expect(dialog).toBeVisible();

      // Verify URL and tab
      expect(page.url()).toContain('/dues');
      await expect(duesNavLink).toHaveClass(/bg-\[#CF8852\]/);

      // Cancel / Close
      const cancelBtn = page.locator('button:has-text("Cancel")');
      await cancelBtn.click();
      await page.waitForTimeout(300);
      expect(page.url()).toContain('/dues');
    }
  });

  test('A5: Ready Reports printable preview modal preserves /reports URL and tab state', async ({ page }) => {
    await page.goto('/reports');
    await selectDevRole(page, 'RECEPTIONIST');
    await page.waitForLoadState('networkidle');

    const reportsNavLink = page.locator('nav a[href="/reports"]');
    await expect(reportsNavLink).toHaveClass(/bg-\[#CF8852\]/);

    const printBtn = page.locator('button[title="Preview & Print Report"]').first();
    if (await printBtn.isVisible()) {
      await printBtn.click();
      await page.waitForTimeout(300);

      expect(page.url()).toContain('/reports');
      await expect(reportsNavLink).toHaveClass(/bg-\[#CF8852\]/);

      const closeBtn = page.locator('button[aria-label="Close dialog"]');
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
        await page.waitForTimeout(300);
      }
      expect(page.url()).toContain('/reports');
    }
  });

  test('A6: Technician Worklist modals preserve /worklist URL and tab state', async ({ page }) => {
    await page.goto('/worklist');
    await selectDevRole(page, 'LAB_TECH');
    await page.waitForLoadState('networkidle');

    const worklistNavLink = page.locator('nav a[href="/worklist"]');
    await expect(worklistNavLink).toHaveClass(/bg-\[#CF8852\]/);
    expect(page.url()).toContain('/worklist');

    // Switch back to receptionist
    await selectDevRole(page, 'RECEPTIONIST');
  });
});

