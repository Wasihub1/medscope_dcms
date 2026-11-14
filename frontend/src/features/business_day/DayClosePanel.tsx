import React, { useCallback, useEffect, useState } from 'react';
import { Lock, Loader2, Unlock } from 'lucide-react';
import { api } from '../../api/client';
import { DayScreen, JournalEntryRow } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

const tk = (n: number) => `৳${n.toLocaleString()}`;
const KIND_LABEL: Record<string, string> = { BANK_DEPOSIT: 'Bank deposit', OWNER_WITHDRAWAL: 'Owner withdrawal', EXPENSE: 'Expense' };

/**
 * Day close (Prompt 18, Module 22). Admin/Owner only (business_day.close). Shows the expected cash by the D45 formula
 * with every term visible, takes counted cash, shows the variance and asks for a reason above the tolerance.
 * Wallet / bank channels are checked on their own lines. Owner can reopen a closed day (reason) and then post
 * adjusting entries only. The payout kinds whose modules are not built yet are shown as 0, labelled.
 */
export const DayClosePanel: React.FC<{ onChanged: () => void }> = ({ onChanged }) => {
  const { hasPermission, role } = useAuth();
  const { showToast } = useToast();
  const [screen, setScreen] = useState<DayScreen | null>(null);
  const [counted, setCounted] = useState('');
  const [channelCounts, setChannelCounts] = useState<Record<string, string>>({});
  const [reason, setReason] = useState('');
  const [mvKind, setMvKind] = useState('EXPENSE');
  const [mvAmount, setMvAmount] = useState('');
  const [mvNote, setMvNote] = useState('');
  const [reopenReason, setReopenReason] = useState('');
  const [entries, setEntries] = useState<JournalEntryRow[]>([]);
  const [adjReason, setAdjReason] = useState('');
  const [busy, setBusy] = useState(false);
  const allowed = hasPermission('business_day.close');
  const isOwner = role === 'OWNER';

  const load = useCallback(async () => {
    try {
      const s = await api.getDayScreen();
      setScreen(s);
      if (s.day?.status === 'REOPENED') {
        setEntries((await api.getJournal({ business_day_id: s.day.id })).entries);
      }
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load the day screen', message: err.message });
    }
  }, [showToast]);

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) return null;
  if (!screen) return <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-[#525333]" /></div>;
  if (!screen.day || !screen.cash || !screen.channels) return null;

  const day = screen.day;
  const cash = screen.cash;
  const editable = day.status === 'OPEN' || day.status === 'REOPENED';
  const countedNum = counted === '' ? null : Number(counted);
  const variance = countedNum === null ? null : countedNum - cash.expected_cash;
  const needsReason = variance !== null && Math.abs(variance) > screen.tolerance;
  const otherChannels = screen.channels.filter((c) => c.channel !== 'CASH' && (c.opening || c.collections || c.refunds));

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try {
      await fn();
      showToast({ type: 'success', title: ok, message: '' });
      await load();
      onChanged();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Not saved', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    const channels: Record<string, number> = {};
    Object.entries(channelCounts).forEach(([ch, v]) => { if (v !== '') channels[ch] = Number(v); });
    return run(() => api.closeBusinessDay({
      counted_cash: Number(counted), counted_channels: channels, variance_reason: reason || undefined,
      day_id: day.status === 'REOPENED' ? day.id : undefined,
    }), 'Day closed');
  };

  const row = (label: string, value: number, sign: '+' | '−' | '', note?: string) => (
    <div className="flex justify-between py-1 border-b border-[#EEEDE8]" key={label}>
      <span className="text-[#54524A]">{sign && <span className="inline-block w-4 font-bold">{sign}</span>}{label}{note && <span className="text-[#8E8A7E]"> {note}</span>}</span>
      <span className="font-semibold text-[#1B1B0E]">{tk(value)}</span>
    </div>
  );

  return (
    <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs space-y-5 text-xs" data-testid="day-close-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-[#1B1B0E] uppercase tracking-wider">Day close — Business Day #{day.day_number} ({day.status})</h2>
        {day.status === 'CLOSED' && <Lock className="w-4 h-4 text-[#9C2417]" />}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div>
          <h3 className="font-bold text-[#525333] mb-1">Expected cash</h3>
          {row('Opening cash', cash.opening_cash, '')}
          {row('Cash collections', cash.cash_collections, '+')}
          {row('Cash refunds paid', cash.cash_refunds, '−')}
          {row('Bank deposits', cash.bank_deposits, '−')}
          {row('Owner withdrawals', cash.owner_withdrawals, '−')}
          {row('Small expenses', cash.expenses, '−')}
          {cash.adjusting_entries !== 0 && row('Adjusting entries on Cash (reopened day)', cash.adjusting_entries, '+')}
          {Object.entries(cash.deferred_payouts).map(([name, v]) => row(name, v, '−', '(not built yet, always 0)'))}
          <div className="flex justify-between pt-2 text-sm font-extrabold text-[#525333]" data-testid="expected-cash">
            <span>Expected cash</span><span>{tk(cash.expected_cash)}</span>
          </div>
          <p className="text-[11px] text-[#8E8A7E] mt-1">Write-offs are not cash and are not part of this figure. Unsynced items: {screen.unsynced_items} (offline sync is not built).</p>
        </div>

        <div className="space-y-2">
          <h3 className="font-bold text-[#525333]">Count</h3>
          {editable ? (
            <>
              <label className="block font-semibold text-[#54524A]" htmlFor="counted-cash">Counted cash (৳)</label>
              <input id="counted-cash" data-testid="counted-cash" type="number" min={0} value={counted} onChange={(e) => setCounted(e.target.value)} className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl text-right font-bold text-sm" />
              {variance !== null && (
                <div className={`font-bold ${variance === 0 ? 'text-[#1E6327]' : 'text-[#9C2417]'}`} data-testid="variance">Variance: {variance > 0 ? '+' : ''}{tk(variance)} {variance < 0 ? '(short)' : variance > 0 ? '(over)' : ''}</div>
              )}
              {otherChannels.length > 0 && (
                <div className="pt-2 space-y-1">
                  <span className="font-semibold text-[#54524A]">Wallet / bank channels (checked on their own lines)</span>
                  {otherChannels.map((c) => (
                    <div key={c.channel} className="flex items-center gap-2">
                      <span className="w-28">{c.channel}</span>
                      <span className="text-[#6D6A60] w-28">expected {tk(c.expected)}</span>
                      <input type="number" min={0} placeholder="counted" value={channelCounts[c.channel] ?? ''} onChange={(e) => setChannelCounts({ ...channelCounts, [c.channel]: e.target.value })} className="w-28 p-1.5 bg-white border border-[#CAC7BE] rounded-lg text-right" />
                    </div>
                  ))}
                </div>
              )}
              <label className="block font-semibold text-[#54524A] pt-1" htmlFor="variance-reason">Reason for the difference {needsReason ? '*' : `(needed above Tk ${screen.tolerance})`}</label>
              <input id="variance-reason" data-testid="variance-reason" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl" />
              <button
                type="button"
                data-testid="close-day-confirm"
                disabled={busy || countedNum === null || countedNum < 0 || (needsReason && !reason.trim())}
                onClick={close}
                className="px-4 py-2 bg-[#9C2417] hover:bg-[#7E1D12] disabled:opacity-50 text-white font-bold rounded-xl inline-flex items-center gap-1.5 cursor-pointer"
              >
                <Lock className="w-4 h-4" /> {day.status === 'REOPENED' ? 'Close the day again' : 'Close business day'}
              </button>
            </>
          ) : (
            <div className="space-y-1">
              <div>Counted cash: <b>{day.counted_cash === null ? '-' : tk(day.counted_cash)}</b></div>
              <div>Variance: <b>{day.variance === null ? '-' : `${day.variance > 0 ? '+' : ''}${tk(day.variance)}`}</b></div>
              {day.variance_reason && <div>Reason: {day.variance_reason}</div>}
              <p className="text-[#8E8A7E]">A closed day cannot be edited. Only the Owner can reopen it, with a reason, to post adjusting entries.</p>
              {isOwner && (
                <div className="pt-2 space-y-2">
                  <input data-testid="reopen-reason" placeholder="Reason to reopen" value={reopenReason} maxLength={300} onChange={(e) => setReopenReason(e.target.value)} className="w-full p-2.5 bg-white border border-[#CAC7BE] rounded-xl" />
                  <button type="button" data-testid="reopen-day" disabled={busy || reopenReason.trim().length < 3} onClick={() => run(() => api.reopenBusinessDay(day.id, reopenReason), 'Day reopened')}
                    className="px-4 py-2 bg-[#525333] hover:bg-[#3F4028] disabled:opacity-50 text-white font-bold rounded-xl inline-flex items-center gap-1.5 cursor-pointer">
                    <Unlock className="w-4 h-4" /> Reopen for adjustments
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {day.status === 'OPEN' && (
        <div className="border-t border-[#E8E7E3] pt-4 space-y-2" data-testid="movement-form">
          <h3 className="font-bold text-[#525333]">Bank deposit, owner withdrawal, small expense (from the drawer cash)</h3>
          <div className="flex flex-wrap gap-2 items-center">
            <select value={mvKind} onChange={(e) => setMvKind(e.target.value)} className="p-2 bg-white border border-[#CAC7BE] rounded-xl" data-testid="movement-kind">
              <option value="EXPENSE">Expense</option>
              <option value="BANK_DEPOSIT">Bank deposit</option>
              {isOwner && <option value="OWNER_WITHDRAWAL">Owner withdrawal</option>}
            </select>
            <input type="number" min={1} placeholder="Amount" value={mvAmount} onChange={(e) => setMvAmount(e.target.value)} className="w-28 p-2 bg-white border border-[#CAC7BE] rounded-xl text-right" data-testid="movement-amount" />
            <input placeholder={mvKind === 'EXPENSE' ? 'What for (required)' : 'Note (optional)'} value={mvNote} maxLength={300} onChange={(e) => setMvNote(e.target.value)} className="flex-1 min-w-48 p-2 bg-white border border-[#CAC7BE] rounded-xl" data-testid="movement-note" />
            <button type="button" data-testid="movement-add" disabled={busy || !Number(mvAmount) || (mvKind === 'EXPENSE' && !mvNote.trim())}
              onClick={() => run(async () => { await api.addDayMovement({ kind: mvKind, amount: Number(mvAmount), note: mvNote || undefined }); setMvAmount(''); setMvNote(''); }, 'Recorded')}
              className="px-4 py-2 bg-[#CF8852] hover:bg-[#B7703B] disabled:opacity-50 text-white font-bold rounded-xl cursor-pointer">Record</button>
          </div>
        </div>
      )}

      {screen.movements && screen.movements.length > 0 && (
        <div className="border-t border-[#E8E7E3] pt-3">
          <h3 className="font-bold text-[#525333] mb-1">Entered today</h3>
          {screen.movements.map((m) => (
            <div key={m.id} className="flex justify-between py-0.5"><span>{KIND_LABEL[m.kind] ?? m.kind}{m.note ? ` — ${m.note}` : ''}</span><span className="font-semibold">{tk(m.amount)}</span></div>
          ))}
        </div>
      )}

      {day.status === 'REOPENED' && isOwner && (
        <div className="border-t border-[#E8E7E3] pt-4 space-y-2" data-testid="adjustments">
          <h3 className="font-bold text-[#525333]">Adjusting entries (reopened: {day.reopen_reason})</h3>
          <p className="text-[#8E8A7E]">Nothing already posted is edited. Reverse an entry below; the reversal is a new entry that points at the original.</p>
          <input placeholder="Reason for the adjustment" value={adjReason} maxLength={300} onChange={(e) => setAdjReason(e.target.value)} className="w-full p-2 bg-white border border-[#CAC7BE] rounded-xl" data-testid="adjust-reason" />
          {entries.filter((e) => !e.reverses_entry_id && !entries.some((x) => x.reverses_entry_id === e.id)).map((e) => (
            <div key={e.id} className="flex items-center justify-between gap-2 py-1 border-b border-[#EEEDE8]">
              <span>#{e.id} {e.event} — {e.lines.map((l) => `${l.account} ${l.debit ? 'Dr ' + l.debit : 'Cr ' + l.credit}`).join(', ')}</span>
              <button type="button" disabled={busy || adjReason.trim().length < 3} onClick={() => run(() => api.postDayAdjustment(day.id, { reason: adjReason, reverse_entry_id: e.id }), 'Reversal posted')}
                className="px-3 py-1 bg-[#525333] disabled:opacity-50 text-white font-semibold rounded-lg cursor-pointer">Reverse</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
