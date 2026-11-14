import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Invoice } from '../../types';
import { Modal } from './Modal';
import { ThermalReceiptModal } from './ThermalReceiptModal';
import { useToast } from '../../context/ToastContext';
import { PAYMENT_CHANNEL_OPTIONS, isChannelDetailMissing } from '../../utils/paymentChannels';

/**
 * The one "take payment against a due" modal (extracted from the Dues page in Prompt 17 so the report
 * handover screen reuses exactly the same flow, endpoint, receipt and validation).
 * Mount it with the invoice id; it loads the invoice, collects through POST /payments and shows the receipt.
 * onPaid runs after a successful payment (the caller refreshes its list); onClose closes the whole thing.
 */
interface Props {
  invoiceId: number | string;
  onClose: () => void;
  onPaid: () => void;
}

export const SettleDueModal: React.FC<Props> = ({ invoiceId, onClose, onPaid }) => {
  const { showToast } = useToast();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [settleAmount, setSettleAmount] = useState<number>(0);
  const [paymentChannel, setPaymentChannel] = useState<string>('CASH');
  const [channelDetail, setChannelDetail] = useState<string>('');
  const [tenderedAmount, setTenderedAmount] = useState<number>(0);
  const [referenceNo, setReferenceNo] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .getInvoice(invoiceId)
      .then((inv) => {
        if (cancelled) return;
        setInvoice(inv);
        setSettleAmount(inv.due_amount);
        setTenderedAmount(inv.due_amount);
      })
      .catch((err: any) => {
        showToast({ type: 'error', title: 'Failed to load invoice', message: err.message });
        onClose();
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoiceId]);

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invoice) return;
    if (settleAmount <= 0 || settleAmount > invoice.due_amount) {
      showToast({ type: 'error', title: 'Invalid Amount', message: 'Amount cannot exceed the pending due.' });
      return;
    }
    if (isChannelDetailMissing(paymentChannel, channelDetail)) {
      showToast({ type: 'warning', title: 'Channel Name Required', message: 'Type the name of the payment channel for "Other".' });
      return;
    }
    setSubmitting(true);
    try {
      await api.createPayment({
        invoice_id: invoice.id,
        amount: settleAmount,
        channel: paymentChannel,
        channel_detail: paymentChannel === 'OTHER' ? channelDetail.trim() : undefined,
        reference_no: referenceNo || undefined,
        notes: 'Reception desk due settlement',
      });
      showToast({ type: 'success', title: 'Due Settled!', message: `৳${settleAmount} collected for invoice ${invoice.invoice_number}.` });
      const updated = await api.getInvoice(invoice.id);
      setInvoice(updated);
      setFormOpen(false);
      setReceiptOpen(true);
      onPaid();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Settlement Failed', message: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  const changeAmount = paymentChannel === 'CASH' ? Math.max(0, tenderedAmount - settleAmount) : 0;

  return (
    <>
      <Modal
        isOpen={formOpen && invoice !== null}
        onClose={onClose}
        title={invoice ? `Settle Balance — ${invoice.invoice_number}` : ''}
        subtitle={invoice ? `Patient: ${invoice.patient_name} | Contact: ${invoice.patient_phone}` : ''}
        maxWidth="md"
      >
        {invoice && (
          <form onSubmit={handleConfirm} className="space-y-4 text-xs">
            <div className="bg-[#FAF3EC] border border-[#E6C4A7] p-3 rounded-xl grid grid-cols-3 gap-2 text-center">
              <div>
                <span className="text-[#96572A] block text-[11px]">Net Amount</span>
                <span className="font-bold text-[#1B1B0E]">৳{invoice.net_amount.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-[#1E6327] block text-[11px]">Already Paid</span>
                <span className="font-bold text-[#1E6327]">৳{invoice.paid_amount.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-[#9C2417] block text-[11px]">Current Due</span>
                <span className="font-bold text-[#9C2417]">৳{invoice.due_amount.toLocaleString()}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[#54524A] font-semibold mb-1">Payment Method *</label>
                <select
                  data-testid="dues-payment-method-select"
                  value={paymentChannel}
                  onChange={(e) => setPaymentChannel(e.target.value)}
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-semibold"
                >
                  {PAYMENT_CHANNEL_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[#54524A] font-semibold mb-1">Collecting Amount (৳) *</label>
                <input
                  type="number"
                  min="1"
                  max={invoice.due_amount}
                  required
                  value={settleAmount}
                  onChange={(e) => {
                    const amt = Number(e.target.value);
                    setSettleAmount(amt);
                    if (paymentChannel === 'CASH') setTenderedAmount(amt);
                  }}
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-bold text-sm text-[#1E6327] text-right"
                />
              </div>
            </div>

            {paymentChannel === 'CASH' && (
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#E8E7E3]">
                <div>
                  <label className="block text-[#54524A] font-semibold mb-1">Tendered Cash (৳)</label>
                  <input
                    type="number"
                    min={settleAmount}
                    value={tenderedAmount}
                    onChange={(e) => setTenderedAmount(Number(e.target.value))}
                    className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-semibold text-right"
                  />
                </div>
                <div>
                  <label className="block text-[#54524A] font-semibold mb-1">Change Return</label>
                  <div className="p-2.5 bg-[#FAF3EC] border border-[#E6C4A7] rounded-xl font-bold text-right text-[#96572A]">
                    ৳{changeAmount.toLocaleString()}
                  </div>
                </div>
              </div>
            )}

            {paymentChannel === 'OTHER' && (
              <div>
                <label className="block text-[#54524A] font-semibold mb-1" htmlFor="dues-channel-detail-input">Channel Name *</label>
                <input
                  id="dues-channel-detail-input"
                  data-testid="dues-channel-detail-input"
                  type="text"
                  maxLength={100}
                  value={channelDetail}
                  onChange={(e) => setChannelDetail(e.target.value)}
                  placeholder="e.g. Upay, Cheque"
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
                />
              </div>
            )}

            {paymentChannel !== 'CASH' && (
              <div>
                <label className="block text-[#54524A] font-semibold mb-1">Reference / TrxID / Approval Code</label>
                <input
                  type="text"
                  value={referenceNo}
                  onChange={(e) => setReferenceNo(e.target.value)}
                  placeholder="e.g. bKash TrxID 8A09LK"
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
              <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors">
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-5 py-2 text-xs font-bold bg-[#1E6327] hover:bg-[#2D8A39] text-white rounded-xl shadow-xs transition-colors"
              >
                {submitting ? 'Processing...' : 'Collect & Issue Receipt'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      <ThermalReceiptModal
        isOpen={receiptOpen}
        onClose={() => {
          setReceiptOpen(false);
          onClose();
        }}
        invoice={invoice}
        isReprint={false}
      />
    </>
  );
};
