/**
 * MedScope DCMS — Role Home Route Resolver
 *
 * Directs authenticated staff to their designated initial operational workbench:
 * - RECEPTIONIST / CASHIER: Invoices workbench (/invoices)
 * - LAB_TECH: Technician Worklist (/worklist)
 * - ADMIN / OWNER: Executive Operations Dashboard (/dashboard)
 */

export function getRoleHomeRoute(role?: string | null): string {
  switch (role) {
    case 'RECEPTIONIST':
    case 'CASHIER':
      return '/invoices';
    case 'LAB_TECH':
      return '/worklist';
    case 'ADMIN':
    case 'OWNER':
    default:
      return '/dashboard';
  }
}

