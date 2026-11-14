import type { PaymentChannel } from '../types';

/**
 * Prompt 10E Part 4: the payment channel list used by every payment / refund form.
 * Values are exactly the backend channels (backend/app/core/payment_channels.py).
 * "Card" is POS_CARD (the old frontend value CARD is gone). OTHER needs a typed channel name.
 */
export const PAYMENT_CHANNEL_OPTIONS: { value: PaymentChannel; label: string }[] = [
  { value: 'CASH', label: 'Cash' },
  { value: 'BKASH', label: 'bKash' },
  { value: 'NAGAD', label: 'Nagad' },
  { value: 'ROCKET', label: 'Rocket' },
  { value: 'POS_CARD', label: 'Card' },
  { value: 'BANK_TRANSFER', label: 'Bank Transfer' },
  { value: 'OTHER', label: 'Other (type the name)' },
];

export const channelLabel = (method?: string | null, detail?: string | null): string => {
  if (!method) return '';
  if (method === 'OTHER') return detail ? `Other (${detail})` : 'Other';
  return PAYMENT_CHANNEL_OPTIONS.find((o) => o.value === method)?.label || method;
};

/** OTHER requires a typed channel name (at least 2 characters), as the backend enforces. */
export const isChannelDetailMissing = (channel: string, detail: string): boolean =>
  channel === 'OTHER' && detail.trim().length < 2;

/**
 * Prompt 10E Part 5: preview of the backend urgent-fee rule (backend is the source of truth):
 * fee = max(100, round(20% of the line's list price)), whole taka, never discounted.
 */
export const URGENT_FEE_MINIMUM = 100;
export const urgentFeePreview = (price: number): number =>
  Math.max(URGENT_FEE_MINIMUM, Math.round(Math.max(0, price) * 0.2));
