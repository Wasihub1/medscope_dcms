import { test, expect } from '@playwright/test';
import { loginAs, openAs } from './support/auth';

/**
 * NOTE (Prompt 10D): this suite CREATES records (patients, doctors, referrers, invoices).
 * It must only be run against a disposable database, never the main development DB.
 * Login: one login = one fixed role; every login lands on /dashboard (see e2e/support/auth.ts).
 */
test.describe('MedScope Receptionist Corrections E2E Suite (Prompt 04, updated Prompt 10D)', () => {
  test.beforeEach(async ({ page }) => {
    // Sign in as the receptionist; every login lands on the Dashboard
    await loginAs(page, 'RECEPTIONIST');
  });

  // -------------------------------------------------------------------------
  // Item 08 & 09: Inline Global Search & Ctrl+F shortcut (No Modal, No Ctrl+K)
  // -------------------------------------------------------------------------
  test('08 & 09: Inline global search and Ctrl+F keyboard shortcut', async ({ page }) => {
    // Prompt 10D: login lands on /dashboard, which has the global header search
    const searchInput = page.locator('#medscope-global-search');
    await expect(searchInput).toBeVisible();

    // Trigger Ctrl+F on the page
    await page.keyboard.press('Control+f');
    await expect(searchInput).toBeFocused();

    // Type query to trigger anchored dropdown
    await searchInput.fill('Fatima');
    const dropdown = page.locator('[data-testid="global-search-dropdown"]');
    await expect(dropdown).toBeVisible({ timeout: 5000 });

    // Press Escape to dismiss
    await page.keyboard.press('Escape');
    await expect(dropdown).toBeHidden();
  });

  // -------------------------------------------------------------------------
  // Item 02: Business Day Close RBAC (Receptionist Disabled, Admin Allowed)
  // -------------------------------------------------------------------------
  test('02: Business Day close action permissions', async ({ page }) => {
    await page.goto('/business-day');
    await page.waitForLoadState('networkidle');

    // Receptionist: close button must be disabled/restricted
    const receptionistDisabledBtn = page.locator('[data-testid="receptionist-close-day-disabled"]');
    await expect(receptionistDisabledBtn).toBeVisible();
    await expect(receptionistDisabledBtn).toBeDisabled();

    // Admin: sign in as the Admin account (no role switching exists any more)
    await openAs(page, 'ADMIN', '/business-day');
    const adminCloseBtn = page.locator('[data-testid="admin-close-day-btn"]');
    await expect(adminCloseBtn).toBeVisible();
    await expect(adminCloseBtn).toBeEnabled();
  });

  // -------------------------------------------------------------------------
  // Item 01, 03, 04, 05, 06, 07: New Invoice Flow
  // -------------------------------------------------------------------------
  test('01, 03, 04, 05, 06, 07: Complete Intake Workflow with Preview, Discounts, and Dual-Copy Print', async ({ page }) => {
    await page.goto('/invoices/new');
    await page.waitForLoadState('networkidle');

    // --- Item 01: Create Patient & Distinct Prescriber / Referrer ---
    const timestamp = Date.now();

    // 1. Register Patient inline
    await page.locator('[data-testid="new-patient-btn"]').click();
    await page.locator('[data-testid="patient-form-fullname"]').fill(`E2E Test Patient ${timestamp}`);
    await page.locator('[data-testid="patient-form-phone"]').fill(`017${(timestamp % 10000000).toString().padStart(8, '0')}`);
    await page.locator('[data-testid="save-patient-submit-btn"]').click();
    await expect(page.locator('[data-testid="selected-patient-name"]')).toContainText(`E2E Test Patient ${timestamp}`);

    // Prompt 10E Part 3: age and gender for the visit (Finalize requires both; no silent default)
    await page.locator('[data-testid="visit-age-input"]').fill('34');
    await page.locator('[data-testid="visit-age-unit"]').selectOption('years');
    await page.locator('[data-testid="visit-gender-select"]').selectOption('Male');

    // 2. Add Prescribing Doctor with write-only commission
    await page.locator('[data-testid="add-doctor-btn"]').click();
    await page.locator('[data-testid="doctor-form-name"]').fill(`Dr. Playwright Prescriber ${timestamp}`);
    await page.locator('[data-testid="doctor-commission-rate"]').fill('20');
    await page.locator('[data-testid="save-doctor-submit-btn"]').click();
    await expect(page.locator('[data-testid="selected-prescriber-name"]')).toContainText(`Dr. Playwright Prescriber ${timestamp}`);

    // 3. Add Commercial Referrer with write-only commission
    await page.locator('[data-testid="add-referrer-btn"]').click();
    await page.locator('[data-testid="referrer-form-name"]').fill(`Agent Partner ${timestamp}`);
    await page.locator('[data-testid="referrer-commission-rate"]').fill('15');
    await page.locator('[data-testid="save-referrer-submit-btn"]').click();
    await expect(page.locator('[data-testid="selected-referrer-name"]')).toContainText(`Agent Partner ${timestamp}`);

    // --- Item 03: Test Catalog Autocomplete Deduplication Filtering ---
    // Select first test
    const firstTest = page.locator('[data-testid^="catalog-test-"]').first();
    const testTestId = await firstTest.getAttribute('data-testid');
    await firstTest.click();

    // Verify test was added to selected lines
    await expect(page.locator('[data-testid^="selected-line-"]')).toHaveCount(1);

    // Verify test is REMOVED from the available catalog (deduplicated by test id)
    const matchingTestInCatalog = page.locator(`[data-testid="${testTestId}"]`);
    await expect(matchingTestInCatalog).toHaveCount(0);

    // --- Item 04: Distinct % and ৳ Line Discount Inputs Dynamic Synchronization ---
    const pctInput = page.locator('[data-testid^="line-discount-percent-"]').first();
    const amtInput = page.locator('[data-testid^="line-discount-fixed-"]').first();
    await expect(pctInput).toBeVisible();
    await expect(amtInput).toBeVisible();
    await expect(pctInput).toHaveValue('');
    await expect(amtInput).toHaveValue('');

    // Entering 50% calculates equivalent Taka amount
    await pctInput.fill('50');
    const amtVal50 = await amtInput.inputValue();
    expect(Number(amtVal50)).toBeGreaterThan(0);

    // Entering fixed amount calculates equivalent percentage
    await amtInput.fill('100');
    const pctVal100 = await pctInput.inputValue();
    expect(Number(pctVal100)).toBeGreaterThan(0);

    // Resetting fixed amount to empty resets discount
    await amtInput.fill('');
    await expect(pctInput).toHaveValue('');
    await expect(amtInput).toHaveValue('');

    // --- Item 05: Default Paid Amount is ৳0 (Unpaid) ---
    const paidInput = page.locator('[data-testid="paid-amount-input"]');
    await expect(paidInput).toHaveValue('0');
    await expect(page.locator('[data-testid="due-status-indicator"]')).toContainText('(Unpaid)');

    // Test Quick Full Pay button
    await page.locator('[data-testid="full-pay-btn"]').click();
    const fullVal = await paidInput.inputValue();
    expect(Number(fullVal)).toBeGreaterThan(0);

    // Reset to Zero
    // Prompt 10E Part 4: the channel list is exactly the backend values; OTHER asks for a name
    const methodSelect = page.locator('[data-testid="payment-method-select"]');
    await expect(methodSelect.locator('option')).toHaveText(['Cash', 'bKash', 'Nagad', 'Rocket', 'Card', 'Bank Transfer', 'Other (type the name)']);
    await methodSelect.selectOption('OTHER');
    await expect(page.locator('[data-testid="channel-detail-input"]')).toBeVisible();
    await methodSelect.selectOption('CASH');

    await page.locator('[data-testid="zero-pay-btn"]').click();
    await expect(paidInput).toHaveValue('0');

    // --- Item 06: Generate Non-Final Preview -> Back & Correct -> Save ---
    await page.locator('[data-testid="generate-preview-btn"]').click();

    // Dual-Copy Modal preview must be open with Patient and Office copies
    const dualModal = page.locator('[data-testid="dual-copy-invoice-modal"]');
    await expect(dualModal).toBeVisible();
    await expect(page.locator('text=Patient Copy')).toBeVisible();
    await expect(page.locator('text=Office / Lab Copy')).toBeVisible();
    await expect(page.locator('[data-testid="invoice-draft-tag"]')).toContainText('Unsaved Draft');

    // Back & Correct preserves all inputs
    await page.locator('[data-testid="invoice-preview-back-btn"]').click();
    await expect(dualModal).toBeHidden();
    await expect(page.locator('[data-testid="selected-patient-name"]')).toContainText(`E2E Test Patient ${timestamp}`);
    await expect(page.locator('[data-testid^="selected-line-"]')).toHaveCount(1);

    // Prompt 10D: Save Draft first (no invoice number, no operational effect) ...
    await page.locator('[data-testid="generate-preview-btn"]').click();
    await expect(dualModal).toBeVisible();
    await page.locator('[data-testid="invoice-preview-save-draft-btn"]').click();
    await expect(page.locator('[data-testid="invoice-draft-tag"]')).toContainText('Saved Draft DRAFT-', { timeout: 8000 });

    // ... then Finalize, which assigns the real invoice number
    await page.locator('[data-testid="invoice-preview-finalize-btn"]').click();
    await expect(page.locator('text=Diagnostic Bill #')).toBeVisible({ timeout: 8000 });
    await page.locator('[data-testid="invoice-preview-close-btn"]').click();

    // --- Item 07: Form is reset to clean state ---
    await expect(page.locator('[data-testid="selected-patient-name"]')).toHaveCount(0);
    await expect(page.locator('[data-testid^="selected-line-"]')).toHaveCount(0);
    await expect(paidInput).toHaveValue('0');
  });

  // -------------------------------------------------------------------------
  // Item 10 & 11 & 14: Invoices List, Print, Standard Labels & Refund Status
  // -------------------------------------------------------------------------
  test('10, 11, 14: Invoices list, reprint action, standard labels, and refund status', async ({ page }) => {
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');

    // Verify table has Payment and Refund Status columns
    await expect(page.locator('th:has-text("Payment")')).toBeVisible();
    await expect(page.locator('th:has-text("Refund Status")')).toBeVisible();

    // Verify standardized status labels exist (Unpaid, Partial Due, or Paid)
    const statusBadges = page.locator('table tbody td:nth-child(8) span');
    if ((await statusBadges.count()) > 0) {
      const firstStatus = await statusBadges.first().textContent();
      expect(['Unpaid', 'Partial Due', 'Paid', 'Draft']).toContain(firstStatus?.trim());
    }

    // Verify User-Friendly Status Filter Dropdown with All 6 Events
    const filterSelect = page.locator('select');
    await expect(filterSelect).toBeVisible();
    for (const opt of ['All Payments', 'Paid', 'Unpaid', 'Partial Due', 'Partially Refunded', 'Fully Refunded']) {
      await filterSelect.selectOption(opt);
      await page.waitForTimeout(200);
      const rowCount = await page.locator('table tbody tr').count();
      expect(rowCount).toBeGreaterThan(0);
    }
    await filterSelect.selectOption('All Payments');

    // Verify Reprint / Print button opens Dual Copy Printable Modal without page navigation
    const printBtn = page.locator('table tbody button[title*="Reprint"]').first();
    if (await printBtn.isVisible()) {
      await printBtn.click();
      const dualModal = page.locator('[data-testid="dual-copy-invoice-modal"]');
      await expect(dualModal).toBeVisible({ timeout: 5000 });
      await expect(page.locator('text=Patient Copy')).toBeVisible();
      await expect(page.locator('text=Office / Lab Copy')).toBeVisible();
      await expect(page.locator('[data-testid="invoice-print-btn"]')).toBeVisible();

      // Close modal; page URL must remain /invoices
      await page.locator('[data-testid="invoice-preview-close-btn"]').click();
      await expect(page).toHaveURL(/\/invoices/);
    }
  });

  // -------------------------------------------------------------------------
  // Item 12: Patient History -> Old Invoice without route navigation
  // -------------------------------------------------------------------------
  test('12: Patient History nested invoice view preserves Patients route and context', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Open first patient's history
    const historyBtn = page.locator('table tbody button[title*="History"]').first();
    if (await historyBtn.isVisible()) {
      await historyBtn.click();
      await expect(page.locator('text=Patient Ledger & Clinical History')).toBeVisible({ timeout: 5000 });

      // Click on Invoices tab
      const invoiceTab = page.locator('button:has-text("Invoices & Tests")');
      await invoiceTab.click();

      // If an invoice exists in history, click View
      const viewNestedBtn = page.locator('[data-testid^="view-nested-invoice-"]').first();
      if (await viewNestedBtn.isVisible()) {
        await viewNestedBtn.click();

        // Dual-copy invoice overlay opens
        const dualModal = page.locator('[data-testid="dual-copy-invoice-modal"]');
        await expect(dualModal).toBeVisible({ timeout: 5000 });

        // Close the invoice overlay
        await page.locator('[data-testid="invoice-preview-close-btn"]').click();
        await expect(dualModal).toBeHidden();

        // INVARIANT: User must STILL be on /patients, with Patient History modal visible!
        await expect(page).toHaveURL(/\/patients/);
        await expect(page.locator('text=Patient Ledger & Clinical History')).toBeVisible();
      }
    }
  });

  // -------------------------------------------------------------------------
  // Key Responsive Viewport Check (Mobile 375x667)
  // -------------------------------------------------------------------------
  test('Responsive Viewport: Mobile rendering and accessible layout', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');

    const searchInput = page.locator('#medscope-global-search');
    await expect(searchInput).toBeVisible();

    const tableContainer = page.locator('.overflow-x-auto');
    await expect(tableContainer).toBeVisible();
  });
});
