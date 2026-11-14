import React, { useCallback, useEffect, useState } from 'react';
import { CreditCard, Search, CheckCircle2, ArrowRight, Phone, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import { DuesCallList, DoctorBalances, WriteOffRecord } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { SettleDueModal } from '../../components/common/SettleDueModal';
import { formatPaymentStatus, getPaymentStatusBadgeVariant } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

/**
 * Dues (Module 18, Prompt 17). Tabs: Bills (derived list with 7 / 30 / 90 day age buckets, settle, write-off),
 * Call list (patients to phone, oldest first), Write-offs (requests above the Admin limit; Owner decides) and
 * Doctor balances (two separate figures per doctor, never merged).
 */
const BUCKETS = ['0-7', '8-30', '31-90', '90+'] as const;
const bucketLabel = (b: string) => (b === '90+' ? 'Over 90 days' : `${b} days`);
const bucketVariant = (b: string): 'success' | 'warning' | 'danger' | 'orange' =>
  b === '0-7' ? 'success' : b === '8-30' ? 'warning' : b === '31-90' ? 'orange' : 'danger';
const tk = (n: number) => `৳${n.toLocaleString()}`;

type Tab = 'BILLS' | 'CALLS' | 'WRITEOFFS' | 'DOCTORS';

export const DuesPage: React.FC = () => {
  const { hasPermission, role } = useAuth();
  const { showToast } = useToast();
  const canWriteOff = hasPermission('due.writeoff');
  const canSeeDoctors = hasPermission('doctor_balance.view');
  const [tab, setTab] = useState<Tab>('BILLS');
  const [dueInvoices, setDueInvoices] = useState<any[]>([]);
  const [calls, setCalls] = useState<DuesCallList | null>(null);
  const [writeOffs, setWriteOffs] = useState<WriteOffRecord[]>([]);
  const [balances, setBalances] = useState<DoctorBalances | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [bucket, setBucket] = useState<string>('');
  const [settleId, setSettleId] = useState<string | number | null>(null);
  const [writeOffFor, setWriteOffFor] = useState<any | null>(null);
  const [woAmount, setWoAmount] = useState(0);
  const [woReason, setWoReason] = useState('');
  const [woBusy, setWoBusy] = useState(false);
  const [adminLimit, setAdminLimit] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      if (tab === 'BILLS') setDueInvoices(await api.getDues(searchTerm.trim() || undefined, bucket || undefined));
      if (tab === 'CALLS') setCalls(await api.getDuesCallList(bucket || undefined, searchTerm.trim() || undefined));
      if (tab === 'WRITEOFFS') setWriteOffs(await api.listWriteOffs());
      if (tab === 'DOCTORS') setBalances(await api.getDoctorBalances());
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [tab, searchTerm, bucket, showToast]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    if (canWriteOff) api.getCenterSettings().then((s) => setAdminLimit(s.writeoff_admin_limit)).catch(() => setAdminLimit(null));
  }, [canWriteOff]);

  const openWriteOff = (inv: any) => {
    setWriteOffFor(inv);
    setWoAmount(inv.due_amount);
    setWoReason('');
  };

  const submitWriteOff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!writeOffFor) return;
    setWoBusy(true);
    try {
      const r = await api.writeOffDue(writeOffFor.invoice_id ?? writeOffFor.id, { amount: woAmount, reason: woReason.trim() });
      showToast(
        r.status === 'APPLIED'
          ? { type: 'success', title: 'Written off', message: `৳${r.amount} written off as bad debt (not a discount).` }
          : { type: 'info', title: 'Sent to the Owner', message: 'This amount is above the Admin limit; the Owner must approve it.' }
      );
      setWriteOffFor(null);
      load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Write-off failed', message: err.message });
    } finally {
      setWoBusy(false);
    }
  };

  const decide = async (w: WriteOffRecord, approve: boolean) => {
    try {
      await api.decideWriteOff(w.id, approve);
      showToast({ type: 'success', title: approve ? 'Write-off approved' : 'Write-off rejected', message: `${w.invoice_no}: ৳${w.amount}` });
      load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed', message: err.message });
    }
  };

  const totalOutstanding = dueInvoices.reduce((sum, inv) => sum + inv.due_amount, 0);
  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: 'BILLS', label: 'Bills with due', show: true },
    { id: 'CALLS', label: 'Call list', show: true },
    { id: 'WRITEOFFS', label: 'Write-offs', show: canWriteOff },
    { id: 'DOCTORS', label: 'Doctor balances', show: canSeeDoctors },
  ];

  return (
    <div className="space-y-5" data-testid="dues-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Outstanding Dues & Settlement</h1>
          <p className="text-xs text-[#6D6A60]">Dues are worked out from bills and payments. Collect them here, follow up by phone, or write them off.</p>
        </div>
        {(tab === 'BILLS' || tab === 'CALLS') && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search bill #, patient no., name, phone..."
              aria-label="Search dues"
              className="text-xs bg-transparent border-none outline-none w-56 text-[#1B1B0E]"
            />
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Dues views">
        {tabs.filter((t) => t.show).map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            data-testid={`dues-tab-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852] ${
              tab === t.id ? 'bg-[#525333] text-white shadow-xs' : 'bg-[#F4F3F0] text-[#54524A] hover:bg-[#E8E7E3]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {(tab === 'BILLS' || tab === 'CALLS') && (
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Age buckets">
          <span className="text-[11px] text-[#6D6A60] mr-1">Age of bill:</span>
          {['', ...BUCKETS].map((b) => (
            <button
              key={b || 'all'}
              type="button"
              data-testid={`dues-bucket-${b || 'all'}`}
              onClick={() => setBucket(b)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer ${
                bucket === b ? 'bg-[#CF8852] text-white' : 'bg-white border border-[#CAC7BE] text-[#54524A] hover:bg-[#F4F3F0]'
              }`}
            >
              {b ? bucketLabel(b) : 'All'}
              {calls && b ? ` · ${tk(calls.bucket_totals[b] || 0)}` : ''}
            </button>
          ))}
        </div>
      )}

      {loading && <div className="py-4 text-center text-xs text-[#6D6A60]"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></div>}

      {tab === 'BILLS' && (
        <>
          <div className="bg-[#FEF7EC] border border-[#FBE0B2] rounded-2xl p-4.5 flex items-center justify-between shadow-xs">
            <div className="flex items-center gap-3.5">
              <div className="p-2.5 bg-white border border-[#FBE0B2] text-[#D9820B] rounded-xl shadow-xs">
                <CreditCard className="w-5 h-5" />
              </div>
              <div>
                <span className="text-xs font-semibold text-[#8A5608] block">Total Uncollected Receivables{bucket ? ` (${bucketLabel(bucket)})` : ''}</span>
                <span className="text-2xl font-extrabold text-[#1B1B0E]">{tk(totalOutstanding)}</span>
              </div>
            </div>
            <span className="text-xs font-bold text-[#8A5608] px-2.5 py-1 bg-white border border-[#FBE0B2] rounded-lg">{dueInvoices.length} Invoices with Due</span>
          </div>

          <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                    <th className="pb-3 pl-2">Invoice #</th>
                    <th className="pb-3">Bill Date</th>
                    <th className="pb-3">Age</th>
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
                      <td colSpan={10} className="py-10 text-center text-[#8E8A7E]">
                        <CheckCircle2 className="w-7 h-7 text-[#2D8A39] mx-auto mb-1.5 opacity-80" />
                        No outstanding dues found! All billing accounts are balanced.
                      </td>
                    </tr>
                  )}
                  {dueInvoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-[#F4F3F0] transition-colors" data-testid={`due-row-${inv.id}`}>
                      <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{inv.invoice_number}</td>
                      <td className="py-3 text-[#6D6A60]">{new Date(inv.created_at).toLocaleDateString('en-GB')}</td>
                      <td className="py-3">
                        <Badge variant={bucketVariant(inv.age_bucket)} size="sm">{inv.age_days}d</Badge>
                      </td>
                      <td className="py-3 font-semibold text-[#1B1B0E]">{inv.patient_name}</td>
                      <td className="py-3 text-[#54524A]">{inv.patient_phone}</td>
                      <td className="py-3 text-right font-medium">{tk(inv.net_amount)}</td>
                      <td className="py-3 text-right text-[#1E6327] font-semibold">{tk(inv.paid_amount)}</td>
                      <td className="py-3 text-right font-bold text-[#9C2417]">
                        {tk(inv.due_amount)}
                        {inv.written_off > 0 && <span className="block text-[10px] font-normal text-[#6D6A60]">{tk(inv.written_off)} written off</span>}
                      </td>
                      <td className="py-3 text-center">
                        <Badge variant={getPaymentStatusBadgeVariant(inv.payment_status, inv.paid_amount, inv.due_amount)} size="sm">
                          {formatPaymentStatus(inv.payment_status, inv.paid_amount, inv.due_amount)}
                        </Badge>
                      </td>
                      <td className="py-3 text-right pr-2 whitespace-nowrap">
                        {canWriteOff && (
                          <button
                            type="button"
                            onClick={() => openWriteOff(inv)}
                            data-testid={`writeoff-open-${inv.id}`}
                            className="mr-2 px-2.5 py-1.5 text-[11px] font-semibold bg-white text-[#9C2417] border border-[#F8CBC6] rounded-lg hover:bg-[#FDF2F0] cursor-pointer"
                          >
                            Write off
                          </button>
                        )}
                        <button
                          onClick={() => setSettleId(inv.id)}
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
        </>
      )}

      {tab === 'CALLS' && calls && (
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs" data-testid="dues-call-list">
          <p className="text-[11px] text-[#6D6A60] mb-3">
            Patients with an unpaid balance, oldest bill first. Total {tk(calls.total_due)}. (SMS reminders are not built.)
          </p>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Patient</th>
                <th className="pb-3">Phone</th>
                <th className="pb-3">Bills</th>
                <th className="pb-3">Oldest</th>
                <th className="pb-3 text-right pr-2">Total due</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {calls.patients.length === 0 && !loading && (
                <tr><td colSpan={5} className="py-8 text-center text-[#8E8A7E]">Nobody to call: no outstanding dues.</td></tr>
              )}
              {calls.patients.map((p) => (
                <tr key={p.patient_id} data-testid={`call-row-${p.patient_id}`}>
                  <td className="py-3 pl-2">
                    <span className="font-semibold text-[#1B1B0E]">{p.patient_name}</span>
                    <span className="block font-mono text-[10px] text-[#6D6A60]">{p.patient_code}</span>
                  </td>
                  <td className="py-3 text-[#1B1B0E]"><span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" />{p.patient_phone}</span></td>
                  <td className="py-3 text-[#54524A]">
                    {p.invoices.map((i) => (
                      <span key={i.invoice_id} className="block font-mono text-[11px]">{i.invoice_no} · {tk(i.due)} · {i.age_days}d</span>
                    ))}
                  </td>
                  <td className="py-3"><Badge variant={bucketVariant(p.age_bucket)} size="sm">{p.oldest_age_days} days</Badge></td>
                  <td className="py-3 text-right pr-2 font-bold text-[#9C2417]">{tk(p.total_due)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'WRITEOFFS' && canWriteOff && (
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs" data-testid="writeoff-list">
          <p className="text-[11px] text-[#6D6A60] mb-3">
            A write-off is bad debt, recorded apart from discounts. An Admin can write off up to {adminLimit !== null ? tk(adminLimit) : 'the Admin limit'} per bill; more needs the Owner.
          </p>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Bill</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3 text-right">Amount</th>
                <th className="pb-3">Reason</th>
                <th className="pb-3">Requested by</th>
                <th className="pb-3">Status</th>
                <th className="pb-3 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {writeOffs.length === 0 && !loading && <tr><td colSpan={7} className="py-8 text-center text-[#8E8A7E]">No write-offs yet.</td></tr>}
              {writeOffs.map((w) => (
                <tr key={w.id} data-testid={`writeoff-row-${w.id}`}>
                  <td className="py-3 pl-2 font-mono font-bold">{w.invoice_no}</td>
                  <td className="py-3">{w.patient_name}</td>
                  <td className="py-3 text-right font-bold">{tk(w.amount)}</td>
                  <td className="py-3 text-[#54524A] max-w-xs truncate" title={w.reason}>{w.reason}</td>
                  <td className="py-3 text-[#54524A]">{w.requested_by_name} ({w.requested_by_role})</td>
                  <td className="py-3">
                    <Badge variant={w.status === 'APPLIED' ? 'success' : w.status === 'PENDING_OWNER' ? 'warning' : 'neutral'} size="sm">
                      {w.status === 'PENDING_OWNER' ? 'Waiting for Owner' : w.status === 'APPLIED' ? 'Written off' : 'Rejected'}
                    </Badge>
                  </td>
                  <td className="py-3 text-right pr-2 whitespace-nowrap">
                    {w.status === 'PENDING_OWNER' && role === 'OWNER' && (
                      <>
                        <button type="button" onClick={() => decide(w, false)} className="mr-2 px-2.5 py-1.5 text-[11px] font-semibold bg-white border border-[#CAC7BE] rounded-lg hover:bg-[#F4F3F0] cursor-pointer">Reject</button>
                        <button type="button" onClick={() => decide(w, true)} data-testid={`writeoff-approve-${w.id}`} className="px-2.5 py-1.5 text-[11px] font-semibold bg-[#525333] text-white rounded-lg hover:bg-[#3F4028] cursor-pointer">Approve</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'DOCTORS' && canSeeDoctors && balances && (
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs" data-testid="doctor-balances">
          <p className="text-[11px] text-[#6D6A60] mb-3">{balances.note}</p>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Doctor</th>
                <th className="pb-3 text-right">Wholesale receivable<span className="block normal-case font-normal">the doctor owes the center</span></th>
                <th className="pb-3 text-right pr-2">Professional-fee payable<span className="block normal-case font-normal">the center owes the doctor</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {balances.items.length === 0 && <tr><td colSpan={3} className="py-8 text-center text-[#8E8A7E]">No doctor has a balance yet.</td></tr>}
              {balances.items.map((d) => (
                <tr key={d.referrer_id}>
                  <td className="py-3 pl-2 font-semibold">{d.name}{d.registration_no ? <span className="text-[#6D6A60] font-normal"> · Reg {d.registration_no}</span> : null}</td>
                  <td className="py-3 text-right font-bold text-[#9C2417]">{tk(d.wholesale_receivable)}</td>
                  <td className="py-3 text-right pr-2 font-bold text-[#185B68]">{tk(d.professional_fee_payable)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {settleId !== null && <SettleDueModal key={settleId} invoiceId={settleId} onClose={() => setSettleId(null)} onPaid={load} />}

      <Modal
        isOpen={writeOffFor !== null}
        onClose={() => setWriteOffFor(null)}
        title={writeOffFor ? `Write off due — ${writeOffFor.invoice_number}` : ''}
        subtitle={writeOffFor ? `Patient: ${writeOffFor.patient_name}` : ''}
        maxWidth="md"
      >
        {writeOffFor && (
          <form onSubmit={submitWriteOff} className="space-y-3 text-xs">
            <div className="p-3 rounded-xl border border-[#F8CBC6] bg-[#FDF2F0] text-[#9C2417]">
              Current due {tk(writeOffFor.due_amount)}. This is recorded as <b>bad debt</b>, not as a discount, and cannot be undone here.
              {role !== 'OWNER' && adminLimit !== null && <span className="block mt-1">An Admin can write off up to {tk(adminLimit)} per bill in total; a larger amount is sent to the Owner for approval.</span>}
            </div>
            <div>
              <label className="block font-semibold text-[#54524A] mb-1" htmlFor="wo-amount">Amount to write off (৳) *</label>
              <input id="wo-amount" type="number" min={1} max={writeOffFor.due_amount} required value={woAmount} onChange={(e) => setWoAmount(Number(e.target.value))} className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl text-right font-bold" />
            </div>
            <div>
              <label className="block font-semibold text-[#54524A] mb-1" htmlFor="wo-reason">Reason *</label>
              <textarea id="wo-reason" rows={2} required maxLength={500} value={woReason} onChange={(e) => setWoReason(e.target.value)} className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl" />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-[#E8E7E3]">
              <button type="button" onClick={() => setWriteOffFor(null)} className="px-4 py-2 font-semibold text-[#54524A] hover:bg-[#E8E7E3] rounded-xl">Cancel</button>
              <button type="submit" disabled={woBusy || !woReason.trim() || woAmount <= 0} data-testid="writeoff-confirm" className="px-5 py-2 font-bold bg-[#9C2417] hover:bg-[#7F1D13] text-white rounded-xl disabled:opacity-50">
                {woBusy ? 'Saving...' : 'Write off'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};
