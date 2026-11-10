import { PaymentStatus, RefundStatus } from '../types';

export function formatPaymentStatus(
  status?: string | PaymentStatus,
  paidAmount?: number,
  dueAmount?: number
): string {
  if (paidAmount !== undefined && dueAmount !== undefined) {
    if (dueAmount === 0 && (paidAmount > 0 || status === 'PAID')) return 'Paid';
    if (paidAmount === 0) return 'Unpaid';
    if (paidAmount > 0 && dueAmount > 0) return 'Partial Due';
  }
  if (!status) return 'Unpaid';
  const s = String(status).toUpperCase();
  if (s === 'PAID') return 'Paid';
  if (s === 'PARTIAL' || s === 'PARTLY_PAID') return 'Partial Due';
  if (s === 'DUE' || s === 'UNPAID') return 'Unpaid';
  if (s === 'REFUNDED') return 'Refunded';
  return s;
}

export function formatRefundStatus(status?: string | RefundStatus): string {
  if (!status) return 'No Refund';
  const s = String(status).toUpperCase();
  switch (s) {
    case 'NO_REFUND':
      return 'No Refund';
    case 'REFUND_PENDING':
      return 'Refund Pending';
    case 'REFUND_APPROVED':
      return 'Refund Approved (Pending Payout)';
    case 'PARTIALLY_REFUNDED':
      return 'Partially Refunded';
    case 'FULLY_REFUNDED':
      return 'Fully Refunded';
    case 'REFUND_REJECTED':
      return 'Refund Rejected';
    default:
      return s;
  }
}

export function getPaymentStatusBadgeVariant(
  status?: string | PaymentStatus,
  paidAmount?: number,
  dueAmount?: number
): 'success' | 'warning' | 'danger' | 'neutral' {
  const formatted = formatPaymentStatus(status, paidAmount, dueAmount);
  if (formatted === 'Paid') return 'success';
  if (formatted === 'Partial Due') return 'warning';
  if (formatted === 'Unpaid') return 'danger';
  return 'neutral';
}

export function getRefundStatusBadgeVariant(
  status?: string | RefundStatus
): 'success' | 'warning' | 'danger' | 'neutral' | 'info' {
  const s = String(status || '').toUpperCase();
  switch (s) {
    case 'FULLY_REFUNDED':
      return 'danger';
    case 'PARTIALLY_REFUNDED':
      return 'warning';
    case 'REFUND_APPROVED':
      return 'warning';
    case 'REFUND_PENDING':
      return 'info';
    case 'REFUND_REJECTED':
      return 'neutral';
    case 'NO_REFUND':
    default:
      return 'neutral';
  }
}

