import React, { useEffect, useState } from 'react';
import { Loader2, Settings as SettingsIcon } from 'lucide-react';
import { api } from '../../api/client';
import { CenterSettings } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

/**
 * Center settings (Prompt 17, Owner only). Two values today:
 * - hold a finished report while its bill has a due (Module 17): on by default;
 * - the largest amount an Admin can write off alone per bill (Module 18, D11).
 */
export const SettingsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [settings, setSettings] = useState<CenterSettings | null>(null);
  const [limit, setLimit] = useState('');
  const [tolerance, setTolerance] = useState('');
  const [busy, setBusy] = useState(false);
  const allowed = hasPermission('settings.manage');

  useEffect(() => {
    if (!allowed) return;
    api.getCenterSettings().then((s) => {
      setSettings(s);
      setLimit(String(s.writeoff_admin_limit));
      setTolerance(String(s.cash_variance_tolerance));
    }).catch((err: any) => showToast({ type: 'error', title: 'Failed to load settings', message: err.message }));
  }, [allowed, showToast]);

  if (!allowed) {
    return <div className="bg-white border border-[#DCDAD4] rounded-2xl p-6 text-xs text-[#6D6A60]" data-testid="settings-forbidden">You do not have permission to change the center settings.</div>;
  }
  if (!settings) return <div className="py-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-[#525333]" /></div>;

  const save = async (changes: Partial<CenterSettings>) => {
    setBusy(true);
    try {
      const s = await api.updateCenterSettings(changes);
      setSettings(s);
      setLimit(String(s.writeoff_admin_limit));
      setTolerance(String(s.cash_variance_tolerance));
      showToast({ type: 'success', title: 'Saved', message: 'The setting was updated.' });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Save failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 max-w-2xl" data-testid="settings-page">
      <div>
        <h1 className="text-lg font-bold text-[#1B1B0E] flex items-center gap-2"><SettingsIcon className="w-5 h-5 text-[#525333]" /> Center settings</h1>
        <p className="text-xs text-[#6D6A60] mt-1">Owner only. Every change is recorded in the audit log.</p>
      </div>

      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 space-y-2">
        <label className="flex items-start gap-3 text-xs text-[#1B1B0E]">
          <input
            type="checkbox"
            className="mt-0.5 accent-[#525333]"
            checked={settings.report_hold_when_due}
            disabled={busy}
            onChange={(e) => save({ report_hold_when_due: e.target.checked })}
            data-testid="setting-hold"
          />
          <span>
            <b>Hold a report while the bill has a due.</b>
            <span className="block text-[#6D6A60]">On: the front desk cannot hand a report over until the due is paid; an Admin or the Owner can release it with a reason. Off: reports are never held.</span>
          </span>
        </label>
      </div>

      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 space-y-2">
        <label className="block text-xs font-semibold text-[#1B1B0E]" htmlFor="setting-limit">Admin write-off limit (৳ per bill, in total)</label>
        <div className="flex items-center gap-2">
          <input id="setting-limit" data-testid="setting-limit" type="number" min={0} value={limit} onChange={(e) => setLimit(e.target.value)} className="w-40 p-2.5 bg-white border border-[#CAC7BE] rounded-xl text-right font-bold text-xs" />
          <button
            type="button"
            disabled={busy || limit === '' || Number(limit) < 0 || Number(limit) === settings.writeoff_admin_limit}
            onClick={() => save({ writeoff_admin_limit: Number(limit) })}
            data-testid="setting-limit-save"
            className="px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3F4028] disabled:opacity-50 cursor-pointer"
          >
            Save
          </button>
        </div>
        <p className="text-[11px] text-[#6D6A60]">An Admin can write off up to this amount on a bill without approval; anything above it waits for the Owner. The Owner has no limit.</p>
      </div>

      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 space-y-2">
        <label className="block text-xs font-semibold text-[#1B1B0E]" htmlFor="setting-tolerance">Day-close variance tolerance (৳)</label>
        <div className="flex items-center gap-2">
          <input id="setting-tolerance" data-testid="setting-tolerance" type="number" min={0} value={tolerance} onChange={(e) => setTolerance(e.target.value)} className="w-40 p-2.5 bg-white border border-[#CAC7BE] rounded-xl text-right font-bold text-xs" />
          <button
            type="button"
            disabled={busy || tolerance === '' || Number(tolerance) < 0 || Number(tolerance) === settings.cash_variance_tolerance}
            onClick={() => save({ cash_variance_tolerance: Number(tolerance) })}
            data-testid="setting-tolerance-save"
            className="px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3F4028] disabled:opacity-50 cursor-pointer"
          >
            Save
          </button>
        </div>
        <p className="text-[11px] text-[#6D6A60]">A counted-cash difference up to this amount (either way) needs no reason when the day is closed. 0 means every difference needs a reason.</p>
      </div>
    </div>
  );
};
