import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Search,
  UserPlus,
  Phone,
  Calendar,
  Eye,
  FileText,
  CreditCard,
  Droplet,
  MapPin,
  Clock,
  Activity,
  PlusCircle,
  FlaskConical,
} from 'lucide-react';
import { api } from '../../api/client';
import { Patient, PatientHistory, Gender, Invoice } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { DualCopyInvoiceModal } from '../../components/common/DualCopyInvoiceModal';
import { formatPaymentStatus, getPaymentStatusBadgeVariant } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

export const PatientsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const idParam = searchParams.get('id');
  const searchParam = searchParams.get('search');

  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState(searchParam || '');

  // Patient History Drawer/Modal State
  const [selectedHistory, setSelectedHistory] = useState<PatientHistory | null>(null);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyTab, setHistoryTab] = useState<'INVOICES' | 'PAYMENTS' | 'LAB_REPORTS' | 'VISITS'>('INVOICES');

  // Item 12: Nested Invoice Detail Overlay inside Patient History without route navigation
  const [nestedInvoice, setNestedInvoice] = useState<Invoice | null>(null);
  const [nestedInvoiceOpen, setNestedInvoiceOpen] = useState(false);

  // New Patient Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newPatient, setNewPatient] = useState<{
    full_name: string;
    phone: string;
    alternate_phone: string;
    gender: Gender;
    age_years: number | '';
    age_months: number | '';
    address: string;
    blood_group: string;
    notes: string;
  }>({
    full_name: '',
    phone: '',
    alternate_phone: '',
    gender: 'MALE',
    age_years: '',
    age_months: '',
    address: '',
    blood_group: '',
    notes: '',
  });

  const { showToast } = useToast();

  const fetchPatients = async () => {
    try {
      setLoading(true);
      const res = await api.getPatients(searchTerm.trim() || undefined);
      setPatients(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load patients', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPatients();
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    if (idParam) {
      handleOpenHistory(idParam);
    }
  }, [idParam]);

  const handleOpenHistory = async (patientId: string) => {
    try {
      setLoadingHistory(true);
      setHistoryModalOpen(true);
      const hist = await api.getPatientHistory(patientId);
      setSelectedHistory(hist);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load history', message: err.message });
      setHistoryModalOpen(false);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleViewNestedInvoice = async (invoiceId: string) => {
    try {
      const inv = await api.getInvoice(invoiceId);
      setNestedInvoice(inv);
      setNestedInvoiceOpen(true);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load invoice', message: err.message });
    }
  };

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPatient.full_name || !newPatient.phone) {
      showToast({ type: 'error', title: 'Required Fields', message: 'Name and Phone are mandatory.' });
      return;
    }

    try {
      const created = await api.createPatient({
        full_name: newPatient.full_name,
        phone: newPatient.phone,
        alternate_phone: newPatient.alternate_phone || null,
        gender: newPatient.gender,
        age_years: newPatient.age_years ? Number(newPatient.age_years) : null,
        age_months: newPatient.age_months ? Number(newPatient.age_months) : null,
        address: newPatient.address || null,
        blood_group: newPatient.blood_group || null,
        notes: newPatient.notes || null,
      });

      showToast({
        type: 'success',
        title: 'Patient Registered',
        message: `${created.full_name} assigned MRN: ${created.mrn}`,
      });
      setCreateModalOpen(false);
      setNewPatient({
        full_name: '',
        phone: '',
        alternate_phone: '',
        gender: 'MALE',
        age_years: '',
        age_months: '',
        address: '',
        blood_group: '',
        notes: '',
      });
      fetchPatients();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Registration Failed', message: err.message });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Patient Registry & History</h1>
          <p className="text-xs text-[#6D6A60]">
            Search patients by name, phone, or MRN. View longitudinal visit and diagnostic billing records.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name, phone, MRN..."
              className="text-xs bg-transparent border-none outline-none w-52 text-[#1B1B0E]"
            />
          </div>

          <button
            onClick={() => setCreateModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            <span>Register Patient</span>
          </button>
        </div>
      </div>

      {/* Patient List Card */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">MRN</th>
                <th className="pb-3">Patient Full Name</th>
                <th className="pb-3">Primary Phone</th>
                <th className="pb-3">Gender / Age</th>
                <th className="pb-3">Blood Group</th>
                <th className="pb-3">Address</th>
                <th className="pb-3">Registered On</th>
                <th className="pb-3 text-right pr-2">History</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {patients.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-[#8E8A7E]">
                    No patient records found.
                  </td>
                </tr>
              )}
              {patients.map((p) => (
                <tr key={p.id} className="hover:bg-[#F4F3F0] transition-colors">
                  <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{p.mrn}</td>
                  <td className="py-3 font-semibold text-[#1B1B0E]">{p.full_name}</td>
                  <td className="py-3 text-[#54524A]">
                    <div className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5 text-[#8E8A7E]" />
                      <span>{p.phone}</span>
                    </div>
                  </td>
                  <td className="py-3 text-[#6D6A60]">
                    {p.gender} {p.age_years ? `(${p.age_years}y)` : ''}
                  </td>
                  <td className="py-3">
                    {p.blood_group ? (
                      <span className="font-bold text-red-700 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded text-[11px]">
                        {p.blood_group}
                      </span>
                    ) : (
                      <span className="text-[#8E8A7E]">-</span>
                    )}
                  </td>
                  <td className="py-3 text-[#6D6A60] truncate max-w-xs">{p.address || '-'}</td>
                  <td className="py-3 text-[#6D6A60]">{new Date(p.created_at).toLocaleDateString('en-GB')}</td>
                  <td className="py-3 text-right pr-2">
                    <button
                      onClick={() => handleOpenHistory(p.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-[#525333] hover:bg-[#E8E7E3] rounded-lg border border-[#CAC7BE] transition-colors cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>History</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Patient History Modal */}
      <Modal
        isOpen={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        title={selectedHistory ? `Patient History — ${selectedHistory.full_name}` : 'Loading History...'}
        subtitle={selectedHistory ? `MRN: ${selectedHistory.mrn} | Contact: ${selectedHistory.phone}` : ''}
        maxWidth="4xl"
      >
        {selectedHistory && (
          <div className="space-y-5 text-xs">
            {/* Header Action & Demographics */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#FAF9F6] border border-[#DCDAD4] p-3.5 rounded-2xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#525333]/10 flex items-center justify-center font-bold text-[#525333] text-sm">
                  {selectedHistory.full_name?.charAt(0) || 'P'}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-[#1B1B0E]">{selectedHistory.full_name}</span>
                    <Badge variant="neutral" size="sm">{selectedHistory.gender}</Badge>
                  </div>
                  <span className="text-[11px] text-[#6D6A60]">
                    MRN: <strong className="font-mono text-[#1B1B0E]">{selectedHistory.mrn}</strong> | Contact: {selectedHistory.phone} {selectedHistory.address ? `| ${selectedHistory.address}` : ''}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setHistoryModalOpen(false);
                  navigate(`/invoices/new?patient_id=${selectedHistory.id}`);
                }}
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
                <span className="text-xl font-bold text-[#CF8852]">{selectedHistory.total_visits}</span>
              </div>
              <div className="bg-[#EDF7EE] border border-[#C3E6C7] p-3 rounded-xl text-center">
                <span className="text-[11px] text-[#1E6327] block font-medium">Lifetime Spent</span>
                <span className="text-xl font-bold text-[#1E6327]">
                  ৳{selectedHistory.total_spent.toLocaleString()}
                </span>
              </div>
              <div className="bg-[#FDF2F0] border border-[#F8CBC6] p-3 rounded-xl text-center">
                <span className="text-[11px] text-[#9C2417] block font-medium">Outstanding Due</span>
                <span className="text-xl font-bold text-[#9C2417]">
                  ৳{selectedHistory.total_due.toLocaleString()}
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
                <span>Invoices & Tests ({selectedHistory.invoices.length})</span>
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
                <span>Payments & Receipts ({selectedHistory.payments?.length || 0})</span>
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
                <span>Visits History ({selectedHistory.visits?.length || 0})</span>
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
                      <th className="p-2.5">Tests Summary</th>
                      <th className="p-2.5 text-right">Net</th>
                      <th className="p-2.5 text-right">Paid</th>
                      <th className="p-2.5 text-right">Due</th>
                      <th className="p-2.5 text-center">Status</th>
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {selectedHistory.invoices.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="p-4 text-center text-[#8E8A7E]">
                          No invoices generated for this patient yet.
                        </td>
                      </tr>
                    ) : (
                      selectedHistory.invoices.map((inv) => (
                        <tr key={inv.id} className="hover:bg-[#F4F3F0]">
                          <td className="p-2.5 font-mono font-bold text-[#1B1B0E]">{inv.invoice_number}</td>
                          <td className="p-2.5 text-[#6D6A60]">
                            {new Date(inv.created_at).toLocaleDateString('en-GB')}
                          </td>
                          <td className="p-2.5 text-[#6D6A60]">
                            {inv.tests_summary && inv.tests_summary.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {inv.tests_summary.map((t: string, idx: number) => (
                                  <span key={idx} className="bg-[#E8E7E3] text-[#525333] px-1.5 py-0.5 rounded text-[10px] font-medium">
                                    {t}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span>{inv.lines_count} tests</span>
                            )}
                          </td>
                          <td className="p-2.5 text-right font-medium">৳{inv.net_amount.toLocaleString()}</td>
                          <td className="p-2.5 text-right text-[#1E6327] font-semibold">
                            ৳{inv.paid_amount.toLocaleString()}
                          </td>
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
                      <th className="p-2.5">Receipt #</th>
                      <th className="p-2.5">Invoice #</th>
                      <th className="p-2.5">Date & Time</th>
                      <th className="p-2.5">Method</th>
                      <th className="p-2.5 text-right">Amount</th>
                      <th className="p-2.5">Reference</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {(!selectedHistory.payments || selectedHistory.payments.length === 0) ? (
                      <tr>
                        <td colSpan={6} className="p-4 text-center text-[#8E8A7E]">
                          No payment receipts recorded for this patient yet.
                        </td>
                      </tr>
                    ) : (
                      selectedHistory.payments.map((pmt) => (
                        <tr key={pmt.id} className="hover:bg-[#F4F3F0]">
                          <td className="p-2.5 font-mono text-[#525333] font-semibold">RCP-{String(pmt.id).padStart(5, '0')}</td>
                          <td className="p-2.5 font-mono font-bold text-[#1B1B0E]">{pmt.invoice_no}</td>
                          <td className="p-2.5 text-[#6D6A60]">
                            {new Date(pmt.received_at).toLocaleString('en-GB')}
                          </td>
                          <td className="p-2.5">
                            <Badge variant="neutral" size="sm">{pmt.method}</Badge>
                          </td>
                          <td className="p-2.5 text-right font-bold text-[#1E6327]">
                            ৳{pmt.amount.toLocaleString()}
                          </td>
                          <td className="p-2.5 text-[#6D6A60] font-mono text-[11px]">
                            {pmt.reference || '-'}
                          </td>
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
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E8E7E3]">
                    {selectedHistory.invoices.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="p-4 text-center text-[#8E8A7E]">
                          No investigations recorded for this patient.
                        </td>
                      </tr>
                    ) : (
                      selectedHistory.invoices.map((inv) => (
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
                          <td className="p-2.5 text-right">
                            <button
                              type="button"
                              onClick={() => {
                                setHistoryModalOpen(false);
                                navigate(`/reports?search=${inv.invoice_number}`);
                              }}
                              className="px-2 py-1 text-[11px] font-medium text-[#CF8852] hover:bg-[#FAF3EC] rounded border border-[#E6C4A7] transition-colors"
                            >
                              Reports
                            </button>
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
                    {(!selectedHistory.visits || selectedHistory.visits.length === 0) ? (
                      <tr>
                        <td colSpan={4} className="p-4 text-center text-[#8E8A7E]">
                          No diagnostic visits logged.
                        </td>
                      </tr>
                    ) : (
                      selectedHistory.visits.map((v) => (
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

      {/* Register New Patient Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Register New Patient"
        subtitle="Intake form with phone duplication check"
        maxWidth="lg"
      >
        <form onSubmit={handleCreatePatient} className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-[#54524A] font-semibold mb-1">Patient Full Name *</label>
              <input
                type="text"
                required
                value={newPatient.full_name}
                onChange={(e) => setNewPatient({ ...newPatient, full_name: e.target.value })}
                placeholder="e.g. Mohammad Rahim"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Phone Number *</label>
              <input
                type="tel"
                required
                value={newPatient.phone}
                onChange={(e) => setNewPatient({ ...newPatient, phone: e.target.value })}
                placeholder="01711000000"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Alternate Phone</label>
              <input
                type="tel"
                value={newPatient.alternate_phone}
                onChange={(e) => setNewPatient({ ...newPatient, alternate_phone: e.target.value })}
                placeholder="Optional"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Gender *</label>
              <select
                value={newPatient.gender}
                onChange={(e) => setNewPatient({ ...newPatient, gender: e.target.value as Gender })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              >
                <option value="MALE">Male</option>
                <option value="FEMALE">Female</option>
                <option value="OTHER">Other</option>
              </select>
            </div>

            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-[#54524A] font-semibold mb-1">Age (Years)</label>
                <input
                  type="number"
                  min="0"
                  max="125"
                  value={newPatient.age_years}
                  onChange={(e) =>
                    setNewPatient({ ...newPatient, age_years: e.target.value ? Number(e.target.value) : '' })
                  }
                  placeholder="Y"
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
                />
              </div>
              <div className="w-16">
                <label className="block text-[#54524A] font-semibold mb-1">Months</label>
                <input
                  type="number"
                  min="0"
                  max="11"
                  value={newPatient.age_months}
                  onChange={(e) =>
                    setNewPatient({ ...newPatient, age_months: e.target.value ? Number(e.target.value) : '' })
                  }
                  placeholder="M"
                  className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Blood Group</label>
              <select
                value={newPatient.blood_group}
                onChange={(e) => setNewPatient({ ...newPatient, blood_group: e.target.value })}
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              >
                <option value="">Unknown</option>
                <option value="A+">A+</option>
                <option value="A-">A-</option>
                <option value="B+">B+</option>
                <option value="B-">B-</option>
                <option value="AB+">AB+</option>
                <option value="AB-">AB-</option>
                <option value="O+">O+</option>
                <option value="O-">O-</option>
              </select>
            </div>

            <div>
              <label className="block text-[#54524A] font-semibold mb-1">Address</label>
              <input
                type="text"
                value={newPatient.address}
                onChange={(e) => setNewPatient({ ...newPatient, address: e.target.value })}
                placeholder="Area, Thana, City"
                className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#E8E7E3]">
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 text-xs font-bold bg-[#CF8852] hover:bg-[#B7703B] text-white rounded-xl shadow-xs transition-colors"
            >
              Register Patient
            </button>
          </div>
        </form>
      </Modal>

      {/* Item 12: Nested Invoice Detail Overlay inside Patient History without navigation */}
      <DualCopyInvoiceModal
        isOpen={nestedInvoiceOpen}
        onClose={() => setNestedInvoiceOpen(false)}
        savedInvoice={nestedInvoice}
      />
    </div>
  );
};

