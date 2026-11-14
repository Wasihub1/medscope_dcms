import React, { useCallback, useEffect, useState } from 'react';
import { Download, Loader2, Scale } from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

type ReportKey = 'cash-book' | 'income-expense' | 'dues' | 'cost-by-referrer';
const TABS: { key: ReportKey; label: string }[] = [
  { key: 'cash-book', label: 'Cash book' },
  { key: 'income-expense', label: 'Daily income & expense' },
  { key: 'dues', label: 'Dues' },
  { key: 'cost-by-referrer', label: 'Cost by referrer' },
];
const CHANNELS = ['CASH', 'BKASH', 'NAGAD', 'ROCKET', 'POS_CARD', 'BANK_TRANSFER', 'OTHER'];
const COLUMNS: Record<ReportKey, { key: string; label: string; money?: boolean }[]> = {
  'cash-book': [
    { key: 'date', label: 'Date' }, { key: 'event', label: 'Event' }, { key: 'memo', label: 'Memo' },
    { key: 'money_in', label: 'In', money: true }, { key: 'money_out', label: 'Out', money: true }, { key: 'balance', label: 'Balance', money: true },
  ],
  'income-expense': [
    { key: 'date', label: 'Date' }, { key: 'test_revenue', label: 'Test revenue', money: true }, { key: 'urgent_fee_revenue', label: 'Urgent fee', money: true },
    { key: 'discount_given', label: 'Discount given', money: true }, { key: 'income', label: 'Income', money: true },
    { key: 'operating_expense', label: 'Expenses', money: true }, { key: 'bad_debt', label: 'Bad debt', money: true },
    { key: 'cash_variance', label: 'Cash variance', money: true }, { key: 'net', label: 'Net', money: true },
  ],
  dues: [
    { key: 'bill_no', label: 'Bill' }, { key: 'bill_date', label: 'Bill date' }, { key: 'patient', label: 'Patient' }, { key: 'phone', label: 'Phone' },
    { key: 'net', label: 'Net', money: true }, { key: 'paid', label: 'Paid', money: true }, { key: 'written_off', label: 'Written off', money: true },
    { key: 'due', label: 'Due', money: true }, { key: 'age_bucket', label: 'Age (days)' },
  ],
  'cost-by-referrer': [
    { key: 'referrer', label: 'Referrer' }, { key: 'bills', label: 'Bills' }, { key: 'net_billed', label: 'Net billed', money: true }, { key: 'cost', label: 'Cost', money: true },
  ],
};

/** Accounting reports (Prompt 18, Module 21): four V1 reports from the journal, flexible date range, CSV export for Excel. */
export const AccountingPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [tab, setTab] = useState<ReportKey>('cash-book');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [channel, setChannel] = useState('CASH');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const allowed = hasPermission('accounting.view');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.getAccountingReport(tab, { from: from || undefined, to: to || undefined, channel: tab === 'cash-book' ? channel : undefined }));
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load the report', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [tab, from, to, channel, showToast]);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) {
    return <div className="bg-white border border-[#DCDAD4] rounded-2xl p-6 text-xs text-[#6D6A60]" data-testid="accounting-forbidden">You do not have permission to view the accounting reports.</div>;
  }

  const summary = (() => {
    if (!data) return null;
    if (tab === 'cash-book') return `Opening ৳${data.opening_balance.toLocaleString()} · in ৳${data.total_in.toLocaleString()} · out ৳${data.total_out.toLocaleString()} · closing ৳${data.closing_balance.toLocaleString()}`;
    if (tab === 'income-expense') return `Income ৳${data.totals.income.toLocaleString()} · expense ৳${data.totals.expense.toLocaleString()} · net ৳${data.totals.net.toLocaleString()} (billing basis: the day a bill is confirmed)`;
    if (tab === 'dues') return `Total due ৳${data.total_due.toLocaleString()}`;
    return data.note;
  })();

  return (
    <div className="space-y-4" data-testid="accounting-page">
      <div>
        <h1 className="text-lg font-bold text-[#1B1B0E] flex items-center gap-2"><Scale className="w-5 h-5 text-[#525333]" /> Accounting</h1>
        <p className="text-xs text-[#6D6A60] mt-1">Figures come from the journal, which starts when Module 21 went live; earlier activity is not backfilled.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button key={t.key} type="button" onClick={() => setTab(t.key)} data-testid={`acc-tab-${t.key}`}
            className={`px-3.5 py-2 text-xs font-semibold rounded-xl cursor-pointer ${tab === t.key ? 'bg-[#525333] text-white' : 'bg-white border border-[#CAC7BE] text-[#54524A]'}`}>{t.label}</button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3 text-xs">
        <label className="block">From<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="block mt-1 p-2 bg-white border border-[#CAC7BE] rounded-xl" data-testid="acc-from" /></label>
        <label className="block">To<input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="block mt-1 p-2 bg-white border border-[#CAC7BE] rounded-xl" data-testid="acc-to" /></label>
        {tab === 'cash-book' && (
          <label className="block">Account
            <select value={channel} onChange={(e) => setChannel(e.target.value)} className="block mt-1 p-2 bg-white border border-[#CAC7BE] rounded-xl">
              {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        )}
        <button type="button" data-testid="acc-export"
          onClick={() => api.downloadAccountingCsv(tab, { from: from || undefined, to: to || undefined, channel: tab === 'cash-book' ? channel : undefined }).catch((err: any) => showToast({ type: 'error', title: 'Export failed', message: err.message }))}
          className="px-4 py-2 bg-[#CF8852] hover:bg-[#B7703B] text-white font-bold rounded-xl inline-flex items-center gap-1.5 cursor-pointer"><Download className="w-4 h-4" /> Export CSV (Excel)</button>
      </div>

      {loading || !data ? (
        <div className="py-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#525333]" /></div>
      ) : (
        <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-4 overflow-x-auto">
          <p className="text-xs font-semibold text-[#1B1B0E] mb-3" data-testid="acc-summary">{summary}</p>
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[#6D6A60]">{COLUMNS[tab].map((c) => <th key={c.key} className={`py-1.5 pr-3 ${c.money ? 'text-right' : ''}`}>{c.label}</th>)}</tr></thead>
            <tbody>
              {data.rows.length === 0 && <tr><td colSpan={COLUMNS[tab].length} className="py-6 text-center text-[#8E8A7E]">No entries in this range.</td></tr>}
              {data.rows.map((r: any, i: number) => (
                <tr key={i} className="border-t border-[#EEEDE8]">
                  {COLUMNS[tab].map((c) => <td key={c.key} className={`py-1.5 pr-3 ${c.money ? 'text-right font-semibold' : ''}`}>{c.money ? `৳${Number(r[c.key] ?? 0).toLocaleString()}` : String(r[c.key] ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
