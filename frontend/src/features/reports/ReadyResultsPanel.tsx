import React, { useCallback, useEffect, useState } from 'react';
import { Eye, RefreshCw, Search } from 'lucide-react';
import { api } from '../../api/client';
import { LabRoom, ReadyReportItem } from '../../types';
import { Badge } from '../../components/common/Badge';
import { ResultReportPreviewModal } from '../../components/common/ResultReportPreviewModal';
import { useToast } from '../../context/ToastContext';
import { useRefetchOnFocus } from '../../utils/useRefetchOnFocus';

/**
 * Prompt 10F (F3): sidebar Ready Reports, "Ready Results" tab.
 * Lists every Ready result from all rooms (ENTERED result; order not cancelled, not performed or
 * awaiting doctor). Same backend definition as the Lab "Ready Reports" tile. These are not issued
 * reports yet (Module 14): the only action is a read-only Preview.
 * The due column appears only when the backend returns it (money-permitted roles).
 */
export const ReadyResultsPanel: React.FC = () => {
  const { showToast } = useToast();
  const [rows, setRows] = useState<ReadyReportItem[]>([]);
  const [rooms, setRooms] = useState<LabRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [room, setRoom] = useState('ALL');
  const [previewId, setPreviewId] = useState<number | null>(null);

  const fetchRows = useCallback(async () => {
    try {
      const res = await api.getReadyReports({ q: search.trim() || undefined, lab_section: room, limit: 200 });
      setRows(res);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load ready results', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [search, room, showToast]);

  useEffect(() => {
    const t = setTimeout(fetchRows, 250);
    return () => clearTimeout(t);
  }, [fetchRows]);

  useEffect(() => {
    api.getRooms().then(setRooms).catch(() => setRooms([]));
  }, []);

  // Newly saved results appear on navigation (mount) and when the window regains focus
  useRefetchOnFocus(fetchRows);

  const showDue = rows.some((r) => r.invoice_due !== undefined);

  return (
    <div className="space-y-4" data-testid="ready-results-panel">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <p className="text-xs text-[#6D6A60]">
          Results submitted by the lab, from all rooms. Preview only: final report issuing is not built yet.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search patient, invoice, test..."
              aria-label="Search ready results"
              className="text-xs bg-transparent border-none outline-none w-48 text-[#1B1B0E]"
            />
          </div>
          <select
            value={room}
            onChange={(e) => setRoom(e.target.value)}
            aria-label="Filter by room"
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
          <button
            type="button"
            onClick={() => fetchRows()}
            className="p-2 bg-white border border-[#CAC7BE] rounded-xl hover:bg-[#F4F3F0] cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
            title="Refresh"
            aria-label="Refresh ready results"
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
                <th className="pb-3">Result entered</th>
                {showDue && <th className="pb-3 text-right">Payment</th>}
                <th className="pb-3 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={showDue ? 7 : 6} className="py-10 text-center text-[#8E8A7E]" data-testid="ready-results-empty">
                    {search.trim() || room !== 'ALL'
                      ? 'No ready results match these filters.'
                      : 'No results are ready yet. A result appears here as soon as the lab submits it; drafts are not shown.'}
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.test_order_id} className="hover:bg-[#F4F3F0] transition-colors" data-testid={`ready-row-${r.test_order_id}`}>
                  <td className="py-3 pl-2 font-mono font-bold text-[#1B1B0E]">{r.invoice_no}</td>
                  <td className="py-3">
                    <div className="font-semibold text-[#1B1B0E]">{r.patient_name}</div>
                    <div className="text-[11px] text-[#6D6A60]">{r.patient_phone || r.patient_code}</div>
                  </td>
                  <td className="py-3">
                    <div className="font-medium text-[#1B1B0E]">{r.test_name}</div>
                    <div className="text-[10px] text-[#8E8A7E] font-mono">{r.test_code}</div>
                  </td>
                  <td className="py-3 text-[#6D6A60]">{r.lab_section_label || 'No room'}</td>
                  <td className="py-3 text-[#54524A]">
                    {r.result_entered_at ? new Date(r.result_entered_at).toLocaleString('en-GB') : '-'}
                    {r.result_entered_by_name && <span className="block text-[10px] text-[#8E8A7E]">by {r.result_entered_by_name}</span>}
                  </td>
                  {showDue && (
                    <td className="py-3 text-right">
                      {r.has_due ? (
                        <Badge variant="danger" size="sm" dot>
                          Due ৳{(r.invoice_due || 0).toLocaleString()}
                        </Badge>
                      ) : (
                        <Badge variant="success" size="sm">
                          Paid
                        </Badge>
                      )}
                    </td>
                  )}
                  <td className="py-3 text-right pr-2">
                    <button
                      type="button"
                      onClick={() => setPreviewId(r.test_order_id)}
                      data-testid={`ready-preview-${r.test_order_id}`}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-white text-[#2B547E] border border-[#B9C9DA] rounded-lg hover:bg-[#EEF3F8] cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Preview Report
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {previewId !== null && (
        <ResultReportPreviewModal key={previewId} isOpen onClose={() => setPreviewId(null)} testOrderId={previewId} source="reports" onFinalized={fetchRows} />
      )}
    </div>
  );
};
