import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Search,
  Printer,
  Eye,
  RotateCcw,
  CreditCard,
  Calendar,
  Filter,
  Receipt,
  CheckCircle2,
  AlertCircle,
  FileText,
} from 'lucide-react';
import { api } from '../../api/client';
import { InvoiceSummary, Invoice, PaymentStatus } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { DualCopyInvoiceModal } from '../../components/common/DualCopyInvoiceModal';
import { PatientHistoryModal } from '../../components/common/PatientHistoryModal';
import {
  formatPaymentStatus,
  formatRefundStatus,
  getPaymentStatusBadgeVariant,
  getRefundStatusBadgeVariant,
} from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

export const InvoicesPage: React.FC = () => {
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('All Payments');

  // Selected Detail Modal State
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  // Reprint State
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [isReprint, setIsReprint] = useState(false);

  // Pre-sample Refund Modal State
  const [refundModalOpen, setRefundModalOpen] = useState(false);
  const [refundLineId, setRefundLineId] = useState<string>('');
  const [refundAmount, setRefundAmount] = useState<number>(0);
  const [refundReason, setRefundReason] = useState<string>('');
  const [submittingRefund, setSubmittingRefund] = useState(false);

  // Settle Due Modal State
  const [settleModalOpen, setSettleModalOpen] = useState(false);
  const [settleAmount, setSettleAmount] = useState<number>(0);
  const [settleChannel, setSettleChannel] = useState<string>('CASH');
  const [settleRef, setSettleRef] = useState<string>('');

  // Disburse Refund Modal State (FIX 4)
  const [disburseModalOpen, setDisburseModalOpen] = useState(false);
  const [selectedRefundForDisburse, setSelectedRefundForDisburse] = useState<any>(null);
  const [disburseMethod, setDisburseMethod] = useState<string>('CASH');
  const [disburseRef, setDisburseRef] = useState<string>('');
  const [submittingDisburse, setSubmittingDisburse] = useState(false);

  // In-place Patient History Modal state (preserves Invoices tab and filters)
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyPatientId, setHistoryPatientId] = useState<string | number | null>(null);

  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const idParam = searchParams.get('id');
  const searchParam = searchParams.get('search');

  const { showToast } = useToast();

  const handleCloseDetail = () => {
    setDetailModalOpen(false);
    if (idParam) {
      const next = new URLSearchParams(searchParams);
      next.delete('id');
      setSearchParams(next, { replace: true });
    }
  };

  useEffect(() => {
    if (searchParam) {
      setSearchTerm(searchParam);
    }
  }, [searchParam]);

  useEffect(() => {
    if (idParam) {
      handleOpenDetail(idParam);
    }
  }, [idParam]);

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (searchTerm.trim()) params.search = searchTerm.trim();
      if (statusFilter !== 'All Payments' && statusFilter !== 'ALL') params.payment_status = statusFilter;
      const res = await api.getInvoices(params);
      setInvoices(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to fetch invoices', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchInvoices();
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm, statusFilter]);

  const handleOpenDetail = async (id: string) => {
    try {
      const inv = await api.getInvoice(id);
      setSelectedInvoice(inv);
      setDetailModalOpen(true);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load details', message: err.message });
    }
  };

  const handleReprint = async (id: string) => {
    try {
      const res = await api.reprintInvoice(id, 'Receptionist duplicate reprint request');
      setSelectedInvoice(res);
      setIsReprint(true);
      setReceiptOpen(true);
      showToast({
        type: 'info',
        title: 'Receipt Ready',
        message: `Invoice #${res.invoice_number} loaded for duplicate printing.`,
      });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Reprint Failed', message: err.message });
    }
  };

  const handleOpenRefundModal = (inv: Invoice) => {
    setSelectedInvoice(inv);
    setRefundLineId('');
    setRefundAmount(inv.paid_amount);
    setRefundReason('');
    setRefundModalOpen(true);
  };

  const handleSubmitRefund = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    if (!refundReason.trim()) {
      showToast({ type: 'error', title: 'Missing Reason', message: 'Please provide a justification for refund.' });
      return;
    }

    setSubmittingRefund(true);
    try {
      await api.requestRefund({
        invoice_id: selectedInvoice.id,
        invoice_line_id: refundLineId || undefined,
        amount: refundAmount,
        reason: refundReason.trim(),
      });
      showToast({
        type: 'success',
        title: 'Refund Request Submitted',
        message: 'Pre-sample cancellation request queued for Admin approval.',
      });
      setRefundModalOpen(false);
      setDetailModalOpen(false);
      fetchInvoices();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Refund Request Failed', message: err.message });
    } finally {
      setSubmittingRefund(false);
    }
  };

  const handleOpenSettleModal = (inv: Invoice) => {
    setSelectedInvoice(inv);
    setSettleAmount(inv.due_amount);
    setSettleChannel('CASH');
    setSettleRef('');
    setSettleModalOpen(true);
  };

  const handleSubmitSettle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoice) return;
    if (settleAmount <= 0 || settleAmount > selectedInvoice.due_amount) {
      showToast({ type: 'error', title: 'Invalid Amount', message: 'Amount must be between 1 and outstanding due.' });
      return;
    }

    try {
      await api.createPayment({
        invoice_id: selectedInvoice.id,
        amount: settleAmount,
        channel: settleChannel,
        reference_no: settleRef || undefined,
        notes: 'Receptionist desk due collection',
      });
      showToast({
        type: 'success',
        title: 'Payment Received',
        message: `৳${settleAmount} collected for invoice ${selectedInvoice.invoice_number}.`,
      });
      setSettleModalOpen(false);
      const updated = await api.getInvoice(selectedInvoice.id);
      setSelectedInvoice(updated);
      fetchInvoices();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Payment Failed', message: err.message });
    }
  };

  const handleOpenDisburse = (refundReq: any) => {
    setSelectedRefundForDisburse(refundReq);
    setDisburseMethod('CASH');
    setDisburseRef('');
    setDisburseModalOpen(true);
  };

  const handleSubmitDisburse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRefundForDisburse) return;
    setSubmittingDisburse(true);
    try {
      await api.disburseRefund(selectedRefundForDisburse.id, {
        method: disburseMethod,
        reference: disburseRef || undefined,
      });
      showToast({
        type: 'success',
        title: 'Refund Disbursed',
        message: `Payout of ৳${selectedRefundForDisburse.amount} successfully processed via ${disburseMethod}.`,
      });
      setDisburseModalOpen(false);
      if (selectedInvoice) {
        const updated = await api.getInvoice(selectedInvoice.id);
        setSelectedInvoice(updated);
      }
      fetchInvoices();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Disbursement Failed', message: err.message });
    } finally {
      setSubmittingDisburse(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Diagnostic Invoices</h1>
          <p className="text-xs text-[#6D6A60]">
            Review all patient invoices, reprint official money receipts, and initiate pre-sample refunds.
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter by bill #, patient, phone..."
              className="text-xs bg-transparent border-none outline-none w-48 text-[#1B1B0E]"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-white border border-[#CAC7BE] rounded-xl px-3 py-1.5 text-xs font-medium text-[#54524A] shadow-2xs cursor-pointer"
          >
            <option value="All Payments">All Payments</option>
            <option value="Paid">Paid</option>
            <option value="Unpaid">Unpaid</option>
            <option value="Partial Due">Partial Due</option>
            <option value="Partially Refunded">Partially Refunded</option>
            <option value="Fully Refunded">Fully Refunded</option>
          </select>
        </div>
      </div>

      {/* Invoices Table Card */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Invoice #</th>
                <th className="pb-3">Date</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3">MRN</th>
                <th className="pb-3 text-right">Net</th>
                <th className="pb-3 text-right">Paid</th>
                <th className="pb-3 text-right">Due</th>
                <th className="pb-3 text-center">Payment</th>
                <th className="pb-3 text-center">Refund Status</th>
                <th className="pb-3 text-right pr-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {invoices.length === 0 && !loading && (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-[#8E8A7E]">
                    No invoices matching your search criteria.
                  </td>
                </tr>
              )}
              {invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-[#F4F3F0] transition-colors">
                  <td
                    onClick={() => handleOpenDetail(inv.id)}
                    className="py-3 pl-2 font-mono font-bold text-[#1B1B0E] hover:text-[#CF8852] hover:underline cursor-pointer"
                  >
                    {inv.invoice_number}
                  </td>
                  <td className="py-3 text-[#6D6A60]">
                    {new Date(inv.created_at).toLocaleDateString('en-GB')}
                  </td>
                  <td className="py-3 font-semibold text-[#1B1B0E]">
                    <div>{inv.patient_name}</div>
                    <div className="text-[11px] text-[#6D6A60] font-normal">{inv.patient_phone}</div>
                  </td>
                  <td className="py-3 text-[#6D6A60] font-mono">{inv.patient_mrn}</td>
                  <td className="py-3 text-right font-medium">৳{inv.net_amount.toLocaleString()}</td>
                  <td className="py-3 text-right text-[#1E6327] font-semibold">৳{inv.paid_amount.toLocaleString()}</td>
                  <td className="py-3 text-right font-semibold">
                    {inv.due_amount > 0 ? (
                      <span className="text-[#9C2417]">৳{inv.due_amount.toLocaleString()}</span>
                    ) : (
                      <span className="text-[#6D6A60]">৳0</span>
                    )}
                  </td>
                  <td className="py-3 text-center">
                    <Badge
                      variant={getPaymentStatusBadgeVariant(inv.payment_status, inv.paid_amount, inv.due_amount)}
                      size="sm"
                    >
                      {formatPaymentStatus(inv.payment_status, inv.paid_amount, inv.due_amount)}
                    </Badge>
                  </td>
                  <td className="py-3 text-center">
                    <Badge variant={getRefundStatusBadgeVariant(inv.refund_status)} size="sm">
                      {formatRefundStatus(inv.refund_status)}
                    </Badge>
                  </td>
                  <td className="py-3 text-right pr-2 space-x-1.5">
                    <button
                      onClick={() => handleOpenDetail(inv.id)}
                      className="p-1.5 text-[#525333] hover:bg-[#E8E7E3] rounded-lg transition-colors cursor-pointer"
                      title="View Invoice Details"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleReprint(inv.id)}
                      className="p-1.5 text-[#CF8852] hover:bg-[#FAF3EC] rounded-lg transition-colors cursor-pointer"
                      title="Reprint Receipt (Duplicate)"
                    >
                      <Printer className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invoice Detail Modal */}
      <Modal
        isOpen={detailModalOpen}
        onClose={handleCloseDetail}
        title={selectedInvoice ? `Invoice Details — ${selectedInvoice.invoice_number}` : ''}
        subtitle={selectedInvoice ? `MRN: ${selectedInvoice.patient_mrn} | Patient: ${selectedInvoice.patient_name}` : ''}
        maxWidth="2xl"
      >
        {selectedInvoice && (
          <div className="space-y-5 text-xs">
            {/* Meta header */}
            <div className="bg-[#F4F3F0] border border-[#E8E7E3] rounded-xl p-3 grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div>
                <span className="text-[#6D6A60] block">Contact</span>
                <span className="font-semibold text-[#1B1B0E]">{selectedInvoice.patient_phone}</span>
              </div>
              <div>
                <span className="text-[#6D6A60] block">Age / Gender</span>
                <span className="font-semibold text-[#1B1B0E]">
                  {selectedInvoice.patient_age_display || '-'} / {selectedInvoice.patient_gender || '-'}
                </span>
              </div>
              <div>
                <span className="text-[#6D6A60] block">Prescribed By</span>
                <span className="font-semibold text-[#1B1B0E] truncate block">
                  {selectedInvoice.prescribed_by_name || 'Self / Walk-in'}
                </span>
              </div>
              <div>
                <span className="text-[#6D6A60] block">Referred By</span>
                <span className="font-semibold text-[#1B1B0E] truncate block">
                  {selectedInvoice.referrer_name || 'Self / Walk-in'}
                </span>
              </div>
              <div>
                <span className="text-[#6D6A60] block">Created By</span>
                <span className="font-semibold text-[#1B1B0E] truncate block">
                  {selectedInvoice.created_by_name || 'Reception Staff'}
                </span>
              </div>
            </div>

            {/* Test Lines */}
            <div>
              <span className="text-xs font-bold text-[#525333] uppercase tracking-wider block mb-2">
                Investigations Ordered
              </span>
              <div className="border border-[#DCDAD4] rounded-xl overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-[#E8E7E3]/60 text-[#6D6A60] font-semibold border-b border-[#DCDAD4]">
                    <tr>
                      <th className="p-2.5">Investigation</th>
                      <th className="p-2.5">Dept</th>
                      <th className="p-2.5 text-center">Urgent</th>
                      <th className="p-2.5 text-center">Sample</th>
                      <th className="p-2.5 text-right">Price</th>
                      <th className="p-2.5 text-right">Disc.</th>
                      <th className="p-2.5 text-right">Net</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {selectedInvoice.lines.map((line) => (
                      <tr key={line.id}>
                        <td className="p-2.5 font-medium">
                          <div className="font-semibold text-[#1B1B0E]">{line.test_name}</div>
                          {line.outcome === 'NOT_PERFORMED' && (
                            <div className="flex flex-wrap items-center gap-1.5 mt-1">
                              <span className="text-[10px] font-bold text-red-700 bg-red-100 px-1.5 py-0.5 rounded">
                                NOT PERFORMED (D15)
                              </span>
                              {line.d15_refund_status && (
                                <span className="text-[10px] text-[#54524A] bg-[#E8E7E3] px-1.5 py-0.5 rounded font-mono">
                                  {line.d15_refund_status === 'PENDING_ADMIN_APPROVAL'
                                    ? 'Refund Pending Admin Approval'
                                    : line.d15_refund_status === 'APPROVED'
                                      ? 'Refund Approved (Pending Payout)'
                                      : line.d15_refund_status === 'REJECTED'
                                        ? `Refund Rejected: ${line.d15_refund_reason || ''}`
                                        : line.d15_refund_status === 'DISBURSED'
                                          ? 'Refund Disbursed'
                                          : line.d15_refund_status}
                                </span>
                              )}
                            </div>
                          )}
                          {line.is_locked && line.outcome !== 'NOT_PERFORMED' && (
                            <div className="text-[10px] text-amber-700 mt-0.5">
                              {line.locked_reason || 'Line locked (specimen processing)'}
                            </div>
                          )}
                        </td>
                        <td className="p-2.5 text-[#6D6A60]">{line.department}</td>
                        <td className="p-2.5 text-center">
                          {line.is_urgent ? (
                            <Badge variant="danger" size="sm">
                              URGENT
                            </Badge>
                          ) : (
                            <span className="text-[#8E8A7E]">-</span>
                          )}
                        </td>
                        <td className="p-2.5 text-center">
                          {(() => {
                            const rawStatus = (line.sample_status || (line.sample_collected ? 'COLLECTED' : 'AWAITING COLLECTION')).toUpperCase();
                            if (rawStatus === 'COLLECTED') {
                              return <Badge variant="success" size="sm">COLLECTED</Badge>;
                            }
                            if (rawStatus === 'REJECTED') {
                              return <Badge variant="danger" size="sm">REJECTED</Badge>;
                            }
                            if (rawStatus === 'SPOILED') {
                              return <Badge variant="danger" size="sm">SPOILED</Badge>;
                            }
                            if (rawStatus === 'PERFORMED') {
                              return <Badge variant="info" size="sm">PERFORMED</Badge>;
                            }
                            return <Badge variant="neutral" size="sm">AWAITING COLLECTION</Badge>;
                          })()}
                        </td>
                        <td className="p-2.5 text-right">৳{line.price}</td>
                        <td className="p-2.5 text-right text-[#1E6327]">
                          {line.discount_amount > 0 ? `-৳${line.discount_amount}` : '-'}
                        </td>
                        <td className="p-2.5 text-right font-bold">৳{line.net_amount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Financial Summary */}
            <div className="bg-[#FAF3EC] border border-[#E6C4A7] rounded-xl p-3.5 space-y-1.5">
              <div className="flex justify-between text-[#6D6A60]">
                <span>Gross Subtotal:</span>
                <span>৳{selectedInvoice.gross_amount.toLocaleString()}</span>
              </div>
              {selectedInvoice.urgent_fee_total > 0 && (
                <div className="flex justify-between text-red-600 font-medium">
                  <span>Urgent Surcharges:</span>
                  <span>+৳{selectedInvoice.urgent_fee_total.toLocaleString()}</span>
                </div>
              )}
              {(selectedInvoice.line_discount_total > 0 || selectedInvoice.master_discount_amount > 0) && (
                <div className="flex justify-between text-[#1E6327] font-medium">
                  <span>Total Discount:</span>
                  <span>
                    -৳{(selectedInvoice.line_discount_total + selectedInvoice.master_discount_amount).toLocaleString()}
                  </span>
                </div>
              )}
              <div className="flex justify-between text-sm font-extrabold text-[#1B1B0E] pt-1.5 border-t border-[#E6C4A7]">
                <span>Net Payable:</span>
                <span>৳{selectedInvoice.net_amount.toLocaleString()}</span>
              </div>
              <div className="flex justify-between font-semibold text-[#1E6327]">
                <span>Paid Total:</span>
                <span>৳{selectedInvoice.paid_amount.toLocaleString()}</span>
              </div>
              <div className={`flex justify-between font-bold ${selectedInvoice.due_amount > 0 ? 'text-[#9C2417]' : 'text-[#6D6A60]'}`}>
                <span>Due Balance:</span>
                <span>৳{selectedInvoice.due_amount.toLocaleString()}</span>
              </div>
            </div>

            {/* Payments History */}
            {selectedInvoice.payments && selectedInvoice.payments.length > 0 && (
              <div>
                <span className="text-xs font-bold text-[#525333] uppercase tracking-wider block mb-2">
                  Payment History
                </span>
                <div className="space-y-1.5">
                  {selectedInvoice.payments.map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between p-2 bg-white border border-[#DCDAD4] rounded-lg"
                    >
                      <div>
                        <span className="font-semibold text-[#1B1B0E]">{p.receipt_no}</span>
                        <span className="text-[#6D6A60] ml-2">
                          via {p.channel} on {new Date(p.created_at).toLocaleString('en-GB')}
                        </span>
                        {p.reference_no && (
                          <span className="text-[#8E8A7E] ml-2 text-[10px] font-mono">Ref: {p.reference_no}</span>
                        )}
                      </div>
                      <span className="font-bold text-[#1E6327]">৳{p.amount.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Refund Status & Lifecycle (Item 14) */}
            <div className="bg-white border border-[#DCDAD4] rounded-xl p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#525333] uppercase tracking-wider">
                  Refund Lifecycle Status
                </span>
                <Badge variant={getRefundStatusBadgeVariant(selectedInvoice.refund_status)} size="sm">
                  {formatRefundStatus(selectedInvoice.refund_status)}
                </Badge>
              </div>
              {selectedInvoice.refund_requests && selectedInvoice.refund_requests.length > 0 ? (
                <div className="space-y-1.5 pt-1">
                  {selectedInvoice.refund_requests.map((req: any) => (
                    <div
                      key={req.id}
                      className="p-2.5 bg-[#FAF9F6] border border-[#E8E7E3] rounded-lg text-xs flex justify-between items-center"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-[#9C2417]">৳{req.amount}</span>
                          <Badge
                            variant={
                              req.status === 'APPROVED' || req.status === 'EXECUTED'
                                ? 'success'
                                : req.status === 'REJECTED'
                                  ? 'danger'
                                  : 'warning'
                            }
                            size="sm"
                          >
                            {req.status}
                          </Badge>
                          {req.request_type && (
                            <span className="text-[10px] text-[#54524A] bg-[#E8E7E3] px-1.5 py-0.5 rounded font-mono">
                              {req.request_type === 'D15_NOT_PERFORMED' ? 'D15 Exception' : 'Pre-Sample'}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[#6D6A60] mt-0.5">Reason: {req.reason}</p>
                        {req.disbursed_at && (
                          <p className="text-[10px] text-green-700 font-medium mt-0.5">
                            Disbursed via {req.disbursement_method || 'CASH'}{' '}
                            {req.disbursement_reference ? `(Ref: ${req.disbursement_reference})` : ''} on{' '}
                            {new Date(req.disbursed_at).toLocaleDateString('en-GB')}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {req.status === 'APPROVED' && (
                          <button
                            type="button"
                            onClick={() => handleOpenDisburse(req)}
                            className="px-2.5 py-1 text-[11px] font-bold bg-[#1E6327] hover:bg-[#2D8A39] text-white rounded-md shadow-2xs transition-colors cursor-pointer"
                          >
                            Disburse Payout
                          </button>
                        )}
                        <span className="text-[10px] text-[#8E8A7E]">
                          {new Date(req.created_at).toLocaleDateString('en-GB')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-[#8E8A7E] italic">No refund requests filed for this invoice.</p>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-[#E8E7E3]">
              <div className="flex items-center gap-2">
                {(() => {
                  const hasEligiblePreSampleLine = selectedInvoice.lines?.some(
                    (l) => !l.sample_collected && !l.is_locked && l.sample_status !== 'REJECTED' && l.sample_status !== 'SPOILED'
                  );
                  return hasEligiblePreSampleLine ? (
                    <button
                      type="button"
                      onClick={() => handleOpenRefundModal(selectedInvoice)}
                      className="px-3 py-2 text-xs font-semibold text-[#9C2417] bg-[#FDF2F0] hover:bg-[#F8CBC6] border border-[#F8CBC6] rounded-xl transition-colors cursor-pointer flex items-center gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Request Pre-Sample Refund
                    </button>
                  ) : null;
                })()}
                {selectedInvoice.due_amount > 0 && (
                  <button
                    type="button"
                    onClick={() => handleOpenSettleModal(selectedInvoice)}
                    className="px-3 py-2 text-xs font-semibold text-[#8A5608] bg-[#FEF7EC] hover:bg-[#FBE0B2] border border-[#FBE0B2] rounded-xl transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <CreditCard className="w-3.5 h-3.5" />
                    Settle Due
                  </button>
                )}
                <button
                  type="button"
                  data-testid="invoice-detail-patient-history-btn"
                  onClick={() => {
                    setHistoryPatientId(selectedInvoice.patient_id);
                    setHistoryModalOpen(true);
                  }}
                  className="px-3 py-2 text-xs font-semibold text-[#525333] bg-[#E8E7E3] hover:bg-[#DCDAD4] border border-[#CAC7BE] rounded-xl transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <Eye className="w-3.5 h-3.5" />
                  Patient History
                </button>
              </div>

              <button
                type="button"
                onClick={() => handleReprint(selectedInvoice.id)}
                className="px-4 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                <Printer className="w-3.5 h-3.5" />
                Reprint Money Receipt
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Pre-Sample Refund Request Modal */}
      <Modal
        isOpen={refundModalOpen}
        onClose={() => setRefundModalOpen(false)}
        title="Request Pre-Sample Cancellation Refund"
        subtitle="Enforces rule: strictly forbidden if sample was collected"
        maxWidth="md"
      >
        <form onSubmit={handleSubmitRefund} className="space-y-4 text-xs">
          <div className="p-3 bg-[#FEF7EC] border border-[#FBE0B2] text-[#8A5608] rounded-xl">
            <p className="font-semibold">Workflow Rule:</p>
            <p className="text-[11px] mt-0.5">
              Pre-sample refunds are strictly permitted only for orders whose samples have NOT yet been collected.
              Submissions require Admin approval.
            </p>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Target Line Item (Optional)</label>
            <select
              value={refundLineId}
              onChange={(e) => setRefundLineId(e.target.value)}
              className="w-full p-2 bg-white border border-[#CAC7BE] rounded-xl outline-none"
            >
              <option value="">Entire Invoice ({selectedInvoice?.invoice_number})</option>
              {selectedInvoice?.lines.map((l) => {
                const isLockedOrProcessed =
                  l.sample_collected ||
                  l.is_locked ||
                  l.sample_status === 'REJECTED' ||
                  l.sample_status === 'SPOILED';
                return (
                  <option key={l.id} value={l.id} disabled={isLockedOrProcessed}>
                    {l.test_name} — ৳{l.net_amount}{' '}
                    {isLockedOrProcessed
                      ? l.outcome === 'NOT_PERFORMED'
                        ? '(D15 NOT PERFORMED - REQUEST VIA TECHNICIAN WORKLIST)'
                        : '(LOCKED / SAMPLE PROCESSED - CANNOT REFUND)'
                      : ''}
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Requested Refund Amount (৳) *</label>
            <input
              type="number"
              min="1"
              max={selectedInvoice?.paid_amount || 1}
              required
              value={refundAmount}
              onChange={(e) => setRefundAmount(Number(e.target.value))}
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-bold text-sm text-[#9C2417] text-right"
            />
            <span className="text-[10px] text-[#8E8A7E]">
              Maximum refundable: ৳{selectedInvoice?.paid_amount} (Paid total)
            </span>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Reason for Cancellation *</label>
            <textarea
              required
              rows={3}
              value={refundReason}
              onChange={(e) => setRefundReason(e.target.value)}
              placeholder="e.g. Patient refused needle prick before blood collection..."
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setRefundModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingRefund}
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors"
            >
              {submittingRefund ? 'Submitting...' : 'Submit to Admin for Approval'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Settle Due Modal */}
      <Modal
        isOpen={settleModalOpen}
        onClose={() => setSettleModalOpen(false)}
        title="Settle Due Payment"
        subtitle={`Invoice: ${selectedInvoice?.invoice_number} | Due: ৳${selectedInvoice?.due_amount}`}
        maxWidth="sm"
      >
        <form onSubmit={handleSubmitSettle} className="space-y-4 text-xs">
          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Payment Method</label>
            <select
              value={settleChannel}
              onChange={(e) => setSettleChannel(e.target.value)}
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-semibold"
            >
              <option value="CASH">Cash</option>
              <option value="BKASH">bKash</option>
              <option value="NAGAD">Nagad</option>
              <option value="ROCKET">Rocket</option>
              <option value="CARD">Card</option>
              <option value="BANK_TRANSFER">Bank Transfer</option>
            </select>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Amount to Pay (৳) *</label>
            <input
              type="number"
              min="1"
              max={selectedInvoice?.due_amount || 1}
              required
              value={settleAmount}
              onChange={(e) => setSettleAmount(Number(e.target.value))}
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-bold text-sm text-[#1E6327] text-right"
            />
          </div>

          {settleChannel !== 'CASH' && (
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">TrxID / Reference No</label>
              <input
                type="text"
                value={settleRef}
                onChange={(e) => setSettleRef(e.target.value)}
                placeholder="Optional"
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
              className="px-5 py-2 text-xs font-bold bg-[#1E6327] hover:bg-[#2D8A39] text-white rounded-xl shadow-xs transition-colors"
            >
              Confirm Collection
            </button>
          </div>
        </form>
      </Modal>

      {/* Disburse Approved Refund Modal (FIX 4) */}
      <Modal
        isOpen={disburseModalOpen}
        onClose={() => setDisburseModalOpen(false)}
        title="Disburse Approved Refund"
        subtitle={`Invoice: ${selectedInvoice?.invoice_number} | Amount: ৳${selectedRefundForDisburse?.amount || 0}`}
        maxWidth="sm"
      >
        <form onSubmit={handleSubmitDisburse} className="space-y-4 text-xs">
          <div className="p-3 bg-green-50 border border-green-200 text-green-900 rounded-xl">
            <p className="font-semibold">Payout Authorization:</p>
            <p className="text-[11px] mt-0.5">
              Admin has approved this refund request. Select payment channel to disburse funds to the patient and update drawer reconciliation.
            </p>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Disbursement Channel *</label>
            <select
              value={disburseMethod}
              onChange={(e) => setDisburseMethod(e.target.value)}
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-semibold"
            >
              <option value="CASH">Cash (Drawer)</option>
              <option value="BKASH">bKash MFS</option>
              <option value="NAGAD">Nagad MFS</option>
              <option value="ROCKET">Rocket MFS</option>
              <option value="CARD">Debit / Credit Card</option>
              <option value="BANK_TRANSFER">Bank Transfer</option>
            </select>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Disbursement Amount (৳)</label>
            <input
              type="text"
              readOnly
              value={`৳${selectedRefundForDisburse?.amount || 0}`}
              className="w-full p-2.5 bg-gray-100 border border-[#CAC7BE] rounded-xl font-bold text-sm text-[#9C2417] text-right"
            />
          </div>

          {disburseMethod !== 'CASH' && (
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">TrxID / Reference No</label>
              <input
                type="text"
                value={disburseRef}
                onChange={(e) => setDisburseRef(e.target.value)}
                placeholder="e.g. TrxID / Reference"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-mono"
              />
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setDisburseModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingDisburse}
              className="px-5 py-2 text-xs font-bold bg-[#1E6327] hover:bg-[#2D8A39] text-white rounded-xl shadow-xs transition-colors"
            >
              {submittingDisburse ? 'Disbursing...' : 'Confirm Payout'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Dual Copy Invoice Modal for Reprinting (Item 10) */}
      <DualCopyInvoiceModal
        isOpen={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        savedInvoice={selectedInvoice}
        isReprint={isReprint}
      />

      {/* In-place Patient History Modal Overlay (preserves Invoices tab state) */}
      <PatientHistoryModal
        isOpen={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        patientId={historyPatientId}
      />
    </div>
  );
};

