import React, { useEffect, useState } from 'react';
import { AlertTriangle, FileText, Loader2, ShieldCheck } from 'lucide-react';
import { Modal } from './Modal';
import { api } from '../../api/client';
import { ResultPreview } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

/**
 * Report preview of a saved result (Prompt 10E Part 9, reworked in Prompt 10F F2).
 * - Read-only: built from the stored result snapshots (component name, unit, reference range,
 *   critical limits as saved), never from the current catalog.
 * - Works for DRAFT and ENTERED results; a DRAFT is clearly marked "not a final report".
 * - Money-free. Preview only: no print, no finalize, no signature, no QR, no SMS (Module 14).
 * source 'lab' = My Work (room access); 'reports' = sidebar Ready Reports (front desk).
 */
interface Props {
  isOpen: boolean;
  onClose: () => void;
  testOrderId: number | null;
  source?: 'lab' | 'reports';
  /** Called after a successful Finalize so the parent list can refresh. */
  onFinalized?: () => void;
}

const flagClass = (flag?: string | null) =>
  flag === 'CRITICAL'
    ? 'text-rose-700 font-bold'
    : flag === 'HIGH' || flag === 'LOW'
    ? 'text-amber-700 font-semibold'
    : 'text-[#1B1B0E]';

const criticalText = (min?: number | null, max?: number | null) => {
  const lo = min !== null && min !== undefined ? `< ${min}` : '';
  const hi = max !== null && max !== undefined ? `> ${max}` : '';
  return [lo, hi].filter(Boolean).join(' or ');
};

const STRUCTURED_LABELS: Record<string, string> = {
  liver: 'Liver',
  gallbladder: 'Gallbladder',
  spleen: 'Spleen',
  pancreas: 'Pancreas',
  kidneys: 'Kidneys',
  bladder: 'Urinary bladder',
  pelvis: 'Pelvic organs',
};

/**
 * The read-only result body (draft banner, patient block, parameter table, narrative, footer).
 * Exported so the doctor sign-off screen (Prompt 15) shows exactly the same saved result without a copy.
 * `onClose` adds the footer Close button; omit it where the parent has its own buttons.
 */
