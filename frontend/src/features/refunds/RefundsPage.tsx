import React, { useState, useEffect } from 'react';
import {
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Shield,
  AlertTriangle,
  FileText,
  User,
  Filter,
} from 'lucide-react';
import { api } from '../../api/client';
import { RefundRequestItem } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

export const RefundsPage: React.FC = () => {
  const [refunds, setRefunds] = useState<RefundRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Review Modal State (Admin only)
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedRefund, setSelectedRefund] = useState<RefundRequestItem | null>(null);
  const [reviewDecision, setReviewDecision] = useState<'APPROVED' | 'REJECTED'>('APPROVED');
  const [rejectionReason, setRejectionReason] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);

  // Disburse Modal State (FIX 4)
  const [disburseModalOpen, setDisburseModalOpen] = useState(false);
  const [selectedDisburseRefund, setSelectedDisburseRefund] = useState<RefundRequestItem | null>(null);
  const [disburseMethod, setDisburseMethod] = useState<'CASH' | 'BKASH' | 'NAGAD' | 'ROCKET' | 'BANK_TRANSFER'>('CASH');
  const [disburseRef, setDisburseRef] = useState('');
  const [submittingDisburse, setSubmittingDisburse] = useState(false);

  const { role } = useAuth();
  const { showToast } = useToast();

  const fetchRefunds = async () => {
    try {
      setLoading(true);
      const res = await api.getRefunds(statusFilter !== 'ALL' ? statusFilter : undefined);
      setRefunds(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load refunds', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRefunds();
  }, [statusFilter]);

  const handleOpenReview = (refund: RefundRequestItem, decision: 'APPROVED' | 'REJECTED') => {
    setSelectedRefund(refund);
    setReviewDecision(decision);
    setRejectionReason('');
    setReviewModalOpen(true);
  };

  const handleConfirmReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRefund) return;
    if (reviewDecision === 'REJECTED' && !rejectionReason.trim()) {
      showToast({ type: 'error', title: 'Rejection Reason Required', message: 'Please specify reason for rejection.' });
      return;
    }

    setSubmittingReview(true);
    try {
      await api.reviewRefund(selectedRefund.id, {
        status: reviewDecision,
        rejection_reason: reviewDecision === 'REJECTED' ? rejectionReason.trim() : undefined,
      });

      showToast({
        type: reviewDecision === 'APPROVED' ? 'success' : 'info',
        title: `Refund ${reviewDecision === 'APPROVED' ? 'Approved' : 'Rejected'}`,
        message: `Refund request for ৳${selectedRefund.amount} has been ${reviewDecision.toLowerCase()}.`,
      });

      setReviewModalOpen(false);
      fetchRefunds();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Review Failed', message: err.message });
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleOpenDisburse = (refund: RefundRequestItem) => {
    setSelectedDisburseRefund(refund);
    setDisburseMethod('CASH');
    setDisburseRef('');
    setDisburseModalOpen(true);
  };

  const handleConfirmDisburse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDisburseRefund) return;
    setSubmittingDisburse(true);
    try {
      await api.disburseRefund(selectedDisburseRefund.id, {
        method: disburseMethod,
        reference: disburseRef.trim() || undefined,
      });
      showToast({
        type: 'success',
        title: 'Refund Disbursed',
        message: `Payout of ৳${selectedDisburseRefund.amount} disbursed via ${disburseMethod}.`,
      });
      setDisburseModalOpen(false);
      fetchRefunds();
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
          <h1 className="text-xl font-bold text-[#1B1B0E]">Pre-Sample Refund Requests</h1>
          <p className="text-xs text-[#6D6A60]">
            Track cancellation requests initiated before specimen collection. Admin approval required for final payout.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-white border border-[#CAC7BE] rounded-xl px-3 py-1.5 text-xs font-medium text-[#54524A] shadow-2xs cursor-pointer"
          >
            <option value="ALL">All Requests</option>
            <option value="PENDING_ADMIN_APPROVAL">Pending Approval</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="COMPLETED">Completed</option>
          </select>
        </div>
      </div>

      {/* Role notice banner */}
      {role === 'ADMIN' ? (
        <div className="p-3 bg-[#FAF3EC] border border-[#CF8852] rounded-xl text-xs text-[#96572A] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-[#CF8852]" />
            <span className="font-semibold">
              Admin Mode Active: You can approve or reject pending cancellation refund requests.
            </span>
          </div>
          <span className="text-[11px] font-mono">Role: ADMIN</span>
        </div>
      ) : (
        <div className="p-3 bg-[#F2F3EC] border border-[#C2C6A4] rounded-xl text-xs text-[#444529] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#525333]" />
            <span>
              Receptionist Mode: You can view status. Switch to Admin mode in the header to test approval actions.
            </span>
          </div>
          <span className="text-[11px] font-mono">Role: RECEPTIONIST</span>
        </div>
      )}

      {/* Refunds Table Card */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Invoice #</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3">Target Test</th>
                <th className="pb-3 text-right">Amount</th>
                <th className="pb-3">Reason</th>
                <th className="pb-3">Requested By</th>
                <th className="pb-3 text-center">Status</th>
                <th className="pb-3 text-right pr-2">Admin Review</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {refunds.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-[#8E8A7E]">
                    No refund requests found matching filter.
                  </td>
                </tr>
              )}
              {refunds.map((r) => (
                <tr key={r.id} className="hover:bg-[#F4F3F0] transition-colors">
                  <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{r.invoice_number}</td>
                  <td className="py-3 font-semibold text-[#1B1B0E]">{r.patient_name}</td>
                  <td className="py-3 text-[#54524A]">
                    <div>{r.test_name || 'Full Invoice'}</div>
                    {r.request_type && (
                      <span className="text-[10px] text-[#54524A] bg-[#E8E7E3] px-1.5 py-0.5 rounded font-mono mt-0.5 inline-block">
                        {r.request_type === 'D15_NOT_PERFORMED' ? 'D15 Exception' : 'Pre-Sample'}
                      </span>
                    )}
                  </td>
                  <td className="py-3 text-right font-bold text-[#9C2417]">৳{r.amount.toLocaleString()}</td>
                  <td className="py-3 text-[#6D6A60] max-w-xs truncate" title={r.reason}>
                    {r.reason}
                  </td>
                  <td className="py-3 text-[#6D6A60]">
                    {r.requested_by_name || 'Reception Staff'}
                    <span className="block text-[10px] text-[#8E8A7E]">
                      {new Date(r.created_at).toLocaleDateString('en-GB')}
                    </span>
                  </td>
                  <td className="py-3 text-center">
                    <Badge
                      variant={
                        r.status === 'APPROVED' || r.status === 'COMPLETED'
                          ? 'success'
                          : r.status === 'REJECTED'
                          ? 'danger'
                          : 'warning'
                      }
                      size="sm"
                    >
                      {r.status.replace(/_/g, ' ')}
                    </Badge>
                  </td>
                  <td className="py-3 text-right pr-2">
                    {r.status === 'PENDING_ADMIN_APPROVAL' ? (
                      role === 'ADMIN' ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleOpenReview(r, 'APPROVED')}
                            className="px-2.5 py-1 bg-[#1E6327] hover:bg-[#2D8A39] text-white font-semibold rounded-md shadow-2xs transition-colors cursor-pointer text-[11px]"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleOpenReview(r, 'REJECTED')}
                            className="px-2.5 py-1 bg-[#9C2417] hover:bg-[#D03828] text-white font-semibold rounded-md shadow-2xs transition-colors cursor-pointer text-[11px]"
                          >
                            Reject
                          </button>
                        </div>
                      ) : (
                        <span className="text-[11px] text-[#8A5608] font-medium italic">
                          Awaiting Admin
                        </span>
                      )
                    ) : r.status === 'APPROVED' ? (
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleOpenDisburse(r)}
                          className="px-2.5 py-1 bg-[#1E6327] hover:bg-[#2D8A39] text-white font-semibold rounded-md shadow-2xs transition-colors cursor-pointer text-[11px]"
                        >
                          Disburse Payout
                        </button>
                      </div>
                    ) : (
                      <div className="text-[11px] text-[#6D6A60]">
                        {r.status === 'COMPLETED' ? (
                          <span className="text-green-700 font-medium">
                            Disbursed ({r.disbursement_method || 'CASH'})
                          </span>
                        ) : r.approved_by_name ? (
                          `Reviewed by ${r.approved_by_name}`
                        ) : (
                          'Completed'
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Admin Review Modal */}
      <Modal
        isOpen={reviewModalOpen}
        onClose={() => setReviewModalOpen(false)}
        title={reviewDecision === 'APPROVED' ? 'Approve Refund Request' : 'Reject Refund Request'}
        subtitle={`Invoice: ${selectedRefund?.invoice_number} | Amount: ৳${selectedRefund?.amount}`}
        maxWidth="md"
      >
        <form onSubmit={handleConfirmReview} className="space-y-4 text-xs">
          <div
            className={`p-3 rounded-xl border ${
              reviewDecision === 'APPROVED'
                ? 'bg-[#EDF7EE] border-[#C3E6C7] text-[#1E6327]'
                : 'bg-[#FDF2F0] border-[#F8CBC6] text-[#9C2417]'
            }`}
          >
            <p className="font-semibold">
              {reviewDecision === 'APPROVED'
                ? 'Confirming approval will authorization the drawer refund ledger.'
                : 'Rejecting this refund request requires an explanation.'}
            </p>
            <p className="text-[11px] mt-0.5">
              Reason specified by reception: "{selectedRefund?.reason}"
            </p>
          </div>

          {reviewDecision === 'REJECTED' && (
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Rejection Reason *</label>
              <textarea
                required
                rows={3}
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Explain why the cancellation refund cannot be granted..."
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setReviewModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingReview}
              className={`px-5 py-2 text-xs font-bold text-white rounded-xl shadow-xs transition-colors ${
                reviewDecision === 'APPROVED'
                  ? 'bg-[#1E6327] hover:bg-[#2D8A39]'
                  : 'bg-[#9C2417] hover:bg-[#D03828]'
              }`}
            >
              {submittingReview
                ? 'Saving...'
                : reviewDecision === 'APPROVED'
                ? 'Confirm Approval'
                : 'Confirm Rejection'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Disburse Approved Refund Modal (FIX 4) */}
      <Modal
        isOpen={disburseModalOpen}
        onClose={() => setDisburseModalOpen(false)}
        title="Disburse Approved Refund"
        subtitle={`Invoice: ${selectedDisburseRefund?.invoice_number} | Amount: ৳${selectedDisburseRefund?.amount || 0}`}
        maxWidth="sm"
      >
        <form onSubmit={handleConfirmDisburse} className="space-y-4 text-xs">
          <div className="p-3 bg-green-50 border border-green-200 text-green-900 rounded-xl">
            <p className="font-semibold">Payout Authorization:</p>
            <p className="text-[11px] mt-0.5">
              Admin has approved this refund. Select payout method to disburse cash or trigger digital transfer.
            </p>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Disbursement Channel *</label>
            <select
              value={disburseMethod}
              onChange={(e) => setDisburseMethod(e.target.value as any)}
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-semibold"
            >
              <option value="CASH">Cash (Cash Drawer)</option>
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
              value={`৳${selectedDisburseRefund?.amount || 0}`}
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
                placeholder="e.g. TrxID / Transfer Receipt"
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
    </div>
  );
};

