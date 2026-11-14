import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FileCheck,
  Search,
  Printer,
  Lock,
  Unlock,
  CheckCircle2,
  AlertTriangle,
  UserCheck,
  Shield,
  Eye,
  Filter,
  FileText,
  Loader2,
} from 'lucide-react';
import { api } from '../../api/client';
import { DeliverableReportItem, ResultPreview } from '../../types';
import { ResultPreviewBody } from '../../components/common/ResultReportPreviewModal';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { PrintableReportModal } from '../../components/common/PrintableReportModal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { ReadyResultsPanel } from './ReadyResultsPanel';
import { SettleDueModal } from '../../components/common/SettleDueModal';

export const ReportsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const searchParam = searchParams.get('search');
  const idParam = searchParams.get('id');

  // Prompt 10F (F3): "Ready Results" (submitted lab results, all rooms) is the default view;
  // "Issued Reports" keeps the report_versions list (filled once Module 14 issues reports).
  const [view, setView] = useState<'READY' | 'ISSUED'>(idParam ? 'ISSUED' : 'READY');
  const [reports, setReports] = useState<DeliverableReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState(searchParam || '');
  const [hasDueFilter, setHasDueFilter] = useState<'ALL' | 'DUE' | 'CLEAR'>('ALL');

  // Delivery Modal State
  const [deliverModalOpen, setDeliverModalOpen] = useState(false);
  const [selectedReport, setSelectedReport] = useState<DeliverableReportItem | null>(null);
  const [recipientName, setRecipientName] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [recipientRelation, setRecipientRelation] = useState('Self');
  const [deliveryNotes, setDeliveryNotes] = useState('');
  const [submittingDelivery, setSubmittingDelivery] = useState(false);

  // Admin Due Override Modal State
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [submittingOverride, setSubmittingOverride] = useState(false);

  // Prompt 16: stored, immutable content of a Final report
  const [snapshotFor, setSnapshotFor] = useState<DeliverableReportItem | null>(null);
  const [snapshot, setSnapshot] = useState<ResultPreview | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const openSnapshot = (rep: DeliverableReportItem) => {
    setSnapshotFor(rep);
    setSnapshot(null);
    setSnapshotError(null);
    api
      .getReportSnapshot(rep.report_version_id ?? rep.id)
      .then(setSnapshot)
      .catch((err: any) => setSnapshotError(err?.message || 'Could not load the stored report.'));
  };

  // Prompt 17: take the due inline (same modal and endpoint as the Dues page)
  const [payInvoiceId, setPayInvoiceId] = useState<string | number | null>(null);

  // Printable Report Modal State
  const [printModalOpen, setPrintModalOpen] = useState(false);

  const { hasPermission } = useAuth();
  // Prompt 10E: only 'report.release_with_due' holders (Admin/Owner) may release with a due, with a reason
  const canReleaseWithDue = hasPermission('report.release_with_due');
  const { showToast } = useToast();

  const fetchReports = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (searchTerm.trim()) params.search = searchTerm.trim();
      if (hasDueFilter === 'DUE') params.has_due = true;
      if (hasDueFilter === 'CLEAR') params.has_due = false;
      const res = await api.getDeliverableReports({ search: params.search, has_due: params.has_due });
      setReports(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load deliverable reports', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchReports();
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm, hasDueFilter]);

  useEffect(() => {
    if (idParam && reports.length > 0) {
      const match = reports.find((r) => String(r.id) === String(idParam) || String(r.report_version_id) === String(idParam));
      if (match) {
        handleViewPrint(match);
      }
    }
  }, [idParam, reports]);

  const handleOpenDeliver = (report: DeliverableReportItem) => {
    setSelectedReport(report);
    setRecipientName(report.patient_name);
    setRecipientPhone(report.patient_phone);
    setRecipientRelation('Self');
    setDeliveryNotes('');
    setDeliverModalOpen(true);
  };

  const handleOpenOverride = (report: DeliverableReportItem) => {
    setSelectedReport(report);
    setRecipientName(report.patient_name);
    setRecipientRelation('Self');
    setOverrideReason('');
    setOverrideModalOpen(true);
  };

  const handleViewPrint = (report: DeliverableReportItem) => {
    setSelectedReport(report);
    setPrintModalOpen(true);
  };

  const handleConfirmDelivery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReport) return;
    if (!recipientName.trim()) {
      showToast({ type: 'error', title: 'Recipient Required', message: 'Please specify recipient name.' });
      return;
    }

    setSubmittingDelivery(true);
    try {
      await api.deliverReport(selectedReport.id, {
        recipient_name: recipientName.trim(),
        recipient_phone: recipientPhone.trim() || undefined,
        recipient_relation: recipientRelation,
        notes: deliveryNotes.trim() || undefined,
      });

      showToast({
        type: 'success',
        title: 'Report Delivered',
        message: `${selectedReport.test_name} handed over to ${recipientName}.`,
      });

      setDeliverModalOpen(false);
      fetchReports();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Delivery Failed', message: err.message });
    } finally {
      setSubmittingDelivery(false);
    }
  };

  const handleConfirmOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReport) return;
    if (!overrideReason.trim()) {
      showToast({ type: 'error', title: 'Reason Required', message: 'Admin override justification is mandatory.' });
      return;
    }

    setSubmittingOverride(true);
    try {
      await api.overrideReportHold(selectedReport.id, {
        override_reason: overrideReason.trim(),
        recipient_name: recipientName.trim() || selectedReport.patient_name,
        recipient_relation: recipientRelation,
      });

      showToast({
        type: 'success',
        title: 'Due Override Delivered',
        message: `Admin override authorized. Report released to ${recipientName}.`,
      });

      setOverrideModalOpen(false);
      fetchReports();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Override Failed', message: err.message });
    } finally {
      setSubmittingOverride(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Ready Reports & Delivery</h1>
          <p className="text-xs text-[#6D6A60]">
            Results ready from the lab, and issued reports for hand-over. Dues require settlement or Admin override authorization.
          </p>
        </div>

        {view === 'ISSUED' && (
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Bill no. (final / temp), patient no., test, mobile, name..."
              aria-label="Search reports for handover"
              className="text-xs bg-transparent border-none outline-none w-72 text-[#1B1B0E]"
            />
          </div>

          <select
            value={hasDueFilter}
            onChange={(e) => setHasDueFilter(e.target.value as any)}
            className="bg-white border border-[#CAC7BE] rounded-xl px-3 py-1.5 text-xs font-medium text-[#54524A] shadow-2xs cursor-pointer"
          >
            <option value="ALL">All Reports</option>
            <option value="CLEAR">Paid / Ready to Handover</option>
            <option value="DUE">Held with Dues</option>
          </select>
        </div>
        )}
      </div>

      <div className="flex items-center gap-1.5" role="tablist" aria-label="Report views">
        {([
          { id: 'READY', label: 'Ready Results' },
          { id: 'ISSUED', label: 'Issued Reports' },
        ] as const).map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={view === t.id}
            data-testid={`reports-tab-${t.id}`}
            onClick={() => setView(t.id)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852] ${
              view === t.id ? 'bg-[#525333] text-white shadow-xs' : 'bg-[#F4F3F0] text-[#54524A] hover:bg-[#E8E7E3]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {view === 'READY' ? (
        <ReadyResultsPanel />
      ) : (
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs" data-testid="issued-reports-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Invoice #</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3">Investigation</th>
                <th className="pb-3">Dept</th>
                <th className="pb-3">Authorized By</th>
                <th className="pb-3 text-right">Outstanding Due</th>
                <th className="pb-3 text-center">Delivery Status</th>
                <th className="pb-3 text-right pr-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {reports.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-[#8E8A7E]">
                    {searchTerm.trim() || hasDueFilter !== 'ALL'
                      ? 'No issued reports match this filter.'
                      : 'No issued reports yet. Finalize a submitted result (Ready Results tab) to issue its report.'}
                  </td>
                </tr>
              )}
              {reports.map((rep) => {
                const hasDue = rep.due_amount > 0;
                // Prompt 17: held follows the center setting (the server decides); a due can exist without a hold
                const held = !rep.can_deliver;
                return (
                  <tr key={rep.id} className="hover:bg-[#F4F3F0] transition-colors">
                    <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{rep.invoice_number}</td>
                    <td className="py-3">
                      <div className="font-semibold text-[#1B1B0E]">{rep.patient_name}</div>
                      <div className="text-[11px] text-[#6D6A60]">{rep.patient_phone}</div>
                    </td>
                    <td className="py-3">
                      <div className="font-medium text-[#1B1B0E]">{rep.test_name}</div>
                      <span className="text-[10px] text-[#8E8A7E]">Version {rep.version_number}.0</span>
                    </td>
                    <td className="py-3 text-[#6D6A60]">{rep.department}</td>
                    <td className="py-3 text-[#54524A]">
                      {rep.authorized_by_name || 'Dr. Anisur Rahman'}
                      <span className="block text-[10px] text-[#8E8A7E]">
                        {rep.authorized_at ? new Date(rep.authorized_at).toLocaleDateString('en-GB') : '-'}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      {hasDue ? (
                        <span className="font-bold text-[#9C2417] px-2 py-0.5 bg-[#FDF2F0] border border-[#F8CBC6] rounded-md">
                          ৳{rep.due_amount.toLocaleString()} Due
                        </span>
                      ) : (
                        <span className="text-[#1E6327] font-semibold">Cleared (৳0)</span>
                      )}
                    </td>
                    <td className="py-3 text-center">
                      {rep.is_delivered ? (
                        <Badge variant="success" size="sm" dot>
                          DELIVERED
                        </Badge>
                      ) : held ? (
                        <Badge variant="danger" size="sm" dot>
                          DUE HOLD
                        </Badge>
                      ) : (
                        <Badge variant="orange" size="sm" dot>
                          READY
                        </Badge>
                      )}
                    </td>
                    <td className="py-3 text-right pr-2 space-x-1.5">
                      <button
                        onClick={() => openSnapshot(rep)}
                        data-testid={`issued-view-${rep.id}`}
                        className="p-1.5 text-[#2B547E] hover:bg-[#EEF3F8] rounded-lg transition-colors cursor-pointer"
                        title="View the stored result of this Final report"
                      >
                        <FileText className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleViewPrint(rep)}
                        className="p-1.5 text-[#525333] hover:bg-[#E8E7E3] rounded-lg transition-colors cursor-pointer"
                        title="Preview & Print Report"
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      {!rep.is_delivered && (
                        <>
                          {hasDue && (
                            <button
                              onClick={() => setPayInvoiceId(rep.invoice_id ?? rep.id)}
                              data-testid={`handover-pay-${rep.id}`}
                              className="px-2.5 py-1 bg-white text-[#1E6327] border border-[#C3E6C7] hover:bg-[#EDF7EE] font-semibold rounded-lg text-xs cursor-pointer"
                              title="Collect the due here, then hand the report over"
                            >
                              Take payment
                            </button>
                          )}
                          {!held ? (
                            <button
                              onClick={() => handleOpenDeliver(rep)}
                              className="px-3 py-1 bg-[#2D8A39] hover:bg-[#1E6327] text-white font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer text-xs inline-flex items-center gap-1"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Deliver</span>
                            </button>
                          ) : canReleaseWithDue ? (
                            <button
                              onClick={() => handleOpenOverride(rep)}
                              className="px-2.5 py-1 bg-[#CF8852] hover:bg-[#B7703B] text-white font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer text-xs inline-flex items-center gap-1"
                              title="Admin Due Override"
                            >
                              <Unlock className="w-3.5 h-3.5" />
                              <span>Override & Deliver</span>
                            </button>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#F4F3F0] text-[#8E8A7E] border border-[#DCDAD4] rounded-lg text-[11px] font-medium"
                              title="Settle the due first, or ask an Admin/Owner to release it with an override reason"
                            >
                              <Lock className="w-3 h-3" />
                              <span>Held</span>
                            </span>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      )}

      {payInvoiceId !== null && (
        <SettleDueModal key={payInvoiceId} invoiceId={payInvoiceId} onClose={() => setPayInvoiceId(null)} onPaid={fetchReports} />
      )}

      {/* Stored Final report content (Prompt 16) */}
      <Modal
        isOpen={snapshotFor !== null}
        onClose={() => setSnapshotFor(null)}
        title="Final report"
        subtitle={snapshotFor ? `${snapshotFor.invoice_number} | ${snapshotFor.test_name}` : undefined}
        maxWidth="4xl"
      >
        {snapshotError ? (
          <div className="p-3 text-xs text-[#54524A] bg-[#F4F3F0] border border-[#DCDAD4] rounded-xl" data-testid="snapshot-unavailable">{snapshotError}</div>
        ) : !snapshot ? (
          <div className="py-10 text-center text-xs text-[#6D6A60]">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
            Loading…
          </div>
        ) : (
          <ResultPreviewBody data={snapshot} onClose={() => setSnapshotFor(null)} />
        )}
      </Modal>

      {/* Deliver Report Modal */}
      <Modal
        isOpen={deliverModalOpen}
        onClose={() => setDeliverModalOpen(false)}
        title="Deliver Diagnostic Report"
        subtitle={`Invoice: ${selectedReport?.invoice_number} | Investigation: ${selectedReport?.test_name}`}
        maxWidth="md"
      >
        <form onSubmit={handleConfirmDelivery} className="space-y-4 text-xs">
          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Recipient Name *</label>
            <input
              type="text"
              required
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
              placeholder="e.g. Patient or relative name"
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Relationship to Patient *</label>
              <select
                value={recipientRelation}
                onChange={(e) => setRecipientRelation(e.target.value)}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl font-medium"
              >
                <option value="Self">Self (Patient)</option>
                <option value="Spouse">Spouse</option>
                <option value="Father">Father</option>
                <option value="Mother">Mother</option>
                <option value="Child">Son / Daughter</option>
                <option value="Sibling">Brother / Sister</option>
                <option value="Other">Other Representative</option>
              </select>
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Recipient Phone</label>
              <input
                type="tel"
                value={recipientPhone}
                onChange={(e) => setRecipientPhone(e.target.value)}
                placeholder="01711..."
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
              />
            </div>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Delivery Notes (Optional)</label>
            <input
              type="text"
              value={deliveryNotes}
              onChange={(e) => setDeliveryNotes(e.target.value)}
              placeholder="e.g. Verified with token receipt #..."
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setDeliverModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingDelivery}
              className="px-5 py-2 text-xs font-bold bg-[#2D8A39] hover:bg-[#1E6327] text-white rounded-xl shadow-xs transition-colors"
            >
              {submittingDelivery ? 'Recording Delivery...' : 'Confirm Delivery'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Admin Due Override Modal */}
      <Modal
        isOpen={overrideModalOpen}
        onClose={() => setOverrideModalOpen(false)}
        title="Admin Due Override & Delivery Release"
        subtitle={`Invoice: ${selectedReport?.invoice_number} | Outstanding: ৳${selectedReport?.due_amount}`}
        maxWidth="md"
      >
        <form onSubmit={handleConfirmOverride} className="space-y-4 text-xs">
          <div className="p-3 bg-[#FAF3EC] border border-[#CF8852] rounded-xl text-[#96572A]">
            <p className="font-semibold flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-[#CF8852]" />
              Audit Exception Requirement
            </p>
            <p className="text-[11px] mt-0.5">
              Releasing this report without collecting the pending due of ৳{selectedReport?.due_amount} will be
              recorded permanently under your Admin ID in the audit trail.
            </p>
          </div>

          <div>
            <label className="block text-[#54524A] font-semibold mb-1">Mandatory Override Justification *</label>
            <textarea
              required
              rows={3}
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="e.g. Emergency patient admitted to ICU, approved by Medical Director..."
              className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Recipient Name *</label>
              <input
                type="text"
                required
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
              />
            </div>
            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Relationship</label>
              <select
                value={recipientRelation}
                onChange={(e) => setRecipientRelation(e.target.value)}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl"
              >
                <option value="Self">Self</option>
                <option value="Attendant">Attendant / Nurse</option>
                <option value="Spouse">Spouse</option>
                <option value="Parent">Parent</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setOverrideModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submittingOverride}
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors"
            >
              {submittingOverride ? 'Authorizing...' : 'Authorize Override & Deliver'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Printable Report Modal */}
      <PrintableReportModal
        isOpen={printModalOpen}
        onClose={() => setPrintModalOpen(false)}
        report={selectedReport}
      />
    </div>
  );
};

