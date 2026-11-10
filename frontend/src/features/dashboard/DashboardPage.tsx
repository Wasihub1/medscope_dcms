import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CalendarDays,
  PlusCircle,
  GitBranch,
  CreditCard,
  FileCheck,
  TrendingUp,
  AlertTriangle,
  RotateCcw,
  Users,
  Receipt,
  ArrowUpRight,
  Printer,
  Eye,
  Loader2,
} from 'lucide-react';
import { api } from '../../api/client';
import { DashboardMetrics, Invoice } from '../../types';
import { Badge } from '../../components/common/Badge';
import { DualCopyInvoiceModal } from '../../components/common/DualCopyInvoiceModal';
import { formatPaymentStatus, getPaymentStatusBadgeVariant } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';

export const DashboardPage: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [isReprint, setIsReprint] = useState(false);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const data = await api.getDashboard();
      setMetrics(data);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load dashboard', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleReprint = async (invoiceId: string) => {
    try {
      const res = await api.reprintInvoice(invoiceId, 'Dashboard quick reprint');
      setSelectedInvoice(res);
      setIsReprint(true);
      setReceiptOpen(true);
      showToast({ type: 'info', title: 'Receipt Reprint', message: `Printed duplicate #${res.reprint_count || 1}` });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Reprint Failed', message: err.message });
    }
  };

  const handleViewInvoice = async (invoiceId: string) => {
    try {
      const inv = await api.getInvoice(invoiceId);
      setSelectedInvoice(inv);
      setIsReprint(false);
      setReceiptOpen(true);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load invoice', message: err.message });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-[#CF8852] animate-spin" />
      </div>
    );
  }

  const day = metrics?.business_day;

  return (
    <div className="space-y-6">
      {/* Bento Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-5">
        {/* Tile 1: Business Day Status (Col span 2) */}
        <div className="md:col-span-2 bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6D6A60]">
                Business Day Lifecycle
              </span>
              <div className="flex items-center gap-2.5">
                <h2 className="text-xl font-bold text-[#1B1B0E]">
                  {day ? `Day #${day.day_number} — ${day.business_date}` : 'No Active Business Day'}
                </h2>
                {day ? (
                  <Badge variant="success" dot>
                    Active
                  </Badge>
                ) : (
                  <Badge variant="danger" dot>
                    Closed
                  </Badge>
                )}
              </div>
              <p className="text-xs text-[#6D6A60]">
                {day
                  ? `Opened at ${new Date(day.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} by ${day.opened_by_name || 'Reception Staff'}`
                  : 'Open a business day to begin intake and transactions.'}
              </p>
            </div>
            <button
              onClick={() => navigate('/business-day')}
              className="p-2 text-[#525333] hover:bg-[#E8E7E3] rounded-xl transition-colors cursor-pointer"
              title="View Business Day Ledger"
            >
              <ArrowUpRight className="w-5 h-5" />
            </button>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-[#E8E7E3]">
            <div>
              <span className="text-[11px] text-[#6D6A60] block">Opening Float</span>
              <span className="text-base font-bold text-[#1B1B0E]">
                ৳{day ? day.opening_balance.toLocaleString() : '0'}
              </span>
            </div>
            <div>
              <span className="text-[11px] text-[#6D6A60] block">Today's Collections</span>
              <span className="text-base font-bold text-[#1E6327]">
                ৳{day ? day.total_collections.toLocaleString() : '0'}
              </span>
            </div>
            <div>
              <span className="text-[11px] text-[#6D6A60] block">Current Balance</span>
              <span className="text-base font-bold text-[#525333]">
                ৳{day ? day.current_balance.toLocaleString() : '0'}
              </span>
            </div>
          </div>
        </div>

        {/* Tile 2: Receptionist Quick Actions (Col span 2) */}
        <div className="md:col-span-2 bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6D6A60]">
            Quick Reception Actions
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 my-auto py-2">
            <button
              onClick={() => navigate('/invoices/new')}
              className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#FAF3EC] border border-[#E6C4A7] text-[#96572A] hover:bg-[#F3E4D6] transition-all cursor-pointer group shadow-2xs"
            >
              <PlusCircle className="w-5 h-5 mb-1.5 text-[#CF8852] group-hover:scale-110 transition-transform" />
              <span className="text-xs font-semibold">New Invoice</span>
            </button>
            <button
              onClick={() => navigate('/assignments')}
              className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#F2F3EC] border border-[#C2C6A4] text-[#444529] hover:bg-[#E2E4D4] transition-all cursor-pointer group shadow-2xs"
            >
              <GitBranch className="w-5 h-5 mb-1.5 text-[#525333] group-hover:scale-110 transition-transform" />
              <span className="text-xs font-semibold">Assign Tests</span>
            </button>
            <button
              onClick={() => navigate('/dues')}
              className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#FEF7EC] border border-[#FBE0B2] text-[#8A5608] hover:bg-[#FDF0DA] transition-all cursor-pointer group shadow-2xs"
            >
              <CreditCard className="w-5 h-5 mb-1.5 text-[#D9820B] group-hover:scale-110 transition-transform" />
              <span className="text-xs font-semibold">Settle Due</span>
            </button>
            <button
              onClick={() => navigate('/reports')}
              className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#EDF7EE] border border-[#C3E6C7] text-[#1E6327] hover:bg-[#DCF1DE] transition-all cursor-pointer group shadow-2xs"
            >
              <FileCheck className="w-5 h-5 mb-1.5 text-[#2D8A39] group-hover:scale-110 transition-transform" />
              <span className="text-xs font-semibold">Ready Reports</span>
            </button>
          </div>
          <span className="text-[11px] text-[#8E8A7E] italic">Fast keyboard shortcuts available</span>
        </div>

        {/* Tile 3: Today Patients Counter */}
        <div
          onClick={() => navigate('/patients')}
          className="bg-[#FAF9F6] border border-[#DCDAD4] hover:border-[#CF8852] rounded-2xl p-4.5 shadow-xs flex flex-col justify-between cursor-pointer transition-all hover:shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6D6A60]">Today's Intake</span>
            <div className="p-2 bg-[#EDF5F7] text-[#185B68] rounded-xl">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-[#1B1B0E]">
              {metrics?.active_patients_today ?? 0}
            </span>
            <span className="text-xs text-[#6D6A60] block mt-0.5">
              Patients Registered Today
            </span>
          </div>
          <div className="mt-2 text-[11px] text-[#185B68] font-medium flex items-center justify-between">
            <span>{metrics?.today_invoices_count ?? 0} Invoices generated</span>
            <span className="text-xs">&rarr;</span>
          </div>
        </div>

        {/* Tile 4: Collections & Net Amount */}
        <div
          onClick={() => navigate('/invoices')}
          className="bg-[#FAF9F6] border border-[#DCDAD4] hover:border-[#CF8852] rounded-2xl p-4.5 shadow-xs flex flex-col justify-between cursor-pointer transition-all hover:shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6D6A60]">Net Revenue</span>
            <div className="p-2 bg-[#EDF7EE] text-[#1E6327] rounded-xl">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-extrabold text-[#1B1B0E]">
              ৳{metrics?.today_net_amount.toLocaleString() ?? '0'}
            </span>
            <span className="text-xs text-[#1E6327] font-semibold block mt-0.5">
              ৳{metrics?.today_paid_amount.toLocaleString() ?? '0'} Collected
            </span>
          </div>
          <div className="mt-2 text-[11px] text-[#8A5608] flex items-center justify-between">
            <span>৳{metrics?.today_due_amount.toLocaleString() ?? '0'} Pending Due</span>
            <span className="text-xs">&rarr;</span>
          </div>
        </div>

        {/* Tile 5: Urgent Attention Queue */}
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-4.5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6D6A60]">Urgent Queue</span>
            <div className="p-2 bg-[#FEF7EC] text-[#8A5608] rounded-xl">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 space-y-2">
            <div
              onClick={() => navigate('/assignments')}
              className="flex items-center justify-between p-2 bg-[#F4F3F0] hover:bg-[#E8E7E3] rounded-lg cursor-pointer transition-colors"
            >
              <span className="text-xs text-[#54524A]">Unassigned Tests</span>
              <span className="text-xs font-bold px-2 py-0.5 bg-[#FAF3EC] text-[#96572A] border border-[#E6C4A7] rounded-full">
                {metrics?.unassigned_tests_count ?? 0}
              </span>
            </div>
            <div
              onClick={() => navigate('/reports?has_due=true')}
              className="flex items-center justify-between p-2 bg-[#F4F3F0] hover:bg-[#E8E7E3] rounded-lg cursor-pointer transition-colors"
            >
              <span className="text-xs text-[#54524A]">Due-Held Reports</span>
              <span className="text-xs font-bold px-2 py-0.5 bg-[#FDF2F0] text-[#9C2417] border border-[#F8CBC6] rounded-full">
                {metrics?.held_reports_count ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Tile 6: Pending Refund Requests */}
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-4.5 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6D6A60]">Refund Requests</span>
            <div className="p-2 bg-[#FAF3EC] text-[#96572A] rounded-xl">
              <RotateCcw className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-extrabold text-[#CF8852]">
              {metrics?.pending_refunds_count ?? 0}
            </span>
            <span className="text-xs text-[#6D6A60] block mt-0.5">
              Pending Admin Review
            </span>
          </div>
          <button
            onClick={() => navigate('/refunds')}
            className="mt-2 text-xs text-[#CF8852] hover:text-[#96572A] font-semibold text-left"
          >
            Review Status &rarr;
          </button>
        </div>
      </div>

      {/* Tile 7: Recent Invoices Table */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-[#1B1B0E]">Recent Invoices</h3>
            <p className="text-xs text-[#6D6A60]">Latest patient visits and diagnostic billing records</p>
          </div>
          <button
            onClick={() => navigate('/invoices')}
            className="text-xs font-semibold text-[#CF8852] hover:text-[#96572A] flex items-center gap-1 cursor-pointer"
          >
            <span>View All Invoices</span>
            <ArrowUpRight className="w-4 h-4" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Invoice #</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3">Contact</th>
                <th className="pb-3 text-right">Net</th>
                <th className="pb-3 text-right">Paid</th>
                <th className="pb-3 text-right">Due</th>
                <th className="pb-3 text-center">Status</th>
                <th className="pb-3 text-right pr-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {metrics?.recent_invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-[#F4F3F0] transition-colors">
                  <td
                    onClick={() => navigate(`/invoices?id=${inv.id}`)}
                    className="py-3 pl-2 font-mono font-bold text-[#1B1B0E] hover:text-[#CF8852] hover:underline cursor-pointer"
                  >
                    {inv.invoice_number}
                  </td>
                  <td className="py-3 font-semibold text-[#1B1B0E]">{inv.patient_name}</td>
                  <td className="py-3 text-[#6D6A60]">{inv.patient_phone}</td>
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
                  <td className="py-3 text-right pr-2 space-x-1.5">
                    <button
                      onClick={() => handleViewInvoice(inv.id)}
                      className="p-1.5 text-[#525333] hover:bg-[#E8E7E3] rounded-lg transition-colors cursor-pointer"
                      title="View Receipt"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleReprint(inv.id)}
                      className="p-1.5 text-[#CF8852] hover:bg-[#FAF3EC] rounded-lg transition-colors cursor-pointer"
                      title="Reprint Duplicate Receipt"
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

      {/* Dual Copy Invoice Modal */}
      <DualCopyInvoiceModal
        isOpen={receiptOpen}
        onClose={() => setReceiptOpen(false)}
        savedInvoice={selectedInvoice}
        isReprint={isReprint}
      />
    </div>
  );
};

