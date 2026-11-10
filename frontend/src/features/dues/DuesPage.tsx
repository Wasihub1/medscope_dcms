import React, { useState, useEffect } from 'react';
import {
  CreditCard,
  Search,
  Phone,
  AlertCircle,
  CheckCircle2,
  Printer,
  Calendar,
  ArrowRight,
} from 'lucide-react';
import { api } from '../../api/client';
import { InvoiceSummary, Invoice } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { ThermalReceiptModal } from '../../components/common/ThermalReceiptModal';
import { formatPaymentStatus, getPaymentStatusBadgeVariant } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

export const DuesPage: React.FC = () => {
  const [dueInvoices, setDueInvoices] = useState<InvoiceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  // Settlement Modal State
  const [settleModalOpen, setSettleModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [settleAmount, setSettleAmount] = useState<number>(0);
  const [paymentChannel, setPaymentChannel] = useState<string>('CASH');
  const [tenderedAmount, setTenderedAmount] = useState<number>(0);
  const [referenceNo, setReferenceNo] = useState<string>('');
  const [submittingPayment, setSubmittingPayment] = useState(false);

  // Receipt Modal
  const [receiptOpen, setReceiptOpen] = useState(false);

  const { showToast } = useToast();

  const fetchDues = async () => {
    try {
      setLoading(true);
      const dues = await api.getDues(searchTerm.trim() || undefined);
      setDueInvoices(dues);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load dues', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDues();
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const handleOpenSettle = async (id: string) => {
    try {
      const inv = await api.getInvoice(id);
      setSelectedInvoice(inv);
      setSettleAmount(inv.due_amount);
      setTenderedAmount(inv.due_amount);
      setPaymentChannel('CASH');
      setReferenceNo('');
      setSettleModalOpen(true);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load invoice', message: err.message });
    }
  };

  const handleConfirmSettlement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    if (settleAmount <= 0 || settleAmount > selectedInvoice.due_amount) {
      showToast({ type: 'error', title: 'Invalid Amount', message: 'Amount cannot exceed the pending due.' });
      return;
    }

    setSubmittingPayment(true);
    try {
      await api.createPayment({
        invoice_id: selectedInvoice.id,
        amount: settleAmount,
        channel: paymentChannel,
        reference_no: referenceNo || undefined,
        notes: 'Reception desk due settlement',
      });

      showToast({
        type: 'success',
        title: 'Due Settled!',
        message: `৳${settleAmount} collected for invoice ${selectedInvoice.invoice_number}.`,
      });

      setSettleModalOpen(false);
      const updated = await api.getInvoice(selectedInvoice.id);
      setSelectedInvoice(updated);
      setReceiptOpen(true);
      fetchDues();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Settlement Failed', message: err.message });
    } finally {
      setSubmittingPayment(false);
    }
  };

  const totalOutstanding = dueInvoices.reduce((sum, inv) => sum + inv.due_amount, 0);
  const changeAmount = paymentChannel === 'CASH' ? Math.max(0, tenderedAmount - settleAmount) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Outstanding Dues & Settlement</h1>
          <p className="text-xs text-[#6D6A60]">
            Review all unpaid balances, collect pending amounts, and clear accounts before report release.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by invoice #, patient, phone..."
              className="text-xs bg-transparent border-none outline-none w-52 text-[#1B1B0E]"
            />
          </div>
        </div>
      </div>

      {/* Summary KPI Banner */}
      <div className="bg-[#FEF7EC] border border-[#FBE0B2] rounded-2xl p-4.5 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 bg-white border border-[#FBE0B2] text-[#D9820B] rounded-xl shadow-xs">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <span className="text-xs font-semibold text-[#8A5608] block">Total Uncollected Receivables</span>
            <span className="text-2xl font-extrabold text-[#1B1B0E]">৳{totalOutstanding.toLocaleString()}</span>
          </div>
        </div>
        <div className="text-right">
          <span className="text-xs font-bold text-[#8A5608] px-2.5 py-1 bg-white border border-[#FBE0B2] rounded-lg">
            {dueInvoices.length} Invoices with Due
          </span>
        </div>
      </div>

      {/* Dues List Card */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Invoice #</th>
                <th className="pb-3">Bill Date</th>
                <th className="pb-3">Patient Name</th>
                <th className="pb-3">Phone</th>
                <th className="pb-3 text-right">Net Bill</th>
                <th className="pb-3 text-right">Paid</th>
                <th className="pb-3 text-right">Pending Due</th>
                <th className="pb-3 text-center">Status</th>
                <th className="pb-3 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {dueInvoices.length === 0 && !loading && (
                <tr>
                  <td colSpan={9} className="py-10 text-center text-[#8E8A7E]">
                    <CheckCircle2 className="w-7 h-7 text-[#2D8A39] mx-auto mb-1.5 opacity-80" />
                    No outstanding dues found! All billing accounts are balanced.
                  </td>
                </tr>
              )}
              {dueInvoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-[#F4F3F0] transition-colors">
                  <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{inv.invoice_number}</td>
                  <td className="py-3 text-[#6D6A60]">{new Date(inv.created_at).toLocaleDateString('en-GB')}</td>
                  <td className="py-3 font-semibold text-[#1B1B0E]">{inv.patient_name}</td>
                  <td className="py-3 text-[#54524A]">{inv.patient_phone}</td>
                  <td className="py-3 text-right font-medium">৳{inv.net_amount.toLocaleString()}</td>
                  <td className="py-3 text-right text-[#1E6327] font-semibold">৳{inv.paid_amount.toLocaleString()}</td>
                  <td className="py-3 text-right font-bold text-[#9C2417]">৳{inv.due_amount.toLocaleString()}</td>
                  <td className="py-3 text-center">
                    <Badge variant={getPaymentStatusBadgeVariant(inv.payment_status, inv.paid_amount, inv.due_amount)} size="sm">
                      {formatPaymentStatus(inv.payment_status, inv.paid_amount, inv.due_amount)}
                    </Badge>
                  </td>
                  <td className="py-3 text-right pr-2">
                    <button
                      onClick={() => handleOpenSettle(inv.id)}
                      className="px-3 py-1.5 bg-[#CF8852] hover:bg-[#B7703B] text-white font-bold rounded-lg shadow-2xs transition-colors cursor-pointer text-xs inline-flex items-center gap-1.5"
                    >
                      <span>Settle Due</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Settle Due Modal */}
      <Modal
        isOpen={settleModalOpen}
        onClose={() => setSettleModalOpen(false)}
        title={selectedInvoice ? `Settle Balance — ${selectedInvoice.invoice_number}` : ''}
        subtitle={selectedInvoice ? `Patient: ${selectedInvoice.patient_name} | Contact: ${selectedInvoice.patient_phone}` : ''}
        maxWidth="md"
      >
        {selectedInvoice && (
          <form onSubmit={handleConfirmSettlement} className="space-y-4 text-xs">
            {/* Amount details */}
            <div className="bg-[#FAF3EC] border border-[#E6C4A7] p-3 rounded-xl grid grid-cols-3 gap-2 text-center">
              <div>
                <span className="text-[#96572A] block text-[11px]">Net Amount</span>
                <span className="font-bold text-[#1B1B0E]">৳{selectedInvoice.net_amount.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-[#1E6327] block text-[11px]">Already Paid</span>
                <span className="font-bold text-[#1E6327]">৳{selectedInvoice.paid_amount.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-[#9C2417] block text-[11px]">Current Due</span>
                <span className="font-bold text-[#9C2417]">৳{selectedInvoice.due_amount.toLocaleString()}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[#54524A] font-semibold mb-1">Payment Method *</label>
                <select
                  value={paymentChannel}
                  onChange={(e) => setPaymentChannel(e.target.value)}
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-semibold"
                >
                  <option value="CASH">Cash</option>
                  <option value="BKASH">bKash</option>
                  <option value="NAGAD">Nagad</option>
                  <option value="ROCKET">Rocket</option>
                  <option value="CARD">Debit / Credit Card</option>
                  <option value="BANK_TRANSFER">Bank Transfer</option>
                </select>
              </div>

              <div>
                <label className="block text-[#54524A] font-semibold mb-1">Collecting Amount (৳) *</label>
                <input
                  type="number"
                  min="1"
                  max={selectedInvoice.due_amount}
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
              <button
                type="button"
                onClick={() => setSettleModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingPayment}
                className="px-5 py-2 text-xs font-bold bg-[#1E6327] hover:bg-[#2D8A39] text-white rounded-xl shadow-xs transition-colors"
              >
                {submittingPayment ? 'Processing...' : 'Collect & Issue Receipt'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Thermal Receipt Modal on Complete */}
      <ThermalReceiptModal
        isOpen={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        invoice={selectedInvoice}
        isReprint={false}
      />
    </div>
  );
};

