import React, { useState, useEffect } from 'react';
import {
  GitBranch,
  Search,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowRight,
  Filter,
  Layers,
  Sparkles,
} from 'lucide-react';
import { api } from '../../api/client';
import { UnassignedTestOrder, LabRoom } from '../../types';
import { Badge } from '../../components/common/Badge';
import { useToast } from '../../context/ToastContext';
import { AssignedTestsPanel } from './AssignedTestsPanel';
import { useRefetchOnFocus } from '../../utils/useRefetchOnFocus';

export const AssignmentsPage: React.FC = () => {
  // Prompt 10F (F1): two views on one page: route UNASSIGNED orders, or see every Assigned Test
  const [view, setView] = useState<'UNASSIGNED' | 'ASSIGNED'>('UNASSIGNED');
  const [unassigned, setUnassigned] = useState<UnassignedTestOrder[]>([]);
  // Prompt 10E: the routing target is a lab room (never a technician, never a destination id)
  const [rooms, setRooms] = useState<LabRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');

  // Selected for assignment
  const [assignmentMap, setAssignmentMap] = useState<Record<string, string>>({});
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [assigning, setAssigning] = useState(false);

  const { showToast } = useToast();

  const fetchData = async () => {
    try {
      setLoading(true);
      const [orders, roomList] = await Promise.all([
        api.getUnassignedTests(searchTerm || undefined, departmentFilter !== 'ALL' ? departmentFilter : undefined),
        api.getRooms(),
      ]);
      setUnassigned(orders);
      setRooms(roomList);

      // Prepopulate with the order's own room (empty room) when it has one; otherwise no choice yet
      const initialMap: Record<string, string> = {};
      orders.forEach((o) => {
        if (o.lab_section) initialMap[o.id] = o.lab_section;
      });
      setAssignmentMap(initialMap);
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to fetch unassigned orders', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchData();
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm, departmentFilter]);

  // Prompt 10F: refresh when the user comes back (orders may have been demoted or released meanwhile)
  useRefetchOnFocus(() => {
    if (view === 'UNASSIGNED') fetchData();
  });

  const handleSelectDestination = (orderId: string, roomCode: string) => {
    setAssignmentMap((prev) => ({ ...prev, [orderId]: roomCode }));
  };

  const handleAssignSingle = async (order: UnassignedTestOrder) => {
    const roomCode = assignmentMap[order.id];
    if (!roomCode) {
      showToast({ type: 'warning', title: 'Select a Room', message: 'Please select the lab room for this test.' });
      return;
    }

    try {
      await api.assignTest(order.id, roomCode, 'Reception routing to lab room');
      showToast({
        type: 'success',
        title: 'Workstation Assigned',
        message: `${order.test_name} assigned successfully.`,
      });
      fetchData();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Assignment Failed', message: err.message });
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  const handleSelectAll = () => {
    if (selectedIds.length === unassigned.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(unassigned.map((o) => o.id));
    }
  };

  const handleBulkAssign = async () => {
    if (selectedIds.length === 0) return;
    const missing = selectedIds.filter((id) => !assignmentMap[id]);
    if (missing.length > 0) {
      showToast({ type: 'warning', title: 'Select a Room', message: `${missing.length} selected order(s) have no room chosen.` });
      return;
    }
    setAssigning(true);
    try {
      const payload = selectedIds.map((id) => ({
        test_order_id: id,
        lab_section: assignmentMap[id],
      }));
      await api.bulkAssign(payload);
      showToast({
        type: 'success',
        title: 'Bulk Assignment Complete',
        message: `${payload.length} test orders routed to lab rooms.`,
      });
      setSelectedIds([]);
      fetchData();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Bulk Assignment Failed', message: err.message });
    } finally {
      setAssigning(false);
    }
  };

  const departments = ['ALL', ...Array.from(new Set(unassigned.map((o) => o.department)))];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-[#1B1B0E]">Workstation Test Assignment</h1>
          <p className="text-xs text-[#6D6A60]">
            Route unassigned investigations to a lab room. Every active technician of that room can work them.
          </p>
        </div>

        {view === 'UNASSIGNED' && (
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CAC7BE] rounded-xl shadow-2xs">
            <Search className="w-4 h-4 text-[#8E8A7E]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter by test, invoice, patient..."
              className="text-xs bg-transparent border-none outline-none w-52 text-[#1B1B0E]"
            />
          </div>

          <select
            value={departmentFilter}
            onChange={(e) => setDepartmentFilter(e.target.value)}
            className="bg-white border border-[#CAC7BE] rounded-xl px-3 py-1.5 text-xs font-medium text-[#54524A] shadow-2xs cursor-pointer"
          >
            {departments.map((dept) => (
              <option key={dept} value={dept}>
                {dept}
              </option>
            ))}
          </select>
        </div>
        )}
      </div>

      {/* Prompt 10F (F1): view switch */}
      <div className="flex items-center gap-1.5" role="tablist" aria-label="Assignment views">
        {([
          { id: 'UNASSIGNED', label: `Unassigned (${unassigned.length})` },
          { id: 'ASSIGNED', label: 'Assigned Tests' },
        ] as const).map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={view === t.id}
            data-testid={`assignments-tab-${t.id}`}
            onClick={() => setView(t.id)}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852] ${
              view === t.id ? 'bg-[#525333] text-white shadow-xs' : 'bg-[#F4F3F0] text-[#54524A] hover:bg-[#E8E7E3]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {view === 'ASSIGNED' ? (
        <AssignedTestsPanel onChanged={fetchData} />
      ) : (
      <>

      {/* Bulk Action Bar (when selected) */}
      {selectedIds.length > 0 && (
        <div className="p-3 bg-[#FAF3EC] border border-[#E6C4A7] rounded-xl flex items-center justify-between animate-in fade-in text-xs">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[#96572A]">
              {selectedIds.length} {selectedIds.length === 1 ? 'order' : 'orders'} selected for routing
            </span>
          </div>

          <button
            onClick={handleBulkAssign}
            disabled={assigning}
            className="px-4 py-1.5 bg-[#CF8852] hover:bg-[#B7703B] text-white font-bold rounded-lg shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{assigning ? 'Routing...' : 'Assign Selected Orders'}</span>
          </button>
        </div>
      )}

      {/* Unassigned Test Orders List */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-5 shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E8E7E3] text-[#6D6A60] uppercase tracking-wider font-semibold">
                <th className="pb-3 pl-2 w-8">
                  <input
                    type="checkbox"
                    checked={unassigned.length > 0 && selectedIds.length === unassigned.length}
                    onChange={handleSelectAll}
                    className="rounded text-[#CF8852] focus:ring-0 cursor-pointer"
                  />
                </th>
                <th className="pb-3">Invoice #</th>
                <th className="pb-3">Patient</th>
                <th className="pb-3">Investigation</th>
                <th className="pb-3">Dept</th>
                <th className="pb-3">Urgency</th>
                <th className="pb-3">Lab Room</th>
                <th className="pb-3 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {unassigned.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#8E8A7E]">
                    <CheckCircle2 className="w-8 h-8 text-[#2D8A39] mx-auto mb-2 opacity-80" />
                    All test orders have been routed to lab rooms!
                  </td>
                </tr>
              )}
              {unassigned.map((order) => {
                const isSelected = selectedIds.includes(order.id);
                return (
                  <tr
                    key={order.id}
                    className={`transition-colors ${isSelected ? 'bg-[#FAF3EC]/60' : 'hover:bg-[#F4F3F0]'}`}
                  >
                    <td className="py-3 pl-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleSelect(order.id)}
                        className="rounded text-[#CF8852] focus:ring-0 cursor-pointer"
                      />
                    </td>
                    <td className="py-3 font-mono font-bold text-[#1B1B0E]">{order.invoice_number}</td>
                    <td className="py-3">
                      <div className="font-semibold text-[#1B1B0E]">{order.patient_name}</div>
                      <div className="text-[11px] text-[#6D6A60]">{order.patient_phone}</div>
                    </td>
                    <td className="py-3">
                      <div className="font-semibold text-[#1B1B0E]">{order.test_name}</div>
                      <div className="text-[11px] text-[#8E8A7E] font-mono">{order.test_code}</div>
                    </td>
                    <td className="py-3 text-[#6D6A60]">{order.department}</td>
                    <td className="py-3">
                      {order.is_urgent ? (
                        <Badge variant="danger" size="sm" dot>
                          URGENT
                        </Badge>
                      ) : (
                        <Badge variant="neutral" size="sm">
                          Standard
                        </Badge>
                      )}
                    </td>
                    <td className="py-3">
                      <select
                        aria-label={`Lab room for ${order.test_name}`}
                        data-testid={`assign-room-select-${order.id}`}
                        value={assignmentMap[order.id] || ''}
                        onChange={(e) => handleSelectDestination(order.id, e.target.value)}
                        className="bg-white border border-[#CAC7BE] rounded-lg px-2.5 py-1 text-xs font-semibold text-[#1B1B0E] max-w-[220px]"
                      >
                        <option value="">Select room…</option>
                        {rooms.map((r) => (
                          <option key={r.code} value={r.code}>
                            {r.name} ({r.room}){r.active_technicians === 0 ? ' — no technician' : ''}
                          </option>
                        ))}
                      </select>
                      {order.lab_section_label && (
                        <div className="text-[10px] text-[#8E8A7E] mt-0.5">Waiting room: {order.lab_section_label}</div>
                      )}
                    </td>
                    <td className="py-3 text-right pr-2">
                      <button
                        onClick={() => handleAssignSingle(order)}
                        className="px-3 py-1 bg-[#525333] hover:bg-[#444529] text-white font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer text-xs flex items-center gap-1 ml-auto"
                      >
                        <span>Assign</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}
    </div>
  );
};