export const ResultPreviewBody: React.FC<{ data: ResultPreview; onClose?: () => void; hideReadyNote?: boolean }> = ({ data, onClose, hideReadyNote }) => {
  const structured = data.structured_data ? Object.entries(data.structured_data).filter(([, v]) => v) : [];
  return (
  <div className="space-y-4 text-xs" data-testid="result-report-preview">
    {data.is_draft ? (
      <div
        role="status"
        data-testid="preview-draft-banner"
        className="flex items-start gap-2 p-3 rounded-xl border-2 border-dashed border-amber-400 bg-amber-50 text-amber-900"
      >
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-amber-700" />
        <div>
          <span className="font-bold block">DRAFT, not a final report</span>
          <span>These values are saved as a draft and may still change. Submit the result to make it Ready.</span>
        </div>
      </div>
    ) : data.report_status === 'FINAL' ? (
      <div className="p-2.5 rounded-xl border border-emerald-200 bg-emerald-50 text-emerald-900 space-y-0.5" data-testid="preview-final-note">
        <span className="flex items-center gap-2 font-bold">
          <ShieldCheck className="w-4 h-4 shrink-0" />
          Final report {data.report_no}. Stored content, it cannot be changed.
        </span>
        {data.signatures?.technician?.name && (
          <span className="block pl-6">
            Technician: {data.signatures.technician.name}
            {data.signatures.technician.signed_at ? ` · ${new Date(data.signatures.technician.signed_at).toLocaleString('en-GB')}` : ''}
          </span>
        )}
        {data.signatures?.doctor?.name && (
          <span className="block pl-6">
            Doctor: {data.signatures.doctor.name} · Reg {data.signatures.doctor.registration_no}
            {data.signatures.doctor.is_attestation ? ' (recorded on the doctor’s behalf)' : ' (approved personally)'}
          </span>
        )}
      </div>
    ) : hideReadyNote ? null : (
      <div className="flex items-center gap-2 p-2.5 rounded-xl border border-[#B9C9DA] bg-[#EEF3F8] text-[#2B547E]" data-testid="preview-entered-note">
        <FileText className="w-4 h-4 shrink-0" />
        <span>
          Result submitted{data.is_ready ? ' and Ready' : ''}. It becomes a Final report when it is finalized (no printing here yet).
        </span>
      </div>
    )}

    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-3 bg-[#F4F3F0] border border-[#DCDAD4] rounded-xl">
      <div>
        <span className="text-[#6D6A60] block">Patient</span>
        <span className="font-semibold text-[#1B1B0E]">{data.patient_name}</span>{' '}
        <span className="font-mono text-[#6D6A60]">({data.patient_code})</span>
      </div>
      <div>
        <span className="text-[#6D6A60] block">Age / Gender</span>
        <span className="font-semibold text-[#1B1B0E]">{data.patient_age || '-'} / {data.patient_gender || '-'}</span>
      </div>
      <div>
        <span className="text-[#6D6A60] block">Investigation</span>
        <span className="font-semibold text-[#1B1B0E]">{data.test_name}</span>{' '}
        <span className="font-mono text-[#6D6A60]">{data.test_code}</span>
        {data.lab_section_label && <span className="block text-[11px] text-[#6D6A60]">Room: {data.lab_section_label}</span>}
      </div>
      <div>
        <span className="text-[#6D6A60] block">Invoice / Sample</span>
        <span className="font-mono text-[#1B1B0E]">
          {data.invoice_no}
          {data.sample_code ? ` · ${data.sample_code}` : ''}
        </span>
        {data.sample_type && <span className="block text-[11px] text-[#6D6A60]">{data.sample_type}</span>}
      </div>
    </div>

    {data.items.length > 0 && (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#F4F3F0] text-[#54524A] border-b border-[#DCDAD4]">
              <th className="py-2 px-3">Parameter</th>
              <th className="py-2 px-3">Result</th>
              <th className="py-2 px-3">Unit</th>
              <th className="py-2 px-3">Reference</th>
              <th className="py-2 px-3">Critical</th>
              <th className="py-2 px-3">Flag</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E8E7E3]">
            {data.items.map((it, idx) => (
              <tr key={`${it.component_code || it.component_name}-${idx}`}>
                <td className="py-1.5 px-3">
                  {it.component_name}
                  {it.comment && <span className="block text-[10px] text-[#6D6A60]">{it.comment}</span>}
                </td>
                <td className={`py-1.5 px-3 ${flagClass(it.flag)}`}>{it.value}</td>
                <td className="py-1.5 px-3 text-[#6D6A60]">{it.unit || ''}</td>
                <td className="py-1.5 px-3 text-[#6D6A60]">{it.reference_range || ''}</td>
                <td className="py-1.5 px-3 text-[#6D6A60]">{criticalText(it.critical_min, it.critical_max)}</td>
                <td className={`py-1.5 px-3 ${flagClass(it.flag)}`}>{it.flag || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}

    {structured.length > 0 && (
      <div className="space-y-1.5">
        {structured.map(([k, v]) => (
          <div key={k}>
            <span className="font-semibold text-[#1B1B0E]">{STRUCTURED_LABELS[k] || k}: </span>
            <span className="text-[#1B1B0E]">{v}</span>
          </div>
        ))}
      </div>
    )}

    {(data.findings || data.impression || data.comments) && (
      <div className="space-y-2">
        {data.findings && (
          <div>
            <span className="font-semibold text-[#1B1B0E] block">Findings</span>
            <p className="whitespace-pre-wrap text-[#1B1B0E]">{data.findings}</p>
          </div>
        )}
        {data.impression && (
          <div>
            <span className="font-semibold text-[#1B1B0E] block">Impression</span>
            <p className="whitespace-pre-wrap text-[#1B1B0E]">{data.impression}</p>
          </div>
        )}
        {data.comments && (
          <div>
            <span className="font-semibold text-[#1B1B0E] block">Comments</span>
            <p className="whitespace-pre-wrap text-[#1B1B0E]">{data.comments}</p>
          </div>
        )}
      </div>
    )}

    {data.items.length === 0 && !data.findings && !data.impression && !data.comments && structured.length === 0 && (
      <p className="text-[#6D6A60]">The saved result has no values yet.</p>
    )}

    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#DCDAD4] text-[11px] text-[#6D6A60]">
      <span className="inline-flex items-center gap-1">
        <FileText className="w-3.5 h-3.5" />
        Result {data.result_status} by {data.entered_by_name || 'staff'}
        {data.updated_at || data.entered_at
          ? ` · ${new Date((data.updated_at || data.entered_at) as string).toLocaleString('en-GB')}`
          : ''}
      </span>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center px-3 py-1.5 text-xs font-semibold bg-white text-[#1B1B0E] border border-[#CAC7BE] rounded-lg hover:bg-[#F4F3F0] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852] cursor-pointer"
        >
          Close
        </button>
      )}
    </div>
  </div>
  );
};

export const ResultReportPreviewModal: React.FC<Props> = ({ isOpen, onClose, testOrderId, source = 'lab', onFinalized }) => {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [finalizing, setFinalizing] = useState(false);
  const finalize = async () => {
    if (!testOrderId) return;
    setFinalizing(true);
    try {
      const r = await api.finalizeReport(testOrderId);
      showToast({ type: 'success', title: 'Report finalized', message: `${r.report_no} is now Final.` });
      onFinalized?.();
      onClose();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Finalize failed', message: err.message });
    } finally {
      setFinalizing(false);
    }
  };
  // Mounted once per order (the parent renders it with key={testOrderId}), so the initial state is
  // already "loading" and the effect only sets state from the async response.
  const [data, setData] = useState<ResultPreview | null>(null);
  const [loading, setLoading] = useState(Boolean(testOrderId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !testOrderId) return;
    let cancelled = false;
    api
      .getResultPreview(testOrderId, source)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err?.message || 'Could not load the result.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, testOrderId, source]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Report Preview"
      subtitle="Saved result, preview only. This is not the issued report."
      maxWidth="2xl"
    >
      {loading ? (
        <div className="py-12 text-center text-xs text-[#6D6A60]">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#525333]" />
          Loading result…
        </div>
      ) : error ? (
        <div className="p-3 text-xs text-rose-800 bg-rose-50 border border-rose-200 rounded-xl">{error}</div>
      ) : data ? (
        <>
          <ResultPreviewBody data={data} onClose={onClose} />
          {!data.is_draft && data.report_status !== 'FINAL' && hasPermission('result.enter') && (
            <div className="mt-3 p-3 rounded-xl border border-[#DCDAD4] bg-[#FAF9F6] text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2" data-testid="finalize-area">
              <span className="text-[#54524A]">
                {data.can_finalize
                  ? 'Finalizing closes this report: its content can no longer be changed.'
                  : data.finalize_blocker}
              </span>
              <button
                type="button"
                onClick={finalize}
                disabled={!data.can_finalize || finalizing}
                data-testid="finalize-report"
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3F4028] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {finalizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                Finalize report
              </button>
            </div>
          )}
        </>
      ) : null}
    </Modal>
  );
};
