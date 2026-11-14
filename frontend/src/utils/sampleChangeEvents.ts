/**
 * Prompt 12: tell the rest of the app that a sample status changed (Sample Taken, Reject/Spoil).
 * The Invoice screens subscribe and refetch, so the sample status shows without a manual reload.
 * Cross-user changes (a technician elsewhere) are covered by focus refetch plus a slow poll while
 * an invoice detail is open (see InvoicesPage).
 */
export const SAMPLE_CHANGED_EVENT = 'medscope:sample-changed';

export function announceSampleChange(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(SAMPLE_CHANGED_EVENT));
}

export function subscribeSampleChange(cb: () => void): () => void {
  window.addEventListener(SAMPLE_CHANGED_EVENT, cb);
  return () => window.removeEventListener(SAMPLE_CHANGED_EVENT, cb);
}

/** Prompt 13: cancellation request / approval / disbursement fire the same refresh event (one mechanism). */
export const announceInvoiceChange = announceSampleChange;
