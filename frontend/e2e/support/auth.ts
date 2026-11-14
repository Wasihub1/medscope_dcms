import { expect, Page } from '@playwright/test';

/**
 * Prompt 10D — shared e2e login helper (replaces the stale `selectDevRole` name).
 *
 * One login = one fixed role, and every login lands on /dashboard. Specs sign in through the
 * real login form (#user / #pass, data-testid login-username / login-password) and then open
 * the page under test.
 *
 * Credentials: usernames are the existing development accounts. The password is NEVER stored in
 * code — it is read from the environment variable MEDSCOPE_E2E_PASSWORD (the owner's existing
 * development password). Example (PowerShell):
 *   $env:MEDSCOPE_E2E_PASSWORD = '<dev password>'; npx playwright test e2e/test_modal_regression.spec.ts
 */
export const E2E_USERS = {
  RECEPTIONIST: 'reception_fatima',
  CASHIER: 'cashier_fatima',
  ADMIN: 'admin_tariq',
  OWNER: 'owner_tariq',
  LAB_TECH: 'tech_kamal', // Hematology — Room 101 (Prompt 10E: worklists are room based)
} as const;

export type E2ERole = keyof typeof E2E_USERS;

export function e2ePassword(): string {
  const pwd = process.env.MEDSCOPE_E2E_PASSWORD;
  if (!pwd) {
    throw new Error(
      'MEDSCOPE_E2E_PASSWORD is not set. Set it to the development password before running the e2e specs (it is never stored in code).'
    );
  }
  return pwd;
}

/** Signs in through the login form and waits for the Dashboard landing page. */
export async function loginAs(page: Page, role: E2ERole): Promise<void> {
  await page.context().clearCookies();
  await page.goto('/login');
  await page.getByTestId('login-username').fill(E2E_USERS[role]);
  await page.getByTestId('login-password').fill(e2ePassword());
  await page.getByTestId('login-submit-btn').click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10000 });
}

/** Signs in, then opens the page under test. */
export async function openAs(page: Page, role: E2ERole, path: string): Promise<void> {
  await loginAs(page, role);
  await page.goto(path);
  await page.waitForLoadState('networkidle');
}
