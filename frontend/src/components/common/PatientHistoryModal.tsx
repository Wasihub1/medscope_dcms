import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  CreditCard,
  Droplet,
  Clock,
  PlusCircle,
  Eye,
  Loader2,
} from 'lucide-react';
import { Modal } from './Modal';
import { DualCopyInvoiceModal } from './DualCopyInvoiceModal';
import { Badge } from './Badge';
import { api } from '../../api/client';
import { PatientHistory, Invoice } from '../../types';
import { formatPaymentStatus, getPaymentStatusBadgeVariant } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

interface PatientHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  patientId: string | number | null;
  /**
   * If provided, custom callback when "New Invoice with Patient" is clicked.
   * Otherwise navigates to /invoices/new?patient_id=...
   */
  onNewInvoice?: (patientId: string | number) => void;
}

export const PatientHistoryModal: React.FC<PatientHistoryModalProps> = ({
  isOpen,
  onClose,
  patientId,
  onNewInvoice,
}) => {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [history, setHistory] = useState<PatientHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyTab, setHistoryTab] = useState<'INVOICES' | 'PAYMENTS' | 'LAB_REPORTS' | 'VISITS'>('INVOICES');

  // Nested Invoice Detail Overlay inside Patient History without route navigation
  const [nestedInvoice, setNestedInvoice] = useState<Invoice | null>(null);
  const [nestedInvoiceOpen, setNestedInvoiceOpen] = useState(false);

  useEffect(() => {
    if (!isOpen || !patientId) {
      setHistory(null);
      return;
    }

    let isMounted = true;
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const hist = await api.getPatientHistory(String(patientId));
        if (isMounted) {
          setHistory(hist);
        }
      } catch (err: any) {
        if (isMounted) {
          showToast({ type: 'error', title: 'Failed to load history', message: err.message });
          onClose();
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchHistory();
    return () => {
      isMounted = false;
    };
  }, [isOpen, patientId]);

  const handleViewNestedInvoice = async (invoiceId: string) => {
    try {
      const inv = await api.getInvoice(invoiceId);
      setNestedInvoice(inv);
      setNestedInvoiceOpen(true);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load invoice', message: err.message });
    }
  };

  const handleNewInvoiceClick = () => {
    if (!history) return;
    onClose();
    if (onNewInvoice) {
      onNewInvoice(history.id);
    } else {
      navigate(`/invoices/new?patient_id=${history.id}`);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={history ? `Patient History — ${history.full_name}` : 'Loading History...'}
        subtitle={history ? `MRN: ${history.mrn} | Contact: ${history.phone}` : ''}
        maxWidth="4xl"
      >
        {loading && (
          <div className="py-12 flex flex-col items-center justify-center gap-2 text-[#6D6A60]">
            <Loader2 className="w-8 h-8 animate-spin text-[#CF8852]" />
            <p className="text-xs font-medium">Fetching patient operational history...</p>
          </div>
        )}

        {!loading && history && (
          <div className="space-y-5 text-xs">
            {/* Header Action & Demographics */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#FAF9F6] border border-[#DCDAD4] p-3.5 rounded-2xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#525333]/10 flex items-center justify-center font-bold text-[#525333] text-sm">
                  {history.full_name?.charAt(0) || 'P'}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-[#1B1B0E]">{history.full_name}</span>
                    <Badge variant="neutral" size="sm">{history.gender}</Badge>
                  </div>
                  <span className="text-[11px] text-[#6D6A60]">
                    MRN: <strong className="font-mono text-[#1B1B0E]">{history.mrn}</strong> | Contact: {history.phone} {history.address ? `| ${history.address}` : ''}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={handleNewInvoiceClick}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors shrink-0 cursor-pointer"
              >
                <PlusCircle className="w-4 h-4" />
                <span>New Invoice with Patient</span>
              </button>
            </div>

            {/* Stat Chips */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-[#FAF3EC] border border-[#E6C4A7] p-3 rounded-xl text-center">
                <span className="text-[11px] text-[#96572A] block font-medium">Total Diagnostic Visits</span>
                <span className="text-xl font-bold text-[#CF8852]">{history.total_visits}</span>
              </div>
              <div className="bg-[#EDF7EE] border border-[#C3E6C7] p-3 rounded-xl text-center">
                <span className="text-[11px] text-[#1E6327] block font-medium">Lifetime Spent</span>
                <span className="text-xl font-bold text-[#1E6327]">
                  ৳{history.total_spent.toLocaleString()}
                </span>
              </div>
              <div className="bg-[#FDF2F0] border border-[#F8CBC6] p-3 rounded-xl text-center">
                <span className="text-[11px] text-[#9C2417] block font-medium">Outstanding Due</span>
                <span className="text-xl font-bold text-[#9C2417]">
                  ৳{history.total_due.toLocaleString()}
                </span>
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-[#DCDAD4] gap-2">
              <button
                type="button"
                onClick={() => setHistoryTab('INVOICES')}
                className={`pb-2.5 px-3 font-semibold text-xs border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                  historyTab === 'INVOICES'
                    ? 'border-[#525333] text-[#525333]'
                    : 'border-transparent text-[#6D6A60] hover:text-[#1B1B0E]'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Invoices & Tests ({history.invoices.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setHistoryTab('PAYMENTS')}
                className={`pb-2.5 px-3 font-semibold text-xs border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                  historyTab === 'PAYMENTS'
                    ? 'border-[#525333] text-[#525333]'
                    : 'border-transparent text-[#6D6A60] hover:text-[#1B1B0E]'
                }`}
              >
                <CreditCard className="w-3.5 h-3.5" />
                <span>Payments & Receipts ({history.payments?.length || 0})</span>
              </button>

              <button
                type="button"
                onClick={() => setHistoryTab('LAB_REPORTS')}
                className={`pb-2.5 px-3 font-semibold text-xs border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                  historyTab === 'LAB_REPORTS'
                    ? 'border-[#525333] text-[#525333]'
                    : 'border-transparent text-[#6D6A60] hover:text-[#1B1B0E]'
                }`}
              >
                <Droplet className="w-3.5 h-3.5" />
                <span>Specimens & Reports</span>
              </button>

              <button
                type="button"
                onClick={() => setHistoryTab('VISITS')}
                className={`pb-2.5 px-3 font-semibold text-xs border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                  historyTab === 'VISITS'
                    ? 'border-[#525333] text-[#525333]'
                    : 'border-transparent text-[#6D6A60] hover:text-[#1B1B0E]'
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>Visits History ({history.visits?.length || 0})</span>
              </button>
            </div>

            {/* Tab 1: Invoices */}
            {historyTab === 'INVOICES' && (
              <div className="border border-[#DCDAD4] rounded-xl overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-[#E8E7E3]/60 text-[#6D6A60] font-semibold border-b border-[#DCDAD4]">
                    <tr>
                      <th className="p-2.5">Invoice #</th>
                      <th className="p-2.5">Date</th>
                      <th className="p-2.5 text-right">Net</th>
                      <th className="p-2.5 text-right">Paid</th>
                      <th className="p-2.5 text-right">Due</th>
                      <th className="p-2.5 text-center">Status</th>
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {history.invoices.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-4 text-center text-[#8E8A7E]">
                          No invoices recorded for this patient.
                        </td>
                      </tr>
                    ) : (
                      history.invoices.map((inv) => (
                        <tr key={inv.id} className="hover:bg-[#F4F3F0]">
                          <td className="p-2.5 font-mono font-bold text-[#1B1B0E]">{inv.invoice_number}</td>
                          <td className="p-2.5 text-[#6D6A60]">
                            {new Date(inv.created_at).toLocaleDateString('en-GB')}
                          </td>
                          <td className="p-2.5 text-right font-medium">৳{inv.net_amount.toLocaleString()}</td>
                          <td className="p-2.5 text-right text-green-700 font-semibold">৳{inv.paid_amount.toLocaleString()}</td>
                          <td className="p-2.5 text-right font-semibold">
                            {inv.due_amount > 0 ? (
                              <span className="text-red-700">৳{inv.due_amount.toLocaleString()}</span>
                            ) : (
                              '৳0'
                            )}
                          </td>
                          <td className="p-2.5 text-center">
                            <Badge
                              variant={getPaymentStatusBadgeVariant(inv.payment_status, inv.paid_amount, inv.due_amount)}
                              size="sm"
                            >
                              {formatPaymentStatus(inv.payment_status, inv.paid_amount, inv.due_amount)}
                            </Badge>
                          </td>
                          <td className="p-2.5 text-right">
                            <button
                              type="button"
                              data-testid={`view-nested-invoice-${inv.id}`}
                              onClick={() => handleViewNestedInvoice(inv.id)}
                              className="px-2 py-1 text-[11px] font-medium text-[#525333] hover:bg-[#E8E7E3] rounded border border-[#CAC7BE] transition-colors cursor-pointer"
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 2: Payments */}
            {historyTab === 'PAYMENTS' && (
              <div className="border border-[#DCDAD4] rounded-xl overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-[#E8E7E3]/60 text-[#6D6A60] font-semibold border-b border-[#DCDAD4]">
                    <tr>
                      <th className="p-2.5">Date</th>
                      <th className="p-2.5">Invoice #</th>
                      <th className="p-2.5">Method</th>
                      <th className="p-2.5">Reference</th>
                      <th className="p-2.5 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {(!history.payments || history.payments.length === 0) ? (
                      <tr>
                        <td colSpan={5} className="p-4 text-center text-[#8E8A7E]">
                          No payment receipts recorded for this patient.
                        </td>
                      </tr>
                    ) : (
                      history.payments.map((p) => (
                        <tr key={p.id} className="hover:bg-[#F4F3F0]">
                          <td className="p-2.5 text-[#6D6A60]">
                            {new Date(p.received_at).toLocaleDateString('en-GB')}
                          </td>
                          <td className="p-2.5 font-mono text-[#1B1B0E]">{p.invoice_no || '—'}</td>
                          <td className="p-2.5 font-semibold text-[#525333]">{p.method}</td>
                          <td className="p-2.5 text-[#6D6A60]">{p.reference || '—'}</td>
                          <td className="p-2.5 text-right font-bold text-[#1E6327]">৳{p.amount.toLocaleString()}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 3: Lab Reports & Specimens */}
            {historyTab === 'LAB_REPORTS' && (
              <div className="border border-[#DCDAD4] rounded-xl overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-[#E8E7E3]/60 text-[#6D6A60] font-semibold border-b border-[#DCDAD4]">
                    <tr>
                      <th className="p-2.5">Invoice #</th>
                      <th className="p-2.5">Tests Summary</th>
                      <th className="p-2.5 text-center">Sample State</th>
                      <th className="p-2.5 text-center">Report State</th>
                      <th className="p-2.5 text-center">Delivery</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {history.invoices.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-4 text-center text-[#8E8A7E]">
                          No investigations recorded for this patient.
                        </td>
                      </tr>
                    ) : (
                      history.invoices.map((inv) => (
                        <tr key={inv.id} className="hover:bg-[#F4F3F0]">
                          <td className="p-2.5 font-mono font-bold text-[#1B1B0E]">{inv.invoice_number}</td>
                          <td className="p-2.5 text-[#6D6A60]">
                            {inv.tests_summary?.join(', ') || `${inv.lines_count} tests`}
                          </td>
                          <td className="p-2.5 text-center">
                            <Badge
                              variant={inv.sample_status === 'COLLECTED' ? 'success' : 'neutral'}
                              size="sm"
                            >
                              {inv.sample_status || 'PENDING'}
                            </Badge>
                          </td>
                          <td className="p-2.5 text-center">
                            <Badge
                              variant={
                                inv.report_status === 'FINAL' || inv.report_status === 'AUTHORIZED'
                                  ? 'success'
                                  : inv.report_status === 'PARTIAL'
                                  ? 'warning'
                                  : 'neutral'
                              }
                              size="sm"
                            >
                              {inv.report_status || 'PENDING'}
                            </Badge>
                          </td>
                          <td className="p-2.5 text-center">
                            <Badge
                              variant={inv.report_delivery_status === 'DELIVERED' ? 'success' : 'neutral'}
                              size="sm"
                            >
                              {inv.report_delivery_status || 'UNDELIVERED'}
                            </Badge>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 4: Visits History */}
            {historyTab === 'VISITS' && (
              <div className="border border-[#DCDAD4] rounded-xl overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-[#E8E7E3]/60 text-[#6D6A60] font-semibold border-b border-[#DCDAD4]">
                    <tr>
                      <th className="p-2.5">Visit Code</th>
                      <th className="p-2.5">Visit Date</th>
                      <th className="p-2.5">Patient Age at Visit</th>
                      <th className="p-2.5">Gender</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {(!history.visits || history.visits.length === 0) ? (
                      <tr>
                        <td colSpan={4} className="p-4 text-center text-[#8E8A7E]">
                          No diagnostic visits logged.
                        </td>
                      </tr>
                    ) : (
                      history.visits.map((v) => (
                        <tr key={v.visit_id} className="hover:bg-[#F4F3F0]">
                          <td className="p-2.5 font-mono font-bold text-[#1B1B0E]">{v.visit_number}</td>
                          <td className="p-2.5 text-[#6D6A60]">
                            {new Date(v.visit_date).toLocaleDateString('en-GB')}
                          </td>
                          <td className="p-2.5 text-[#6D6A60]">{v.age_summary}</td>
                          <td className="p-2.5 text-[#6D6A60]">{v.gender}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Item 12: Nested Invoice Detail Overlay inside Patient History without navigation */}
      <DualCopyInvoiceModal
        isOpen={nestedInvoiceOpen}
        onClose={() => setNestedInvoiceOpen(false)}
        savedInvoice={nestedInvoice}
      />
    </>
  );
};
