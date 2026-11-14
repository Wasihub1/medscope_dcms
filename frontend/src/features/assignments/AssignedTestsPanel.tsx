import React, { useCallback, useEffect, useState } from 'react';
import { MoveRight, RefreshCw, Search, Lock } from 'lucide-react';
import { api } from '../../api/client';
import { AssignedTestOrder, LabRoom } from '../../types';
import { Badge } from '../../components/common/Badge';
import { Modal } from '../../components/common/Modal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useRefetchOnFocus } from '../../utils/useRefetchOnFocus';

/**
 * Prompt 10F (F1): Assigned Tests view inside the Assign Tests page.
 * - Every test order: invoice, patient, test, room, the room's active technicians (or UNASSIGNED),
 *   status, urgent flag and created time. Money-free.
 * - RECEPTIONIST / CASHIER: view only. ADMIN / OWNER (worklist.reassign): Reassign Room on rows that
 *   are not COMPLETED, cancelled or not performed. The backend decides can_reassign per row and
 *   refuses the call anyway; this page only reflects it.
 * - Reassign reuses POST /worklist/{id}/reassign (reason, append-only history, audit row).
 */
const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'ALL', label: 'All statuses' },
  { value: 'OPEN', label: 'Open (not completed)' },
  { value: 'UNASSIGNED', label: 'Unassigned' },
  { value: 'ASSIGNED', label: 'Assigned' },
  { value: 'SAMPLE_PENDING', label: 'Sample pending' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'AWAITING_DOCTOR', label: 'Awaiting doctor' },
  { value: 'PENDING', label: 'Pending (outsourced)' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'NOT_PERFORMED', label: 'Not performed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

const statusVariant = (s: string) =>
  s === 'COMPLETED' ? 'success' : s === 'UNASSIGNED' ? 'warning' : s === 'CANCELLED' || s === 'REJECTED' || s === 'SPOILED' ? 'danger' : s === 'AWAITING_DOCTOR' ? 'orange' : 'info';

interface Props {
  /** Called after a successful move so the parent can refresh its own lists. */
  onChanged?: () => void;
}

export const AssignedTestsPanel: React.FC<Props> = ({ onChanged }) => {
  const { hasPermission } = useAuth();
  const canReassign = hasPermission('worklist.reassign');
  const { showToast } = useToast();

  const [rows, setRows] = useState<AssignedTestOrder[]>([]);
  const [rooms, setRooms] = useState<LabRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [roomFilter, setRoomFilter] = useState('ALL');
  const [search, setSearch] = useState('');

  const [target, setTarget] = useState<AssignedTestOrder | null>(null);
  const [newRoom, setNewRoom] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchRows = useCallback(async () => {
    try {
      const res = await api.getAssignedOrders({
        status: statusFilter,
        lab_section: roomFilter,
        q: search.trim() || undefined,
        limit: 300,
      });
      setRows(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load assigned tests', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [statusFilter, roomFilter, search, showToast]);

  useEffect(() => {
    const t = setTimeout(fetchRows, 250);
    return () => clearTimeout(t);
  }, [fetchRows]);

  useEffect(() => {
    api.getRooms().then(setRooms).catch(() => setRooms([]));
  }, []);

  useRefetchOnFocus(fetchRows);

  const openReassign = (row: AssignedTestOrder) => {
    setTarget(row);
    setNewRoom('');
    setReason('');
  };

  const submitReassign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target || !newRoom) return;
    setSaving(true);
    try {
      const res = await api.reassignRoom(target.test_order_id, newRoom, reason.trim() || undefined);
      showToast({
        type: 'success',
        title: 'Room changed',
        message: `${target.test_name} (order #${target.test_order_id}) moved to ${res.lab_section_label || newRoom}.`,
      });
      setTarget(null);
      await fetchRows();
      onChanged?.();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Reassign failed', message: err.message || 'Could not move the order.' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="assigned-tests-panel">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <p className="text-xs text-[#6D6A60]">
          {canReassign
            ? 'Every test order with its lab room. You can move an order to another room until it is completed.'
            : 'Every test order with its lab room. View only: moving an order to another room is done by an Admin or Owner.'}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search patient, invoice, test..."
              aria-label="Search assigned tests"
              className="text-xs bg-transparent border-none outline-none w-48 text-[#1B1B0E]"
            />
          </div>
          <select
            value={roomFilter}
            onChange={(e) => setRoomFilter(e.target.value)}
            aria-label="Filter by room"
            data-testid="assigned-room-filter"
            className="bg-white border border-[#CAC7BE] rounded-xl px-3 py-1.5 text-xs font-medium text-[#54524A] shadow-2xs cursor-pointer"
          >
            <option value="ALL">All rooms</option>
            {rooms.map((r) => (
              <option key={r.code} value={r.code}>
                {r.name} ({r.room})
              </option>
            ))}
            <option value="NONE">No room</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
            data-testid="assigned-status-filter"
            className="bg-white border border-[#CAC7BE] rounded-xl px-3 py-1.5 text-xs font-medium text-[#54524A] shadow-2xs cursor-pointer"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => fetchRows()}
            className="p-2 bg-white border border-[#CAC7BE] rounded-xl hover:bg-[#F4F3F0] cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
            title="Refresh"
            aria-label="Refresh assigned tests"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#525333]" />
          </button>
        </div>
      </div>

      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2">Invoice #</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3">Investigation</th>
                <th className="pb-3">Room</th>
                <th className="pb-3">Technician(s)</th>
                <th className="pb-3">Status</th>
                <th className="pb-3">Created</th>
                <th className="pb-3 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-[#8E8A7E]">
                    No test orders match these filters.
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.test_order_id} className="hover:bg-[#F4F3F0] transition-colors" data-testid={`assigned-row-${r.test_order_id}`}>
                  <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{r.invoice_no}</td>
                  <td className="py-3">
                    <div className="font-semibold text-[#1B1B0E]">{r.patient_name}</div>
                    <div className="text-[11px] text-[#6D6A60] font-mono">{r.patient_code}</div>
                  </td>
                  <td className="py-3">
                    <div className="font-semibold text-[#1B1B0E]">{r.test_name}</div>
                    <div className="text-[11px] text-[#8E8A7E] font-mono">
                      {r.test_code}
                      {r.urgent && (
                        <span className="ml-1.5 align-middle">
                          <Badge variant="danger" size="sm" dot>
                            URGENT
                          </Badge>
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 text-[#1B1B0E]">{r.lab_section_label || <span className="text-[#8E8A7E]">No room</span>}</td>
                  <td className="py-3">
                    {r.assignment_state === 'UNASSIGNED' ? (
                      <Badge variant="warning" size="sm">
                        UNASSIGNED
                      </Badge>
                    ) : (
                      <span className="text-[#1B1B0E]">{r.technician_names.join(', ')}</span>
                    )}
                    {r.worked_by_name && <div className="text-[10px] text-[#6D6A60]">Worked by: {r.worked_by_name}</div>}
                  </td>
                  <td className="py-3">
                    <Badge variant={statusVariant(r.status) as any} size="sm">
                      {r.status.replace(/_/g, ' ')}
                    </Badge>
                    {r.result_status && <div className="text-[10px] text-[#6D6A60] mt-0.5">Result: {r.result_status}</div>}
                  </td>
                  <td className="py-3 text-[#6D6A60] whitespace-nowrap">{new Date(r.created_at).toLocaleString('en-GB')}</td>
                  <td className="py-3 text-right pr-2">
                    {canReassign &&
                      (r.can_reassign ? (
                        <button
                          type="button"
                          onClick={() => openReassign(r)}
                          data-testid={`assigned-reassign-${r.test_order_id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#54524A] bg-white border border-[#CAC7BE] rounded-lg hover:bg-[#F4F3F0] cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
                        >
                          <MoveRight className="w-3 h-3" />
                          Reassign Room
                        </button>
                      ) : (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] text-[#8E8A7E]"
                          title={r.reassign_block_reason || undefined}
                        >
                          <Lock className="w-3 h-3" />
                          {(r.reassign_block_reason || 'Locked').split(':')[0]}
                        </span>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal isOpen={target !== null} onClose={() => setTarget(null)} title="Reassign to Another Room">
        {target && (
          <form onSubmit={submitReassign} className="space-y-4 text-xs">
            <div className="p-3 bg-[#F4F3F0] rounded-xl border border-[#DCDAD4] space-y-1">
              <span className="font-semibold text-[#1B1B0E] block">
                Order #{target.test_order_id}: {target.test_name}
              </span>
              <span className="text-[#6D6A60] block">Current room: {target.lab_section_label || 'none'}</span>
              <span className="text-[#6D6A60] block">Samples and results already entered are kept.</span>
            </div>
            <div>
              <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor="assigned-reassign-room">
                New room *
              </label>
              <select
                id="assigned-reassign-room"
                data-testid="assigned-reassign-room-select"
                required
                value={newRoom}
                onChange={(e) => setNewRoom(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              >
                <option value="" disabled>
                  Select a room…
                </option>
                {rooms
                  .filter((r) => r.code !== target.lab_section)
                  .map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.name} ({r.room}){r.active_technicians === 0 ? ' — no technician' : ''}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor="assigned-reassign-reason">
                Reason (optional)
              </label>
              <input
                id="assigned-reassign-reason"
                type="text"
                maxLength={255}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. analyser down in this room"
                className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button type="button" onClick={() => setTarget(null)} className="px-4 py-2 font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer">
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || !newRoom}
                className="px-4 py-2 font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3E3F27] disabled:opacity-50 cursor-pointer"
              >
                {saving ? 'Moving…' : 'Move Order'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};
