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
import { UnassignedTestOrder, TestDestination } from '../../types';
import { Badge } from '../../components/common/Badge';
import { useToast } from '../../context/ToastContext';

export const AssignmentsPage: React.FC = () => {
  const [unassigned, setUnassigned] = useState<UnassignedTestOrder[]>([]);
  const [destinations, setDestinations] = useState<TestDestination[]>([]);
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
      const [orders, dests] = await Promise.all([
        api.getUnassignedTests(searchTerm || undefined, departmentFilter !== 'ALL' ? departmentFilter : undefined),
        api.getDestinations(),
      ]);
      setUnassigned(orders);
      setDestinations(dests);

      // Prepopulate assignmentMap with suggested destination if available
      const initialMap: Record<string, string> = {};
      orders.forEach((o) => {
        if (o.suggested_destination_id) {
          initialMap[o.id] = o.suggested_destination_id;
        } else if (dests.length > 0) {
          initialMap[o.id] = dests[0].id;
        }
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

  const handleSelectDestination = (orderId: string, destId: string) => {
    setAssignmentMap((prev) => ({ ...prev, [orderId]: destId }));
  };

  const handleAssignSingle = async (order: UnassignedTestOrder) => {
    const destId = assignmentMap[order.id];
    if (!destId) {
      showToast({ type: 'warning', title: 'Select Destination', message: 'Please select a laboratory destination.' });
      return;
    }

    try {
      await api.assignTest(order.id, destId, 'Reception routing to workstation');
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
    setAssigning(true);
    try {
      const payload = selectedIds.map((id) => ({
        test_order_id: id,
        destination_id: assignmentMap[id] || destinations[0].id,
      }));
      await api.bulkAssign(payload);
      showToast({
        type: 'success',
        title: 'Bulk Assignment Complete',
        message: `${payload.length} test orders routed to workstations.`,
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
            Route pending diagnostic investigations to dedicated technician benches, analyzers, and rooms.
          </p>
        </div>

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
      </div>

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
                <th className="pb-3">Target Workstation / Room</th>
                <th className="pb-3 text-right pr-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E8E7E3]/60">
              {unassigned.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#8E8A7E]">
                    <CheckCircle2 className="w-8 h-8 text-[#2D8A39] mx-auto mb-2 opacity-80" />
                    All test orders have been assigned to laboratory workstations!
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
                        value={assignmentMap[order.id] || ''}
                        onChange={(e) => handleSelectDestination(order.id, e.target.value)}
                        className="bg-white border border-[#CAC7BE] rounded-lg px-2.5 py-1 text-xs font-semibold text-[#1B1B0E] max-w-[200px]"
                      >
                        {destinations.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name} {d.room_no ? `(Rm ${d.room_no})` : ''}
                          </option>
                        ))}
                      </select>
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
    </div>
  );
};

