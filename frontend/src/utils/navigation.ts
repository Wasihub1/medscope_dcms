/**
 * MedScope DCMS — Home Route Resolver
 *
 * Prompt 10D (ADL-033): every login lands on the Dashboard, whatever the role.
 * The Dashboard shows each role only what it may see, plus a link to its main work page.
 * The role argument is kept so existing call sites stay unchanged.
 */

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getRoleHomeRoute(_role?: string | null): string {
  return '/dashboard';
}
