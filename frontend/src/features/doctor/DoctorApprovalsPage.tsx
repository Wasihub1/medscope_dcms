import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Loader2, RefreshCw, Search, ShieldCheck, UserCheck } from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { ResultPreviewBody } from '../../components/common/ResultReportPreviewModal';
import { useRefetchOnFocus } from '../../utils/useRefetchOnFocus';
import { ApprovalDetail, ApprovalQueue, ApprovalQueueItem, DoctorRef } from '../../types';

/**
 * Prompt 15 (D22): Doctor sign-off.
 * Results whose test needs a doctor (doctor-required or both-signature), submitted by the lab and not
 * yet approved. Two paths share this screen:
 *  - Admin / Owner see every doctor's pending results and record the approval on a doctor's behalf
 *    (doctor picker + mandatory attestation tick). This is the only path for visiting doctors (no login).
 *  - A DOCTOR login sees only results assigned to their own doctor profile and approves them directly.
 * No rejection / send-back here (not decided yet) and no final report issuing (Module 14).
 */
const RULE_LABEL: Record<string, string> = {
  DOCTOR_REQUIRED: 'Doctor required',
  BOTH_SIGNATURES: 'Both signatures',
};

const inputCls =
  'w-full text-xs bg-white border border-[#CAC7BE] rounded-xl px-3 py-2 text-[#1B1B0E] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]';

type DoctorOption = DoctorRef & { referrer_type?: string };
const NON_DOCTOR_TYPES = ['agent', 'clinic', 'institution', 'other', 'third party'];

