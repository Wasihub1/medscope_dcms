import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useToast } from '../../context/ToastContext';
import { Modal } from '../../components/common/Modal';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { RangeVersion, TestItem, TestRanges, RangeBandInput } from '../../types';

/**
 * Prompt 14 (D24): reference ranges versioned by sex and age band in days, inside the Catalog area.
 * Admin/Owner add a band, make a NEW VERSION of a band, or retire a band. Rows are never edited or deleted:
 * a new version supersedes the old one for future results only; saved results keep their own snapshot.
 */
type Form =
  | { mode: 'band'; componentId: number; componentName: string }
  | { mode: 'version'; version: RangeVersion; componentName: string }
  | null;

const num = (v: string): number | null => (v.trim() === '' ? null : Number(v));
const txt = (n?: number | null) => (n === null || n === undefined ? '' : String(n));
const span = (v: RangeVersion) => `${v.age_days_min} - ${v.age_days_max ?? 'no limit'}`;
const btn =
  'px-2.5 py-1 text-[11px] font-semibold text-[#525333] bg-white border border-[#CAC7BE] hover:bg-[#F4F3F0] rounded-lg cursor-pointer';
const input = 'w-full px-2.5 py-2 border border-[#CAC7BE] rounded-lg bg-white text-xs';

export const ReferenceRangesPanel: React.FC = () => {
  const { showToast } = useToast();
  const [search, setSearch] = useState('');
  const [tests, setTests] = useState<TestItem[]>([]);
  const [data, setData] = useState<TestRanges | null>(null);
  const [form, setForm] = useState<Form>(null);
  const [retire, setRetire] = useState<{ version: RangeVersion; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRetired, setShowRetired] = useState(false);
  const [f, setF] = useState({ sex: 'ANY', amin: '0', amax: '', rmin: '', rmax: '', cmin: '', cmax: '', text: '', note: '' });

  useEffect(() => {
    let alive = true;
    api.getTests(search || undefined, undefined, 50)
      .then((r) => { if (alive) setTests(r); })
      .catch((err: any) => { if (alive) showToast({ type: 'error', title: 'Could not load tests', message: err.message }); });
    return () => { alive = false; };
  }, [search, showToast]);

  const openTest = async (id: number | string) => {
    try {
      setData(await api.getReferenceRanges(id));
    } catch (err: any) {
      showToast({ type: 'error', title: 'Could not load ranges', message: err.message });
    }
  };

  const startBand = (componentId: number, componentName: string) => {
    setF({ sex: 'ANY', amin: '0', amax: '', rmin: '', rmax: '', cmin: '', cmax: '', text: '', note: '' });
    setForm({ mode: 'band', componentId, componentName });
  };
  const startVersion = (version: RangeVersion, componentName: string) => {
    setF({
      sex: version.sex, amin: String(version.age_days_min), amax: txt(version.age_days_max),
      rmin: txt(version.ref_min), rmax: txt(version.ref_max), cmin: txt(version.critical_min), cmax: txt(version.critical_max),
      text: version.reference_range_text || '', note: '',
    });
    setForm({ mode: 'version', version, componentName });
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form || !data) return;
    const values: RangeBandInput = {
      ref_min: num(f.rmin), ref_max: num(f.rmax), critical_min: num(f.cmin), critical_max: num(f.cmax),
      reference_range_text: f.text.trim() || null, note: f.note.trim() || null,
    };
    setBusy(true);
    try {
      if (form.mode === 'band') {
        await api.addRangeBand(form.componentId, { ...values, sex: f.sex, age_days_min: Number(f.amin || 0), age_days_max: num(f.amax) });
        showToast({ type: 'success', title: 'Band added', message: form.componentName });
      } else {
        await api.newRangeVersion(form.version.id, values);
        showToast({ type: 'success', title: 'New version saved', message: 'It applies to future results only. Saved results keep their own range.' });
      }
      setForm(null);
      await openTest(data.test_id);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Not saved', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const doRetire = async (reason: string) => {
    if (!retire || !data) return;
    setBusy(true);
    try {
      await api.retireRangeBand(retire.version.id, reason);
      showToast({ type: 'success', title: 'Band retired', message: 'Saved results keep their own range.' });
      setRetire(null);
      await openTest(data.test_id);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Not retired', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const isNew = form?.mode === 'band';

  return (
    <div className="space-y-4" data-testid="reference-ranges-panel">
      <p className="text-xs text-[#6D6A60]">
        Ranges are set per test component by sex and age band in days. A change is saved as a new version; it applies to future
        results only and never alters a result that was already saved.
      </p>
      <div className="flex gap-4 flex-wrap items-start">
        <div className="w-64 space-y-2">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tests..." className={input} data-testid="ranges-test-search" />
          <div className="max-h-96 overflow-auto border border-[#E8E7E3] rounded-lg bg-white">
            {tests.map((t) => (
              <button
                key={t.id}
                onClick={() => openTest(t.id)}
                data-testid={`ranges-test-${t.id}`}
                className={`block w-full text-left px-3 py-2 text-xs border-b border-[#F0EFEB] hover:bg-[#F4F3F0] cursor-pointer ${data?.test_id === Number(t.id) ? 'bg-[#EEF0DD] font-semibold' : ''}`}
              >
                [{t.code}] {t.name}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 min-w-[320px] space-y-4">
          {!data && <p className="text-xs text-[#6D6A60]">Choose a test to see its components and bands.</p>}
          {data && (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-[#1B1B0E]">{data.test_name}</h2>
                <label className="text-[11px] text-[#54524A] flex items-center gap-1">
                  <input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} /> Show old versions
                </label>
              </div>
              {data.components.length === 0 && <p className="text-xs text-[#6D6A60]">This test has no result components.</p>}
              {data.components.map((c) => (
                <div key={c.component_id} className="bg-white border border-[#E8E7E3] rounded-xl overflow-hidden" data-testid={`range-component-${c.component_id}`}>
                  <div className="flex items-center justify-between px-3 py-2 bg-[#F4F3F0]">
                    <span className="text-xs font-semibold">{c.name} <span className="text-[#6D6A60] font-normal">({c.code}{c.unit ? `, ${c.unit}` : ''})</span></span>
                    <button className={btn} data-testid={`add-band-${c.component_id}`} onClick={() => startBand(c.component_id, c.name)}>Add band</button>
                  </div>
                  <table className="w-full text-[11px]">
                    <thead className="text-left text-[#6D6A60]">
                      <tr><th className="p-2">Sex</th><th className="p-2">Age (days)</th><th className="p-2">Reference</th><th className="p-2">Critical</th><th className="p-2">Version</th><th className="p-2 text-right">Action</th></tr>
                    </thead>
                    <tbody>
                      {c.versions.filter((v) => v.is_current || showRetired).map((v) => (
                        <tr key={v.id} className={`border-t border-[#F0EFEB] ${v.is_current ? '' : 'text-[#8E8A7E]'}`}>
                          <td className="p-2">{v.sex === 'ANY' ? 'Any' : v.sex === 'MALE' ? 'Male' : 'Female'}</td>
                          <td className="p-2">{span(v)}</td>
                          <td className="p-2">{txt(v.ref_min) || '-'} to {txt(v.ref_max) || '-'}</td>
                          <td className="p-2">{txt(v.critical_min) || '-'} / {txt(v.critical_max) || '-'}</td>
                          <td className="p-2">v{v.version_no}{v.is_current ? '' : ' (old)'}</td>
                          <td className="p-2 text-right space-x-1">
                            {v.is_current && (
                              <>
                                <button className={btn} data-testid={`new-version-${v.id}`} onClick={() => startVersion(v, c.name)}>New version</button>
                                <button className={btn} data-testid={`retire-band-${v.id}`} onClick={() => setRetire({ version: v, name: `${c.name}: ${v.sex}, ${span(v)} days` })}>Retire</button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                      {c.versions.filter((v) => v.is_current).length === 0 && (
                        <tr><td colSpan={6} className="p-3 text-center text-amber-700">No current band. Results for this component will be marked "no range" until one is added.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      <Modal isOpen={form !== null} onClose={() => setForm(null)} title={isNew ? 'Add band' : 'New version of band'} subtitle={form?.componentName} maxWidth="md">
        <form onSubmit={save} className="space-y-3 text-xs" data-testid="range-form">
          {!isNew && (
            <p className="p-2 bg-[#FEF7EC] border border-[#FBE0B2] text-[#8A5608] rounded-lg">
              Sex and age span stay the same. This version applies to future results only; the current one is kept as history.
            </p>
          )}
          <div className="grid grid-cols-3 gap-2">
            <label>Sex
              <select className={input} value={f.sex} disabled={!isNew} onChange={(e) => setF({ ...f, sex: e.target.value })} data-testid="range-sex">
                <option value="ANY">Any</option><option value="MALE">Male</option><option value="FEMALE">Female</option>
              </select>
            </label>
            <label>Age from (days)
              <input className={input} type="number" min={0} value={f.amin} disabled={!isNew} onChange={(e) => setF({ ...f, amin: e.target.value })} data-testid="range-age-min" />
            </label>
            <label>Age to (days)
              <input className={input} type="number" min={0} value={f.amax} disabled={!isNew} placeholder="no limit" onChange={(e) => setF({ ...f, amax: e.target.value })} data-testid="range-age-max" />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label>Reference min<input className={input} type="number" step="any" value={f.rmin} onChange={(e) => setF({ ...f, rmin: e.target.value })} data-testid="range-ref-min" /></label>
            <label>Reference max<input className={input} type="number" step="any" value={f.rmax} onChange={(e) => setF({ ...f, rmax: e.target.value })} data-testid="range-ref-max" /></label>
            <label>Critical low<input className={input} type="number" step="any" value={f.cmin} onChange={(e) => setF({ ...f, cmin: e.target.value })} data-testid="range-crit-min" /></label>
            <label>Critical high<input className={input} type="number" step="any" value={f.cmax} onChange={(e) => setF({ ...f, cmax: e.target.value })} data-testid="range-crit-max" /></label>
          </div>
          <label className="block">Range text shown on the report (optional)
            <input className={input} value={f.text} maxLength={200} onChange={(e) => setF({ ...f, text: e.target.value })} placeholder="e.g. 12.0 - 16.0 g/dL" />
          </label>
          <label className="block">Note (optional)
            <input className={input} value={f.note} maxLength={300} onChange={(e) => setF({ ...f, note: e.target.value })} />
          </label>
          <div className="flex justify-end gap-2 pt-2 border-t border-[#E8E7E3]">
            <button type="button" className={btn} onClick={() => setForm(null)}>Close</button>
            <button type="submit" disabled={busy} className="px-4 py-1.5 text-xs font-bold bg-[#525333] text-white rounded-lg" data-testid="range-save">
              {busy ? 'Saving...' : isNew ? 'Add band' : 'Save new version'}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        isOpen={retire !== null}
        title="Retire band?"
        itemName={retire?.name || ''}
        effect="Future results will no longer use this band. Results already saved keep the range they were entered with."
        confirmLabel="Retire"
        requireReason
        danger
        busy={busy}
        testId="range-retire-confirm"
        onCancel={() => setRetire(null)}
        onConfirm={doRetire}
      />
    </div>
  );
};