/** Doctor search by name, same source as the referrer / doctor search elsewhere (GET /referrers). */
const DoctorPicker: React.FC<{
  id: string;
  value: DoctorRef | null;
  onChange: (d: DoctorRef | null) => void;
}> = ({ id, value, onChange }) => {
  const [q, setQ] = useState('');
  const [options, setOptions] = useState<DoctorOption[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      api
        .getReferrers(q.trim() || undefined)
        .then((rs) =>
          setOptions(
            (rs as any[])
              .filter((r) => !NON_DOCTOR_TYPES.includes(String(r.referrer_type || '').toLowerCase()))
              .map((r) => ({ id: Number(r.id), name: String(r.name), registration_no: r.registration_no ?? null, specialty: r.specialty ?? null }))
          )
        )
        .catch(() => setOptions([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q, open]);

  if (value) {
    return (
      <div className="flex items-center justify-between gap-2 px-3 py-2 bg-[#F4F3F0] border border-[#DCDAD4] rounded-xl text-xs" data-testid={`${id}-selected`}>
        <span>
          <span className="font-semibold text-[#1B1B0E]">{value.name}</span>{' '}
          <span className="text-[#6D6A60]">{value.registration_no ? `Reg ${value.registration_no}` : 'no registration number on file'}</span>
        </span>
        <button type="button" onClick={() => onChange(null)} className="text-[#525333] font-semibold hover:underline cursor-pointer">
          Change
        </button>
      </div>
    );
  }
  return (
    <div className="relative">
      <input
        id={id}
        type="text"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search doctor by name…"
        aria-label="Search doctor by name"
        autoComplete="off"
        className={inputCls}
        data-testid={id}
      />
      {open && (
        <ul className="absolute z-20 mt-1 w-full max-h-48 overflow-auto bg-white border border-[#CAC7BE] rounded-xl shadow-lg text-xs" role="listbox">
          {options.length === 0 && <li className="px-3 py-2 text-[#6D6A60]">No doctor found.</li>}
          {options.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                role="option"
                aria-selected="false"
                onClick={() => {
                  onChange(d);
                  setOpen(false);
                  setQ('');
                }}
                className="w-full text-left px-3 py-2 hover:bg-[#F4F3F0] cursor-pointer"
              >
                <span className="font-semibold text-[#1B1B0E]">{d.name}</span>{' '}
                <span className="text-[#6D6A60]">{d.registration_no ? `Reg ${d.registration_no}` : 'no registration number'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const ApprovalModal: React.FC<{
  testOrderId: number;
  onClose: () => void;
  onDone: () => void;
}> = ({ testOrderId, onClose, onDone }) => {
  const { showToast } = useToast();
  const [detail, setDetail] = useState<ApprovalDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [doctor, setDoctor] = useState<DoctorRef | null>(null);
  const [attest, setAttest] = useState(false);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getApprovalDetail(testOrderId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        if (d.assigned_doctor) setDoctor(d.assigned_doctor);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err?.message || 'Could not load this result.');
      });
    return () => {
      cancelled = true;
    };
  }, [testOrderId]);

  const staffPath = detail?.path === 'STAFF_ATTESTATION';
  const doctorName = staffPath ? doctor?.name : detail?.my_doctor?.name;
  const canSubmit = Boolean(detail?.can_approve) && !busy && (!staffPath || (Boolean(doctor) && attest));

  const submit = async () => {
    if (!detail) return;
    setBusy(true);
    try {
      await api.approveResult(
        detail.test_order_id,
        staffPath ? { doctor_id: doctor!.id, attestation: attest, notes: notes.trim() || undefined } : { notes: notes.trim() || undefined }
      );
      showToast({ type: 'success', title: 'Approval recorded', message: `${detail.preview.test_name} approved${doctorName ? ` for ${doctorName}` : ''}.` });
      onDone();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Approval failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title="Doctor sign-off"
      subtitle={staffPath ? 'Record the approval on the doctor’s behalf.' : 'Review the result and approve it.'}
      maxWidth="4xl"
    >
      {error ? (
        <div className="p-3 text-xs text-rose-800 bg-rose-50 border border-rose-200 rounded-xl">{error}</div>
      ) : !detail ? (
        <div className="py-12 text-center text-xs text-[#6D6A60]">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#525333]" />
          Loading result…
        </div>
      ) : (
        <div className="space-y-4 text-xs" data-testid="approval-modal">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-3 bg-[#EEF3F8] border border-[#B9C9DA] rounded-xl text-[#2B547E]">
            <div>
              <span className="block opacity-75">Approval rule</span>
              <span className="font-semibold" data-testid="approval-rule">{RULE_LABEL[detail.approval_rule] || detail.approval_rule}</span>
            </div>
            <div>
              <span className="block opacity-75">Technician sign-off</span>
              <span className="font-semibold">
                {detail.technician_name || 'Lab staff'}
                {detail.technician_signed_at ? ` · ${new Date(detail.technician_signed_at).toLocaleString('en-GB')}` : ''}
              </span>
            </div>
            <div>
              <span className="block opacity-75">Doctor</span>
              <span className="font-semibold" data-testid="approval-doctor">
                {(staffPath ? doctor : detail.my_doctor)?.name || 'Not selected'}
                {(staffPath ? doctor : detail.my_doctor)?.registration_no ? ` · Reg ${(staffPath ? doctor : detail.my_doctor)!.registration_no}` : ''}
              </span>
            </div>
          </div>

          <ResultPreviewBody data={detail.preview} hideReadyNote />

          {detail.approval ? (
            <div className="flex items-start gap-2 p-3 rounded-xl border border-emerald-200 bg-emerald-50 text-emerald-900" data-testid="approval-existing">
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                Approved for <b>{detail.approval.doctor.name}</b> (Reg {detail.approval.doctor.registration_no}) on{' '}
                {new Date(detail.approval.approved_at).toLocaleString('en-GB')}.{' '}
                {detail.approval.is_attestation
                  ? `Recorded by ${detail.approval.approved_by_name || 'staff'} (${detail.approval.approved_by_role}) on the doctor’s behalf.`
                  : 'Approved by the doctor personally.'}
              </span>
            </div>
          ) : (
            <div className="space-y-3 pt-3 border-t border-[#DCDAD4]">
              {!detail.can_approve && detail.blocked_reason && (
                <div className="p-3 rounded-xl border border-amber-300 bg-amber-50 text-amber-900" role="status">{detail.blocked_reason}</div>
              )}
              {staffPath ? (
                <>
                  <div>
                    <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor="approval-doctor-search">Doctor *</label>
                    <DoctorPicker id="approval-doctor-search" value={doctor} onChange={setDoctor} />
                  </div>
                  <label className="flex items-start gap-2 text-[#1B1B0E]">
                    <input
                      type="checkbox"
                      className="mt-0.5 accent-[#525333]"
                      checked={attest}
                      onChange={(e) => setAttest(e.target.checked)}
                      data-testid="approval-attestation"
                    />
                    <span>
                      I confirm {doctor ? <b>{doctor.name}</b> : 'the selected doctor'} has reviewed and approved this result, and I am recording the
                      approval on their behalf.
                    </span>
                  </label>
                </>
              ) : (
                <p className="text-[#54524A]">
                  You are approving this result as <b>{detail.my_doctor?.name}</b>
                  {detail.my_doctor?.registration_no ? ` (Reg ${detail.my_doctor.registration_no})` : ''}.
                </p>
              )}
              <div>
                <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor="approval-notes">Notes (optional)</label>
                <textarea
                  id="approval-notes"
                  rows={2}
                  maxLength={500}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="flex flex-col-reverse sm:flex-row justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold bg-white text-[#1B1B0E] border border-[#CAC7BE] rounded-xl hover:bg-[#F4F3F0] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={submit}
                  disabled={!canSubmit}
                  data-testid="approval-confirm"
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3F4028] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  {staffPath ? 'Confirm approval on behalf' : 'Approve'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};

/** Admin/Owner: pick the doctor whose queue an order belongs to (the DOCTOR login then finds it). */
const AssignModal: React.FC<{ item: ApprovalQueueItem; onClose: () => void; onDone: () => void }> = ({ item, onClose, onDone }) => {
  const { showToast } = useToast();
  const [doctor, setDoctor] = useState<DoctorRef | null>(item.assigned_doctor || null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api.assignApprovalDoctor(item.test_order_id, doctor ? doctor.id : null);
      showToast({ type: 'success', title: 'Doctor assigned', message: doctor ? `${item.test_name} is now in ${doctor.name}'s queue.` : 'Assignment cleared.' });
      onDone();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Assign failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal isOpen onClose={onClose} title="Assign to a doctor" subtitle={`${item.test_name} · ${item.patient_name}`} maxWidth="md">
      <div className="space-y-3 text-xs">
        <label className="block font-semibold text-[#1B1B0E]" htmlFor="assign-doctor-search">Doctor</label>
        <DoctorPicker id="assign-doctor-search" value={doctor} onChange={setDoctor} />
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-semibold bg-white border border-[#CAC7BE] rounded-xl hover:bg-[#F4F3F0] cursor-pointer">
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={busy}
            data-testid="assign-confirm"
            className="px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3F4028] disabled:opacity-50 cursor-pointer"
          >
            {doctor ? 'Assign' : 'Clear assignment'}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export const DoctorApprovalsPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [queue, setQueue] = useState<ApprovalQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterDoctor, setFilterDoctor] = useState<DoctorRef | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [assigning, setAssigning] = useState<ApprovalQueueItem | null>(null);

  const allowed = hasPermission('result.complete_doctor_routed');

  const fetchQueue = useCallback(async () => {
    try {
      setQueue(await api.getApprovalQueue({ q: search.trim() || undefined, doctor_id: filterDoctor?.id }));
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load the sign-off queue', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [search, filterDoctor, showToast]);

  useEffect(() => {
    if (!allowed) return;
    const t = setTimeout(fetchQueue, 250);
    return () => clearTimeout(t);
  }, [fetchQueue, allowed]);
  useRefetchOnFocus(fetchQueue);

  if (!allowed) {
    return (
      <div className="bg-white border border-[#DCDAD4] rounded-2xl p-6 text-xs text-[#6D6A60]" data-testid="approvals-forbidden">
        You do not have permission to view doctor sign-off.
      </div>
    );
  }

  const own = queue?.scope === 'OWN';

  return (
    <div className="space-y-4" data-testid="doctor-approvals-page">
      <div>
        <h1 className="text-lg font-bold text-[#1B1B0E] flex items-center gap-2">
          <UserCheck className="w-5 h-5 text-[#525333]" /> Doctor Sign-off
        </h1>
        <p className="text-xs text-[#6D6A60] mt-1">
          {own
            ? 'Results assigned to you, waiting for your approval.'
            : 'Submitted results waiting for a doctor’s approval. Record the approval on the doctor’s behalf with the attestation tick.'}
        </p>
      </div>

      {own && !queue?.my_doctor && (
        <div className="p-3 text-xs text-amber-900 bg-amber-50 border border-amber-300 rounded-xl" role="status" data-testid="no-doctor-profile">
          Your login is not linked to a doctor profile yet, so no results can be assigned to you. Ask the Owner or an Admin to link it in User Management.
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
          <Search className="w-4 h-4 text-[#8E8A7E]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search patient, invoice, test..."
            aria-label="Search sign-off queue"
            className="text-xs bg-transparent border-none outline-none w-48 text-[#1B1B0E]"
          />
        </div>
        {!own && (
          <div className="w-64">
            <DoctorPicker id="queue-doctor-filter" value={filterDoctor} onChange={setFilterDoctor} />
          </div>
        )}
        {!own && !filterDoctor && <span className="text-[11px] text-[#6D6A60]">Showing all doctors. Pick one to filter.</span>}
        <button
          type="button"
          onClick={() => fetchQueue()}
          className="p-2 bg-white border border-[#CAC7BE] rounded-xl hover:bg-[#F4F3F0] cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
          title="Refresh"
          aria-label="Refresh sign-off queue"
        >
          <RefreshCw className="w-3.5 h-3.5 text-[#525333]" />
        </button>
      </div>

      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        {loading ? (
          <div className="py-10 text-center text-xs text-[#6D6A60]">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#525333]" />
            Loading…
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                  <th className="pb-3 pl-2">Invoice #</th>
                  <th className="pb-3">Patient</th>
                  <th className="pb-3">Test</th>
                  <th className="pb-3">Rule</th>
                  <th className="pb-3">Technician</th>
                  <th className="pb-3">Doctor</th>
                  <th className="pb-3 pr-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E8E7E3]">
                {(queue?.items || []).length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-[#6D6A60]" data-testid="approvals-empty">
                      Nothing is waiting for a doctor’s approval.
                    </td>
                  </tr>
                )}
                {(queue?.items || []).map((it) => (
                  <tr key={it.test_order_id} data-testid={`approval-row-${it.test_order_id}`}>
                    <td className="py-2.5 pl-2 font-mono">{it.invoice_no}</td>
                    <td className="py-2.5">
                      <span className="font-semibold text-[#1B1B0E]">{it.patient_name}</span>
                      <span className="block font-mono text-[10px] text-[#6D6A60]">{it.patient_code}</span>
                    </td>
                    <td className="py-2.5">
                      {it.test_name}
                      {it.urgent && <span className="ml-1"><Badge variant="danger">Urgent</Badge></span>}
                    </td>
                    <td className="py-2.5">
                      <Badge variant={it.approval_rule === 'BOTH_SIGNATURES' ? 'info' : 'warning'}>{RULE_LABEL[it.approval_rule] || it.approval_rule}</Badge>
                    </td>
                    <td className="py-2.5 text-[#54524A]">{it.technician_name || '-'}</td>
                    <td className="py-2.5 text-[#54524A]">{it.assigned_doctor?.name || <span className="text-[#8E8A7E]">Not assigned</span>}</td>
                    <td className="py-2.5 pr-2 text-right whitespace-nowrap">
                      {!own && (
                        <button
                          type="button"
                          onClick={() => setAssigning(it)}
                          className="mr-2 px-2.5 py-1.5 text-[11px] font-semibold bg-white text-[#525333] border border-[#CAC7BE] rounded-lg hover:bg-[#F4F3F0] cursor-pointer"
                        >
                          Assign doctor
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setOpenId(it.test_order_id)}
                        data-testid={`approval-open-${it.test_order_id}`}
                        className="px-2.5 py-1.5 text-[11px] font-semibold bg-[#525333] text-white rounded-lg hover:bg-[#3F4028] cursor-pointer"
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {openId !== null && (
        <ApprovalModal
          key={openId}
          testOrderId={openId}
          onClose={() => setOpenId(null)}
          onDone={() => {
            setOpenId(null);
            fetchQueue();
          }}
        />
      )}
      {assigning && (
        <AssignModal
          key={assigning.test_order_id}
          item={assigning}
          onClose={() => setAssigning(null)}
          onDone={() => {
            setAssigning(null);
            fetchQueue();
          }}
        />
      )}
    </div>
  );
};
