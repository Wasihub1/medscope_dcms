import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Search,
  RefreshCw,
  Droplet,
  Activity,
  History,
  Tag,
  XCircle,
  PhoneCall,
  Send,
  Layers,
  Camera,
  Check,
  AlertCircle,
  FileText,
  Eye,
  MoveRight,
  FileCheck,
  Inbox,
} from 'lucide-react';
import { api } from '../../api/client';
import {
  TechnicianWorklistItem,
  WorklistSummary,
  BarcodeLabelData,
  LabRoom,
} from '../../types';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Modal } from '../../components/common/Modal';
import { SampleBarcodeModal } from '../../components/common/SampleBarcodeModal';
import { LifecycleHistoryModal } from '../../components/common/LifecycleHistoryModal';
import { ResultEntryModal } from '../../components/common/ResultEntryModal';
import { ResultReportPreviewModal } from '../../components/common/ResultReportPreviewModal';
import { WORKLIST_TILES, WorklistTileId, applyTile, isTileActive, tileCount } from './worklistTiles';
import { useRefetchOnFocus } from '../../utils/useRefetchOnFocus';

export const TechnicianWorklistPage: React.FC = () => {
  const { role, staffName, department, hasPermission } = useAuth();
  const canReassign = hasPermission('worklist.reassign');
  const canSeeAllRooms = hasPermission('worklist.view_all');
  const { showToast } = useToast();

  const [items, setItems] = useState<TechnicianWorklistItem[]>([]);
  const [summary, setSummary] = useState<WorklistSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [urgentOnly, setUrgentOnly] = useState(false);

  // Active Task for Modals
  const [activeOrder, setActiveOrder] = useState<TechnicianWorklistItem | null>(null);

  // 1. Sample Collection Modal State
  const [sampleModalOpen, setSampleModalOpen] = useState(false);
  const [sampleTypeInput, setSampleTypeInput] = useState('');
  const [sampleTimeInput, setSampleTimeInput] = useState('');
  const [tempSampleIdInput, setTempSampleIdInput] = useState('');
  const [sampleNotes, setSampleNotes] = useState('');
  const [submittingSample, setSubmittingSample] = useState(false);

  // 2. Barcode Label Modal State
  const [barcodeModalOpen, setBarcodeModalOpen] = useState(false);
  const [barcodeData, setBarcodeData] = useState<BarcodeLabelData | null>(null);

  // 3. Lifecycle History Timeline Modal State
  const [historyModalOpen, setHistoryModalOpen] = useState(false);

  // 4. Reject / Spoil Sample Modal State (Section 5.3)
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [spoilTypeInput, setSpoilTypeInput] = useState('REJECTED');
  const [rejectionReasonInput, setRejectionReasonInput] = useState('');
  const [rejectionNotesInput, setRejectionNotesInput] = useState('');
  const [submittingReject, setSubmittingReject] = useState(false);

  // 5. Patient Contact Follow-up Modal State (D15 rule)
  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [contactStatusInput, setContactStatusInput] = useState('CALLED');
  const [contactNotesInput, setContactNotesInput] = useState('');
  const [submittingContact, setSubmittingContact] = useState(false);

  // 6. Culture Stage Modal State (Section 5.5)
  const [cultureModalOpen, setCultureModalOpen] = useState(false);
  const [cultureStageInput, setCultureStageInput] = useState('INCUBATING');
  const [cultureNotesInput, setCultureNotesInput] = useState('');
  const [submittingCulture, setSubmittingCulture] = useState(false);

  // 7. Outsourced Stage Modal State (Section 5.5)
  const [outsourcedModalOpen, setOutsourcedModalOpen] = useState(false);
  const [outsourcedActionInput, setOutsourcedActionInput] = useState('SENT');
  const [outsourcedLabName, setOutsourcedLabName] = useState('National Reference Lab');
  const [outsourcedRefNo, setOutsourcedRefNo] = useState('');
  const [outsourcedNotesInput, setOutsourcedNotesInput] = useState('');
  const [submittingOutsourced, setSubmittingOutsourced] = useState(false);

  // 8. Module 13: Result Entry Modal State
  const [resultModalOpen, setResultModalOpen] = useState(false);
  const [submittingD15Refund, setSubmittingD15Refund] = useState(false);

  // 9. Prompt 10E Part 9: report preview of a saved result
  const [previewOrderId, setPreviewOrderId] = useState<number | null>(null);
  // Prompt 10F (F2): the result just saved. Shown above the grid with a Preview action, because a
  // submitted result can leave the active tab (e.g. Sample Pending -> Completed) right after save.
  const [lastSaved, setLastSaved] = useState<{ id: number; testName: string; status: 'DRAFT' | 'ENTERED' } | null>(null);

  // 10. Prompt 10E Part 7: reassign an order to another room (worklist.reassign)
  const [rooms, setRooms] = useState<LabRoom[]>([]);
  const [reassignModalOpen, setReassignModalOpen] = useState(false);
  const [reassignRoom, setReassignRoom] = useState('');
  const [reassignReason, setReassignReason] = useState('');
  const [submittingReassign, setSubmittingReassign] = useState(false);

  useEffect(() => {
    if (!canReassign) return;
    api.getRooms().then(setRooms).catch(() => setRooms([]));
  }, [canReassign]);

  // Prompt 10E Part 8: Bento tiles are filters (same effect as the status tabs)
  const handleTileClick = (id: WorklistTileId) => {
    const next = applyTile(id, { statusFilter, urgentOnly });
    setStatusFilter(next.statusFilter);
    setUrgentOnly(next.urgentOnly);
  };

  const handleOpenReassign = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    setReassignRoom('');
    setReassignReason('');
    setReassignModalOpen(true);
  };

  const handleSubmitReassign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrder || !reassignRoom) return;
    setSubmittingReassign(true);
    try {
      const res = await api.reassignRoom(activeOrder.test_order_id, reassignRoom, reassignReason.trim() || undefined);
      showToast({
        type: 'success',
        title: 'Order Reassigned',
        message: `Order #${activeOrder.test_order_id} moved to ${res.lab_section_label || reassignRoom}.`,
      });
      setReassignModalOpen(false);
      fetchData();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Reassign Failed', message: err.message || 'Could not move the order.' });
    } finally {
      setSubmittingReassign(false);
    }
  };

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const [listRes, summaryRes] = await Promise.all([
        api.getWorklist({
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
          urgent_only: urgentOnly ? true : undefined,
          q: searchQuery.trim() || undefined,
        }),
        api.getWorklistSummary(),
      ]);
      setItems(listRes);
      setSummary(summaryRes);
    } catch (err: any) {
      console.error('Failed to load technician worklist:', err);
      showToast({
        type: 'error',
        title: 'Worklist Load Error',
        message: err.message || 'Could not retrieve laboratory tasks.',
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, urgentOnly, searchQuery, showToast]);

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [fetchData]);

  // Prompt 10F: refetch when the user returns to the window (e.g. an order was moved to this room)
  useRefetchOnFocus(fetchData);

  const handleResultSaved = (savedStatus?: 'DRAFT' | 'ENTERED') => {
    if (activeOrder) {
      setLastSaved({ id: activeOrder.test_order_id, testName: activeOrder.test_name, status: savedStatus || 'ENTERED' });
    }
    fetchData();
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  // Open Sample Collection Modal
  const handleOpenSampleModal = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    setSampleTypeInput(order.sample_type || 'Blood');
    const now = new Date();
    const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    setSampleTimeInput(localIso);
    setTempSampleIdInput(order.temp_sample_id || '');
    setSampleNotes('');
    setSampleModalOpen(true);
  };

  // Submit Sample Taken Event
  const handleSubmitSample = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrder) return;
    setSubmittingSample(true);
    try {
      let isoDate: string | undefined = undefined;
      if (sampleTimeInput) {
        isoDate = new Date(sampleTimeInput).toISOString();
      }
      await api.recordSampleTaken(activeOrder.test_order_id, {
        collected_at: isoDate,
        sample_type: sampleTypeInput || undefined,
        temp_sample_id: tempSampleIdInput || undefined,
        notes: sampleNotes || undefined,
      });
      showToast({
        type: 'success',
        title: 'Specimen Recorded',
        message: `Sample Taken recorded for Order #${activeOrder.test_order_id}. Invoice line locked.`,
      });
      setSampleModalOpen(false);
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Sample Action Failed',
        message: err.message || 'Could not record specimen collection event.',
      });
    } finally {
      setSubmittingSample(false);
    }
  };

  // Open Barcode Label Modal
  const handleOpenBarcodeModal = async (order: TechnicianWorklistItem) => {
    try {
      const data = await api.getBarcodeLabel(order.test_order_id);
      setBarcodeData(data);
      setBarcodeModalOpen(true);
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Barcode Error',
        message: err.message || 'Failed to generate specimen barcode.',
      });
    }
  };

  // Open History Timeline Modal
  const handleOpenHistoryModal = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    setHistoryModalOpen(true);
  };

  // Open Reject / Spoil Modal
  const handleOpenRejectModal = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    setSpoilTypeInput('REJECTED');
    setRejectionReasonInput('Hemolyzed specimen unsuitable for analysis');
    setRejectionNotesInput('');
    setRejectModalOpen(true);
  };

  // Submit Reject / Spoil Sample
  const handleSubmitReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrder) return;
    if (!rejectionReasonInput.trim()) {
      showToast({ type: 'warning', title: 'Reason Required', message: 'Rejection reason is mandatory.' });
      return;
    }
    setSubmittingReject(true);
    try {
      await api.rejectSample(activeOrder.test_order_id, {
        rejection_reason: rejectionReasonInput.trim(),
        spoil_type: spoilTypeInput,
        notes: rejectionNotesInput.trim() || undefined,
      });
      showToast({
        type: 'success',
        title: 'Specimen Rejected',
        message: `Specimen marked ${spoilTypeInput}. Patient flagged for follow-up call.`,
      });
      setRejectModalOpen(false);
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Rejection Failed',
        message: err.message || 'Failed to record specimen rejection.',
      });
    } finally {
      setSubmittingReject(false);
    }
  };

  // Open Patient Contact Follow-up Modal
  const handleOpenContactModal = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    setContactStatusInput('CALLED');
    setContactNotesInput('');
    setContactModalOpen(true);
  };

  // Submit Patient Contact Follow-up
  const handleSubmitContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrder) return;
    setSubmittingContact(true);
    try {
      await api.recordPatientContact(activeOrder.test_order_id, {
        contact_status: contactStatusInput,
        notes: contactNotesInput.trim() || undefined,
      });
      showToast({
        type: 'success',
        title: 'Contact Logged',
        message: `Patient contact updated to ${contactStatusInput}.`,
      });
      setContactModalOpen(false);
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: err.message || 'Failed to record patient contact.',
      });
    } finally {
      setSubmittingContact(false);
    }
  };

  // Imaging Performed Handler
  const handleImagingPerformed = async (testOrderId: number) => {
    try {
      await api.recordImagingPerformed(testOrderId, {});
      showToast({
        type: 'success',
        title: 'Scan Performed',
        message: 'Imaging examination recorded. Order routed to visiting physician queue.',
      });
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Action Failed',
        message: err.message || 'Failed to record scan.',
      });
    }
  };

  // Open Culture Stage Modal
  const handleOpenCultureModal = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    const nextStage = order.culture_stage === 'INCUBATING' ? 'PRELIMINARY' : order.culture_stage === 'PRELIMINARY' ? 'FINAL' : 'INCUBATING';
    setCultureStageInput(nextStage);
    setCultureNotesInput('');
    setCultureModalOpen(true);
  };

  // Submit Culture Stage
  const handleSubmitCulture = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrder) return;
    setSubmittingCulture(true);
    try {
      await api.recordCultureStage(activeOrder.test_order_id, {
        stage: cultureStageInput,
        notes: cultureNotesInput.trim() || undefined,
      });
      showToast({
        type: 'success',
        title: 'Culture Stage Updated',
        message: `Examination moved to ${cultureStageInput} stage.`,
      });
      setCultureModalOpen(false);
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Stage Update Failed',
        message: err.message || 'Failed to update culture stage.',
      });
    } finally {
      setSubmittingCulture(false);
    }
  };

  // Open Outsourced Stage Modal
  const handleOpenOutsourcedModal = (order: TechnicianWorklistItem, defaultAction: 'SENT' | 'RECEIVED') => {
    setActiveOrder(order);
    setOutsourcedActionInput(defaultAction);
    setOutsourcedLabName(order.outsourced_lab_name || 'National Reference Lab');
    setOutsourcedRefNo(order.outsourced_ref_no || '');
    setOutsourcedNotesInput('');
    setOutsourcedModalOpen(true);
  };

  // Submit Outsourced Stage
  const handleSubmitOutsourced = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrder) return;
    setSubmittingOutsourced(true);
    try {
      await api.recordOutsourcedStage(activeOrder.test_order_id, {
        action: outsourcedActionInput,
        lab_name: outsourcedLabName || undefined,
        ref_no: outsourcedRefNo || undefined,
        notes: outsourcedNotesInput.trim() || undefined,
      });
      showToast({
        type: 'success',
        title: 'Outsourced Status Updated',
        message: `Specimen marked as ${outsourcedActionInput} for referral laboratory.`,
      });
      setOutsourcedModalOpen(false);
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: err.message || 'Failed to update outsourced record.',
      });
    } finally {
      setSubmittingOutsourced(false);
    }
  };

  // Transition Task Status (Enforces Prompt 06 Invariants)
  const handleStatusChange = async (testOrderId: number, newStatus: string) => {
    try {
      await api.updateWorklistStatus(testOrderId, { status: newStatus });
      showToast({
        type: 'success',
        title: 'Status Updated',
        message: `Task #${testOrderId} moved to ${newStatus.replace('_', ' ')}.`,
      });
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Update Prohibited',
        message: err.message || 'Failed to update order status.',
      });
    }
  };

  // Module 13: Open Result Entry Modal
  const handleOpenResultModal = (order: TechnicianWorklistItem) => {
    setActiveOrder(order);
    setResultModalOpen(true);
  };

  // FIX 4: Submit D15 Refund Request for Rejected/Spoiled Specimen
  const handleSubmitD15Refund = async (order: TechnicianWorklistItem) => {
    setSubmittingD15Refund(true);
    try {
      await api.submitD15RefundRequest(
        order.test_order_id,
        order.patient_contact_notes || order.rejection_reason || 'Specimen spoiled/rejected'
      );
      showToast({
        type: 'success',
        title: 'D15 Refund Requested',
        message: `Refund request submitted to Admin for Order #${order.test_order_id}.`,
      });
      fetchData();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Refund Request Failed',
        message: err.message || 'Could not submit D15 refund request.',
      });
    } finally {
      setSubmittingD15Refund(false);
    }
  };

  const statusTabs = [
    { id: 'ALL', label: 'All Tasks', count: summary?.total_assigned || 0 },
    { id: 'SAMPLE_PENDING', label: 'Sample Pending', count: summary?.sample_pending_count || 0 },
    { id: 'IN_PROGRESS', label: 'In Progress', count: summary?.in_progress_count || 0 },
    { id: 'AWAITING_DOCTOR', label: 'Doctor Queue', count: summary?.awaiting_doctor_count || 0 },
    { id: 'REJECTED', label: 'Rejected / Spoiled', count: summary?.rejected_count || 0 },
    { id: 'CULTURE', label: 'Culture & Sensitivity', count: summary?.culture_count || 0 },
    { id: 'IMAGING', label: 'Imaging / USG', count: summary?.imaging_count || 0 },
    { id: 'OUTSOURCED', label: 'Outsourced Labs', count: summary?.outsourced_count || 0 },
    { id: 'LATE', label: 'Late', count: summary?.late_count || 0 },
    { id: 'READY', label: 'Ready Reports', count: summary?.ready_count || 0 },
    { id: 'COMPLETED', label: 'Completed', count: summary?.completed_count || 0 },
  ];

  // Prompt 10E Part 8: visual style per tile (brand look kept)
  const tileStyle: Record<WorklistTileId, { text: string; icon: React.ReactNode }> = {
    ALL: { text: 'text-[#1B1B0E]', icon: <Activity className="w-3.5 h-3.5 text-[#525333]" /> },
    URGENT: { text: 'text-[#B05B20]', icon: <span className="w-2 h-2 rounded-full bg-[#CF8852] animate-pulse" /> },
    SAMPLE_PENDING: { text: 'text-[#8B6B23]', icon: <Droplet className="w-3.5 h-3.5 text-[#8B6B23]" /> },
    IN_PROGRESS: { text: 'text-[#2B547E]', icon: <FlaskConical className="w-3.5 h-3.5 text-[#2B547E]" /> },
    AWAITING_DOCTOR: { text: 'text-amber-800', icon: <Clock className="w-3.5 h-3.5 text-amber-700" /> },
    REJECTED: { text: 'text-rose-700', icon: <XCircle className="w-3.5 h-3.5 text-rose-600" /> },
    LATE: { text: 'text-rose-700', icon: <AlertTriangle className="w-3.5 h-3.5 text-rose-600" /> },
    READY: { text: 'text-emerald-800', icon: <FileCheck className="w-3.5 h-3.5 text-emerald-700" /> },
    UNASSIGNED: { text: 'text-[#54524A]', icon: <Inbox className="w-3.5 h-3.5 text-[#54524A]" /> },
    COMPLETED: { text: 'text-emerald-700', icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> },
  };
  const visibleTiles = WORKLIST_TILES.filter((t) => t.id !== 'UNASSIGNED' || canSeeAllRooms);

  return (
    <div className="space-y-6">
      {/* Header & Workbench Identity */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-[#525333] text-white rounded-xl shadow-xs">
              <FlaskConical className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#1B1B0E] flex items-center gap-2">
                Technician Worklist & Specimen Lifecycle
                <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-[#E8E7E3] text-[#525333] border border-[#CAC7BE]">
                  {summary?.department || department || 'Laboratory Workstation'}
                </span>
              </h1>
              <p className="text-xs text-[#6D6A60]">
                Logged in as <strong className="text-[#1B1B0E]">{staffName}</strong> ({role}). Strict specimen tracking & financial-data isolation.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold bg-white text-[#1B1B0E] border border-[#CAC7BE] rounded-xl hover:bg-[#F4F3F0] transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#525333] ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh Tasks</span>
          </button>
        </div>
      </div>

      {/* KPI Bento Grid Metric Tiles — Prompt 10E Part 8: each tile is a filter (click again to clear) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3" role="group" aria-label="Worklist filters">
        {visibleTiles.map((tile) => {
          const active = isTileActive(tile.id, { statusFilter, urgentOnly });
          const count = tileCount(summary as unknown as Record<string, unknown>, tile.id);
          const lateAlert = tile.id === 'LATE' && count > 0 && !active;
          return (
            <button
              key={tile.id}
              type="button"
              onClick={() => handleTileClick(tile.id)}
              aria-pressed={active}
              data-testid={`worklist-tile-${tile.id}`}
              title={active ? `Showing: ${tile.label} (click to clear)` : `Show ${tile.label}`}
              className={`text-left p-3 rounded-2xl border shadow-2xs transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852] focus-visible:ring-offset-1 ${
                active
                  ? 'bg-[#525333] border-[#3E3F27] shadow-xs'
                  : lateAlert
                  ? 'bg-[#FDF2F2] border-rose-300 hover:border-rose-400'
                  : 'bg-[#FAF9F6] border-[#DCDAD4] hover:border-[#A9A68F] hover:bg-[#F4F3F0]'
              }`}
            >
              <span className={`text-[10px] font-semibold block ${active ? 'text-white/80' : tileStyle[tile.id].text}`}>
                {tile.label}
              </span>
              <span className="flex items-baseline justify-between mt-1">
                <span className={`text-xl font-bold ${active ? 'text-white' : tileStyle[tile.id].text}`}>{count}</span>
                {tileStyle[tile.id].icon}
              </span>
            </button>
          );
        })}
      </div>

      {/* Filter Toolbar & Status Tabs */}
      <div className="bg-[#FAF9F6] p-3.5 rounded-2xl border border-[#DCDAD4] space-y-3 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Status Tab Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
            {statusTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  statusFilter === tab.id
                    ? 'bg-[#525333] text-white shadow-xs'
                    : 'bg-[#F4F3F0] text-[#54524A] hover:bg-[#E8E7E3]'
                }`}
              >
                {tab.label}
                <span className={`ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] ${
                  statusFilter === tab.id ? 'bg-white/20 text-white' : 'bg-[#DCDAD4] text-[#1B1B0E]'
                }`}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          {/* Urgent Filter Toggle */}
          <button
            onClick={() => setUrgentOnly((prev) => !prev)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
              urgentOnly
                ? 'bg-[#CF8852] text-white border-[#B05B20] shadow-xs'
                : 'bg-white text-[#54524A] border-[#CAC7BE] hover:bg-[#F4F3F0]'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Urgent STAT Only</span>
          </button>
        </div>

        {/* Search Bar (Barcode, Sample Code, MRN, Name) */}
        <div className="relative">
          <Search className="w-4 h-4 text-[#8E8A7E] absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Scan barcode, enter sample code (SMP-...), patient name, MRN, or test name..."
            className="w-full pl-10 pr-4 py-2 bg-white text-xs text-[#1B1B0E] border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333] focus:ring-1 focus:ring-[#525333] placeholder:text-[#8E8A7E]"
          />
        </div>
      </div>

      {/* Main Worklist Table */}
      <div className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl overflow-hidden shadow-2xs">
        {lastSaved && (
          <div
            role="status"
            data-testid="last-saved-result"
            className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-xs border-b border-[#DCDAD4] bg-[#EEF3F8] text-[#2B547E]"
          >
            <span>
              Result saved{lastSaved.status === 'DRAFT' ? ' as DRAFT' : ' (submitted)'} for order #{lastSaved.id}: {lastSaved.testName}
            </span>
            <span className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPreviewOrderId(lastSaved.id)}
                data-testid={`last-saved-preview-${lastSaved.id}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-white text-[#2B547E] border border-[#B9C9DA] rounded-lg hover:bg-white/70 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
              >
                <Eye className="w-3.5 h-3.5" />
                Preview Report
              </button>
              <button
                type="button"
                onClick={() => setLastSaved(null)}
                aria-label="Dismiss saved-result notice"
                className="px-2 py-1 text-[11px] text-[#54524A] hover:underline cursor-pointer"
              >
                Dismiss
              </button>
            </span>
          </div>
        )}
        {loading ? (
          <div className="py-20 text-center">
            <RefreshCw className="w-7 h-7 text-[#525333] animate-spin mx-auto mb-3" />
            <p className="text-xs text-[#6D6A60]">Loading laboratory worklist queue...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center">
            <div className="w-12 h-12 rounded-full bg-[#E8E7E3] text-[#525333] flex items-center justify-center mx-auto mb-3">
              <FlaskConical className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-[#1B1B0E]">
              {statusFilter === 'READY' ? 'No Ready Reports Yet' : 'No Laboratory Tasks in Queue'}
            </h3>
            <p className="text-xs text-[#6D6A60] mt-1 max-w-sm mx-auto">
              {statusFilter === 'READY'
                ? 'A result appears here as soon as it is submitted (Submit Results). Drafts are not Ready. Click the Ready Reports tile again to clear the filter.'
                : 'There are no laboratory orders matching your selected filters. Switch filters or inspect other queues.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#F4F3F0] text-[#54524A] font-semibold border-b border-[#DCDAD4]">
                  <th className="py-3 px-4">Priority / Order</th>
                  <th className="py-3 px-4">Patient Information</th>
                  <th className="py-3 px-4">Investigation & Specimen</th>
                  <th className="py-3 px-4">Turnaround Clocks (TAT)</th>
                  <th className="py-3 px-4">Workflow Status</th>
                  <th className="py-3 px-4 text-right">Operational Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E8E7E3]">
                {items.map((order) => {
                  const hasSample = order.sample_status === 'COLLECTED';
                  const isRejected = order.status === 'REJECTED' || order.status === 'SPOILED';
                  // Prompt 10E Part 2: one backend rule decides imaging / sample requirement
                  const isImaging =
                    order.is_imaging ??
                    (order.requires_doctor || order.report_template === 'NARRATIVE');
                  const needsSample = order.requires_sample ?? !isImaging;
                  const canWork = hasSample || !needsSample;
                  const isCulture = order.report_template === 'CULTURE_SENSITIVITY';

                  return (
                    <tr
                      key={order.test_order_id}
                      className={`hover:bg-[#F9F8F5] transition-colors ${
                        order.is_late
                          ? 'bg-[#FFF8F8]'
                          : isRejected
                          ? 'bg-[#FFF5F5]'
                          : (order.urgent && order.status !== 'COMPLETED')
                          ? 'bg-[#FFFAF5]'
                          : ''
                      }`}
                    >
                      {/* Priority & Order ID */}
                      <td className="py-3.5 px-4 align-top">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-[#1B1B0E]">
                              #{order.test_order_id}
                            </span>
                            <span className="text-[10px] text-[#6D6A60]">
                              (Inv: {order.invoice_no})
                            </span>
                          </div>

                          {/* FIX 2: Stat Urgent badge stays until Test Status is COMPLETED */}
                          {order.urgent && order.status !== 'COMPLETED' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#F9E2D2] text-[#B05B20] border border-[#E9BD9E]">
                              <span className="w-1.5 h-1.5 rounded-full bg-[#CF8852] animate-ping" />
                              STAT URGENT
                            </span>
                          )}

                          {order.is_late && (
                            <div
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FEE2E2] text-[#B91C1C] border border-[#FCA5A5]"
                              title={order.late_reason || 'Elapsed time exceeded turnaround limit'}
                            >
                              <AlertTriangle className="w-3 h-3 text-rose-600 shrink-0" />
                              LATE
                            </div>
                          )}

                          {/* FIX 1: Line Lock badge REMOVED from Technician UI as required */}

                          {/* Module 13 Result Status Indicator */}
                          {order.result_status && (
                            <span className="inline-block text-[9px] text-[#525333] bg-[#E8E7E3] px-1.5 py-0.5 rounded font-semibold">
                              Result: {order.result_status}
                            </span>
                          )}

                          {/* FIX 4 D15 Refund Status Badge */}
                          {order.d15_refund_status && (
                            <span
                              className={`inline-block text-[9px] px-1.5 py-0.5 rounded font-semibold border ${
                                order.d15_refund_status === 'APPROVED'
                                  ? 'bg-blue-50 text-blue-800 border-blue-200'
                                  : order.d15_refund_status === 'DISBURSED'
                                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                  : order.d15_refund_status === 'REJECTED'
                                  ? 'bg-rose-50 text-rose-800 border-rose-200'
                                  : 'bg-amber-50 text-amber-800 border-amber-200'
                              }`}
                            >
                              D15: {order.d15_refund_status.replace(/_/g, ' ')}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Patient Demographics (NO FINANCIAL DATA!) */}
                      <td className="py-3.5 px-4 align-top">
                        <div className="space-y-0.5">
                          <span className="font-semibold text-[#1B1B0E] block">
                            {order.patient_name}
                          </span>
                          <div className="text-[11px] text-[#6D6A60] flex items-center gap-2">
                            <span className="font-mono">{order.patient_code}</span>
                            <span>•</span>
                            <span>{order.patient_gender || 'Unknown'}</span>
                            {order.patient_age && (
                              <>
                                <span>•</span>
                                <span>{order.patient_age}</span>
                              </>
                            )}
                          </div>
                          {order.patient_phone && (
                            <span className="text-[10px] text-[#8E8A7E] font-mono block">
                              {order.patient_phone}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Investigation & Specimen */}
                      <td className="py-3.5 px-4 align-top">
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-[#1B1B0E]">
                              {order.test_name}
                            </span>
                            <span className="text-[10px] px-1.5 py-0.2 bg-[#E8E7E3] text-[#54524A] rounded font-mono">
                              {order.test_code}
                            </span>
                          </div>

                          <div className="text-[11px] text-[#6D6A60] flex items-center gap-2">
                            <span className="px-1.5 py-0.2 bg-[#F4F3F0] rounded border border-[#DCDAD4] text-[10px]">
                              {order.department}
                            </span>
                            {order.sample_type && !isImaging && (
                              <span className="flex items-center gap-1 text-[11px] text-[#525333]">
                                <Droplet className="w-3 h-3" />
                                {order.sample_type}
                              </span>
                            )}
                          </div>

                          {/* Specimen Status & Barcode */}
                          {isRejected ? (
                            <div className="space-y-1">
                              <div className="flex items-center gap-1 text-[10px] font-bold text-rose-800 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                                <XCircle className="w-3 h-3 text-rose-600 shrink-0" />
                                <span>{order.status}: {order.rejection_reason || 'Specimen spoiled'}</span>
                              </div>
                              {order.patient_contact_status && (
                                <span className="text-[10px] text-amber-800 font-semibold block">
                                  📞 Contact: {order.patient_contact_status.replace('_', ' ')}
                                </span>
                              )}
                            </div>
                          ) : hasSample ? (
                            <div className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              <Check className="w-3 h-3 text-emerald-600" />
                              <span>{order.sample_code}</span>
                              {order.temp_sample_id && (
                                <span className="text-[9px] text-[#8E8A7E]">
                                  (Offline: {order.temp_sample_id})
                                </span>
                              )}
                            </div>
                          ) : isImaging ? (
                            <div className="flex items-center gap-1.5 text-[10px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                              <Camera className="w-3 h-3" />
                              <span>Imaging Procedure (No Biological Specimen)</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 text-[10px] text-[#8B6B23] bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                              <Clock className="w-3 h-3" />
                              <span>Specimen Pending Collection</span>
                            </div>
                          )}

                          {/* Culture Stage Indicator */}
                          {order.culture_stage && (
                            <div className="text-[10px] font-semibold text-purple-800 bg-purple-50 px-2 py-0.5 rounded border border-purple-200 inline-block">
                              Stage: {order.culture_stage}
                            </div>
                          )}

                          {/* Outsourced Lab Indicator */}
                          {order.outsourced_status && (
                            <div className="text-[10px] font-semibold text-blue-800 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 inline-block">
                              Referral Lab: {order.outsourced_status} ({order.outsourced_lab_name || 'Outside Lab'})
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Turnaround Clocks */}
                      <td className="py-3.5 px-4 align-top">
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="text-[#6D6A60]">Target TAT:</span>
                            <span className="font-semibold text-[#1B1B0E]">{order.tat_display}</span>
                          </div>

                          {/* Patient Clock */}
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="text-[#6D6A60]">Patient Clock:</span>
                            <span
                              className={`font-mono font-semibold ${
                                order.patient_clock_elapsed_mins >
                                (order.turnaround_hours ? order.turnaround_hours * 60 : 999999)
                                  ? 'text-rose-600'
                                  : 'text-[#1B1B0E]'
                              }`}
                            >
                              {order.patient_clock_display}
                            </span>
                          </div>

                          {/* Lab Clock */}
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="text-[#6D6A60]">Lab Clock:</span>
                            <span
                              className={`font-mono font-semibold ${
                                order.lab_clock_elapsed_mins &&
                                order.turnaround_hours &&
                                order.lab_clock_elapsed_mins > order.turnaround_hours * 60
                                  ? 'text-rose-600'
                                  : order.lab_clock_display
                                  ? 'text-[#1B1B0E]'
                                  : 'text-[#8E8A7E]'
                              }`}
                            >
                              {order.lab_clock_display || (isImaging ? 'At Scan' : 'Not Collected')}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Workflow Status */}
                      <td className="py-3.5 px-4 align-top">
                        <div className="space-y-1">
                          <span
                            className={`inline-block px-2.5 py-1 rounded-xl text-[11px] font-bold ${
                              order.status === 'COMPLETED'
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : order.status === 'IN_PROGRESS'
                                ? 'bg-blue-100 text-blue-800 border border-blue-300'
                                : order.status === 'AWAITING_DOCTOR'
                                ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                : isRejected
                                ? 'bg-rose-100 text-rose-800 border border-rose-300'
                                : 'bg-stone-100 text-stone-800 border border-stone-300'
                            }`}
                          >
                            {order.status.replace('_', ' ')}
                          </span>

                          {order.lab_section_label && (
                            <span className="text-[10px] text-[#525333] font-semibold block truncate" data-testid={`order-room-${order.test_order_id}`}>
                              Room: {order.lab_section_label}
                            </span>
                          )}
                          {order.assigned_to_name && (
                            <span className="text-[10px] text-[#6D6A60] block truncate">
                              Worked by: {order.assigned_to_name}
                            </span>
                          )}
                          {order.report_ready && (
                            <span className="inline-block text-[10px] font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              Report Ready
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Operational Actions */}
                      <td className="py-3.5 px-4 align-top text-right">
                        <div className="flex flex-col items-end gap-1.5">
                          {/* 1. Barcode Label Trigger (Whenever sample is collected) */}
                          {hasSample && (
                            <button
                              onClick={() => handleOpenBarcodeModal(order)}
                              data-testid={`print-barcode-${order.test_order_id}`}
                              className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-white text-[#525333] border border-[#CAC7BE] rounded-lg hover:bg-[#F4F3F0] transition-colors shadow-2xs cursor-pointer"
                              title="Print 50mm x 30mm specimen tube barcode label"
                            >
                              <Tag className="w-3.5 h-3.5" />
                              <span>Barcode</span>
                            </button>
                          )}

                          {/* 2. REJECTED / SPOILED ORDER ACTIONS */}
                          {isRejected ? (
                            <div className="flex flex-col items-end gap-1">
                              <div className="flex items-center gap-1">
                                {order.patient_followup_required || order.patient_contact_status === 'PENDING_CALL' ? (
                                  <button
                                    onClick={() => handleOpenContactModal(order)}
                                    data-testid={`contact-patient-${order.test_order_id}`}
                                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold bg-[#CF8852] text-white rounded-lg hover:bg-[#B7703B] transition-colors shadow-2xs cursor-pointer"
                                  >
                                    <PhoneCall className="w-3 h-3" />
                                    <span>Call Patient</span>
                                  </button>
                                ) : (
                                  <button
                                    onClick={() => handleOpenContactModal(order)}
                                    className="px-2 py-0.5 text-[10px] text-[#54524A] bg-white border border-[#CAC7BE] rounded hover:bg-gray-50 cursor-pointer"
                                  >
                                    Edit Call Log
                                  </button>
                                )}
                              </div>

                              {/* FIX 4: Explicit D15 Refund Request Action */}
                              {!order.d15_refund_status ? (
                                <button
                                  onClick={() => handleSubmitD15Refund(order)}
                                  disabled={submittingD15Refund}
                                  data-testid={`submit-d15-refund-${order.test_order_id}`}
                                  className="flex items-center gap-1 px-2 py-1 text-[11px] font-bold text-rose-700 bg-white border border-rose-300 rounded-lg hover:bg-rose-50 transition-colors shadow-2xs cursor-pointer"
                                  title="Submit D15 Not Performed refund request to Admin"
                                >
                                  <AlertCircle className="w-3 h-3 text-rose-600" />
                                  <span>Submit D15 Refund</span>
                                </button>
                              ) : null}
                            </div>
                          ) : isImaging ? (
                            /* 3. IMAGING / RADIOLOGY WORKFLOW (Section 5.5 & Module 13) */
                            <div className="flex flex-col items-end gap-1">
                              <div className="flex items-center gap-1">
                                {order.status !== 'AWAITING_DOCTOR' && order.status !== 'COMPLETED' && (
                                  <button
                                    onClick={() => handleImagingPerformed(order.test_order_id)}
                                    data-testid={`perform-imaging-${order.test_order_id}`}
                                    className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors shadow-2xs cursor-pointer"
                                    title="Mark examination performed and route to doctor"
                                  >
                                    <Camera className="w-3 h-3" />
                                    <span>Perform Scan</span>
                                  </button>
                                )}

                                {/* Module 13: Enter/Edit Imaging Report Findings */}
                                <button
                                  onClick={() => handleOpenResultModal(order)}
                                  data-testid={`enter-results-${order.test_order_id}`}
                                  className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold bg-[#525333] text-white rounded-lg hover:bg-[#3E3F27] transition-colors shadow-2xs cursor-pointer"
                                  title="Enter examination findings and impression"
                                >
                                  <FileText className="w-3 h-3" />
                                  <span>{order.has_result || order.result_status ? 'Edit Report' : 'Enter Report'}</span>
                                </button>
                              </div>

                              {order.status === 'AWAITING_DOCTOR' && (
                                <span className="text-[10px] text-amber-800 font-semibold bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                  Doctor Queue
                                </span>
                              )}
                            </div>
                          ) : (
                            /* 4. STANDARD LABORATORY SPECIMEN WORKFLOW (Module 12 & Module 13) */
                            <div className="space-y-1">
                              {/* Before Sample Collection: ONLY allow Sample Taken! */}
                              {!hasSample && needsSample && order.status !== 'COMPLETED' && (
                                <button
                                  onClick={() => handleOpenSampleModal(order)}
                                  data-testid={`sample-taken-${order.test_order_id}`}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3E3F27] transition-all shadow-xs cursor-pointer"
                                >
                                  <Droplet className="w-3.5 h-3.5" />
                                  <span>Sample Taken</span>
                                </button>
                              )}
                              {/* Prompt 10F (F4): results and Complete stay locked until Sample Taken */}
                              {!hasSample && needsSample && order.status !== 'COMPLETED' && (
                                <span className="block text-[10px] text-[#8B6B23] text-right" data-testid={`sample-first-hint-${order.test_order_id}`}>
                                  Take the sample before entering results
                                </span>
                              )}

                              {/* After Sample Collection: Allow Operational Execution & Module 13 Result Entry */}
                              {canWork && order.status !== 'COMPLETED' && (
                                <div className="flex flex-col items-end gap-1">
                                  <div className="flex items-center gap-1">
                                    {/* Module 13: Enter Results Button */}
                                    <button
                                      onClick={() => handleOpenResultModal(order)}
                                      data-testid={`enter-results-${order.test_order_id}`}
                                      className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold bg-[#525333] text-white rounded-lg hover:bg-[#3E3F27] transition-colors shadow-2xs cursor-pointer"
                                      title="Enter test investigation values and flags"
                                    >
                                      <FileText className="w-3 h-3" />
                                      <span>{order.has_result || order.result_status ? 'Edit Results' : 'Enter Results'}</span>
                                    </button>

                                    {/* Culture Stages */}
                                    {isCulture && (
                                      <button
                                        onClick={() => handleOpenCultureModal(order)}
                                        data-testid={`culture-stage-${order.test_order_id}`}
                                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold bg-purple-50 text-purple-800 border border-purple-200 rounded-lg hover:bg-purple-100 cursor-pointer"
                                      >
                                        <Layers className="w-3 h-3" />
                                        <span>Stage</span>
                                      </button>
                                    )}

                                    {/* Outsourced Dispatch / Receive */}
                                    {order.outsourced_status === null ? (
                                      <button
                                        onClick={() => handleOpenOutsourcedModal(order, 'SENT')}
                                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200 rounded-lg hover:bg-blue-100 cursor-pointer"
                                      >
                                        <Send className="w-3 h-3" />
                                        <span>Dispatch</span>
                                      </button>
                                    ) : order.outsourced_status === 'SENT' ? (
                                      <button
                                        onClick={() => handleOpenOutsourcedModal(order, 'RECEIVED')}
                                        className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg hover:bg-emerald-100 cursor-pointer"
                                      >
                                        <Check className="w-3 h-3" />
                                        <span>Receive</span>
                                      </button>
                                    ) : null}

                                    {/* Reject Sample Option (only when a sample exists) */}
                                    {hasSample && (
                                    <button
                                      onClick={() => handleOpenRejectModal(order)}
                                      data-testid={`reject-sample-${order.test_order_id}`}
                                      className="px-2 py-1 text-[11px] font-semibold text-rose-700 bg-white border border-rose-300 rounded-lg hover:bg-rose-50 cursor-pointer"
                                      title="Mark specimen rejected / spoiled"
                                    >
                                      Reject
                                    </button>
                                    )}

                                    {/* Complete Button (Only valid when sample collected) */}
                                    <button
                                      onClick={() => handleStatusChange(order.test_order_id, 'COMPLETED')}
                                      data-testid={`complete-task-${order.test_order_id}`}
                                      className="px-2.5 py-1 text-[11px] font-semibold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors shadow-2xs cursor-pointer"
                                      title="Mark test execution completed"
                                    >
                                      Complete
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Prompt 10E Part 9: Preview Report once a result is saved */}
                          {(order.has_result || order.result_status) && (
                            <button
                              onClick={() => setPreviewOrderId(order.test_order_id)}
                              data-testid={`preview-report-${order.test_order_id}`}
                              className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold bg-white text-[#2B547E] border border-[#B9C9DA] rounded-lg hover:bg-[#EEF3F8] transition-colors shadow-2xs cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
                              title="Preview the report of the saved result"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              <span>Preview Report</span>
                            </button>
                          )}

                          {/* Prompt 10E Part 7: move to another room (worklist.reassign), until COMPLETED */}
                          {canReassign && order.status !== 'COMPLETED' && order.status !== 'CANCELLED' && !isRejected && order.outcome !== 'NOT_PERFORMED' && (
                            <button
                              onClick={() => handleOpenReassign(order)}
                              data-testid={`reassign-room-${order.test_order_id}`}
                              className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold text-[#54524A] bg-white border border-[#CAC7BE] rounded-lg hover:bg-[#F4F3F0] cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]"
                              title="Move this order to another lab room"
                            >
                              <MoveRight className="w-3 h-3" />
                              <span>Reassign Room</span>
                            </button>
                          )}

                          {/* 5. View Lifecycle History Timeline */}
                          <button
                            onClick={() => handleOpenHistoryModal(order)}
                            data-testid={`view-history-${order.test_order_id}`}
                            className="flex items-center gap-1 text-[10px] text-[#6D6A60] hover:text-[#1B1B0E] hover:underline cursor-pointer pt-0.5"
                          >
                            <History className="w-3 h-3" />
                            <span>Timeline</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL 1: Quick & Full Route Specimen Collection Modal */}
      <Modal
        isOpen={sampleModalOpen}
        onClose={() => setSampleModalOpen(false)}
        title="Record Specimen Collection"
      >
        {activeOrder && (
          <form onSubmit={handleSubmitSample} className="space-y-4">
            <div className="p-3 bg-[#F4F3F0] rounded-xl border border-[#DCDAD4] space-y-1">
              <span className="text-xs font-semibold text-[#1B1B0E] block">
                Order #{activeOrder.test_order_id}: {activeOrder.test_name}
              </span>
              <span className="text-xs text-[#6D6A60] block">
                Patient: <strong className="text-[#1B1B0E]">{activeOrder.patient_name}</strong> ({activeOrder.patient_code})
              </span>
              <span className="text-[11px] text-[#525333] block">
                Department: {activeOrder.department}
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Specimen / Sample Type
              </label>
              <input
                type="text"
                value={sampleTypeInput}
                onChange={(e) => setSampleTypeInput(e.target.value)}
                placeholder="e.g. Whole Blood (EDTA), Plain Serum, Fluoride Blood, Spot Urine..."
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Sample Collection Timestamp (Real-time or Manual Edit)
              </label>
              <input
                type="datetime-local"
                value={sampleTimeInput}
                onChange={(e) => setSampleTimeInput(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
              <span className="text-[10px] text-[#8E8A7E] mt-1 block">
                Note: Manual timestamp adjustments (&gt;5 mins drift) are automatically logged in the audit ledger per Section 4.7.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Offline Temporary Sample Barcode (Optional)
              </label>
              <input
                type="text"
                value={tempSampleIdInput}
                onChange={(e) => setTempSampleIdInput(e.target.value)}
                placeholder="e.g. TEMP-SMP-2026-0042"
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333] font-mono"
              />
              <span className="text-[10px] text-[#8E8A7E] mt-1 block">
                For samples collected offline during power/network downtime.
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Collection Remarks (Optional)
              </label>
              <input
                type="text"
                value={sampleNotes}
                onChange={(e) => setSampleNotes(e.target.value)}
                placeholder="Optional phlebotomist remarks..."
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button
                type="button"
                onClick={() => setSampleModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingSample}
                className="px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3E3F27] transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {submittingSample ? 'Recording...' : 'Confirm Sample Taken'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 2: Reject / Spoil Sample Modal (Section 5.3) */}
      <Modal
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject or Spoil Specimen"
      >
        {activeOrder && (
          <form onSubmit={handleSubmitReject} className="space-y-4">
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl space-y-1">
              <span className="text-xs font-bold text-rose-900 block">
                Marking Specimen Unsuitable (D15 Rule)
              </span>
              <p className="text-[11px] text-rose-800 leading-relaxed">
                Order #{activeOrder.test_order_id} ({activeOrder.test_name}). Rejecting a specimen marks the task Not Performed, locks ordinary cancellation, and triggers patient follow-up for a new collection. There is no free re-run.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Incident Classification
              </label>
              <select
                value={spoilTypeInput}
                onChange={(e) => setSpoilTypeInput(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              >
                <option value="REJECTED">REJECTED (Hemolyzed, Clotted, Insufficient Volume)</option>
                <option value="SPOILED">SPOILED (Mishandled, Contaminated, Tube Broken)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Rejection Reason (Mandatory)
              </label>
              <select
                value={rejectionReasonInput}
                onChange={(e) => setRejectionReasonInput(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333] mb-2"
              >
                <option value="Hemolyzed specimen unsuitable for analysis">Hemolyzed specimen unsuitable for analysis</option>
                <option value="Grossly clotted specimen (EDTA failure)">Grossly clotted specimen (EDTA failure)</option>
                <option value="Insufficient sample volume (QNS)">Insufficient sample volume (QNS)</option>
                <option value="Lipemic / Chylous specimen interference">Lipemic / Chylous specimen interference</option>
                <option value="Container damaged / specimen leaked">Container damaged / specimen leaked</option>
                <option value="Incorrect specimen tube / anticoagulant used">Incorrect specimen tube / anticoagulant used</option>
                <option value="Custom">Custom / Other Clinical Reason</option>
              </select>

              {rejectionReasonInput === 'Custom' && (
                <input
                  type="text"
                  placeholder="Specify clinical rejection reason..."
                  onChange={(e) => setRejectionReasonInput(e.target.value)}
                  className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
                  required
                />
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Additional Observations
              </label>
              <textarea
                value={rejectionNotesInput}
                onChange={(e) => setRejectionNotesInput(e.target.value)}
                placeholder="Details of phlebotomy or laboratory observation..."
                rows={2}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button
                type="button"
                onClick={() => setRejectModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingReject}
                className="px-4 py-2 text-xs font-semibold bg-rose-600 text-white rounded-xl hover:bg-rose-700 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {submittingReject ? 'Rejecting...' : 'Confirm Sample Rejection'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 3: Patient Contact Follow-up Modal (D15 rule) */}
      <Modal
        isOpen={contactModalOpen}
        onClose={() => setContactModalOpen(false)}
        title="Record Patient Follow-up Call"
      >
        {activeOrder && (
          <form onSubmit={handleSubmitContact} className="space-y-4">
            <div className="p-3 bg-[#FAF9F6] border border-[#DCDAD4] rounded-xl space-y-1">
              <span className="text-xs font-semibold text-[#1B1B0E] block">
                Patient: {activeOrder.patient_name} ({activeOrder.patient_code})
              </span>
              <span className="text-xs text-[#525333] block">
                Phone: <strong className="font-mono">{activeOrder.patient_phone || 'No phone recorded'}</strong>
              </span>
              <span className="text-[11px] text-rose-700 block">
                Reason for Call: Specimen {activeOrder.status} ({activeOrder.rejection_reason || 'Rejection'})
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Call Outcome
              </label>
              <select
                value={contactStatusInput}
                onChange={(e) => setContactStatusInput(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              >
                <option value="CALLED">CALLED (Spoke with patient / Voicemail left)</option>
                <option value="RECOLLECTION_AGREED">RECOLLECTION_AGREED (Patient agreed to come for new sample)</option>
                <option value="REFUND_REQUESTED">REFUND_REQUESTED (Patient requested refund for cancelled test)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Call Notes
              </label>
              <textarea
                value={contactNotesInput}
                onChange={(e) => setContactNotesInput(e.target.value)}
                placeholder="Log patient response, expected arrival time, or refund request details..."
                rows={3}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button
                type="button"
                onClick={() => setContactModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingContact}
                className="px-4 py-2 text-xs font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3E3F27] transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {submittingContact ? 'Saving...' : 'Save Call Outcome'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 4: Culture Multi-Stage Progression Modal */}
      <Modal
        isOpen={cultureModalOpen}
        onClose={() => setCultureModalOpen(false)}
        title="Culture & Sensitivity Stage Transition"
      >
        {activeOrder && (
          <form onSubmit={handleSubmitCulture} className="space-y-4">
            <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl space-y-1">
              <span className="text-xs font-semibold text-purple-900 block">
                {activeOrder.test_name} ({activeOrder.test_code})
              </span>
              <span className="text-[11px] text-purple-800 block">
                Current Stage: <strong>{activeOrder.culture_stage || 'Not Started'}</strong>
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Target Culture Stage
              </label>
              <select
                value={cultureStageInput}
                onChange={(e) => setCultureStageInput(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              >
                <option value="INCUBATING">INCUBATING (24h/48h incubation in progress)</option>
                <option value="PRELIMINARY">PRELIMINARY (Growth observed, preliminary report)</option>
                <option value="FINAL">FINAL (Organism identified & AST sensitivity done)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Stage Remarks
              </label>
              <textarea
                value={cultureNotesInput}
                onChange={(e) => setCultureNotesInput(e.target.value)}
                placeholder="Incubation observations, colony count, preliminary Gram stain..."
                rows={2}
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button
                type="button"
                onClick={() => setCultureModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingCulture}
                className="px-4 py-2 text-xs font-semibold bg-purple-700 text-white rounded-xl hover:bg-purple-800 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {submittingCulture ? 'Saving...' : 'Update Culture Stage'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 5: Outsourced Referral Lab Modal */}
      <Modal
        isOpen={outsourcedModalOpen}
        onClose={() => setOutsourcedModalOpen(false)}
        title="Outside Referral Laboratory Log"
      >
        {activeOrder && (
          <form onSubmit={handleSubmitOutsourced} className="space-y-4">
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl space-y-1">
              <span className="text-xs font-semibold text-blue-900 block">
                {activeOrder.test_name} ({activeOrder.test_code})
              </span>
              <span className="text-[11px] text-blue-800 block">
                Action: <strong>{outsourcedActionInput === 'SENT' ? 'Dispatch Specimen Out' : 'Receive Results In'}</strong>
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Referral Laboratory Name
              </label>
              <input
                type="text"
                value={outsourcedLabName}
                onChange={(e) => setOutsourcedLabName(e.target.value)}
                placeholder="e.g. Popular Diagnostic, icddr,b, Armed Forces Lab..."
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Dispatch / Tracking / Reference Number
              </label>
              <input
                type="text"
                value={outsourcedRefNo}
                onChange={(e) => setOutsourcedRefNo(e.target.value)}
                placeholder="e.g. Courier #99812 or Lab Order #REF-881"
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333] font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#1B1B0E] mb-1">
                Remarks
              </label>
              <input
                type="text"
                value={outsourcedNotesInput}
                onChange={(e) => setOutsourcedNotesInput(e.target.value)}
                placeholder="Transport conditions (cold chain, ice pack)..."
                className="w-full text-xs px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button
                type="button"
                onClick={() => setOutsourcedModalOpen(false)}
                className="px-4 py-2 text-xs font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingOutsourced}
                className="px-4 py-2 text-xs font-semibold bg-blue-700 text-white rounded-xl hover:bg-blue-800 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {submittingOutsourced ? 'Saving...' : 'Confirm Outsourced Stage'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* MODAL 6: Specimen Tube Barcode Label Printing Modal */}
      <SampleBarcodeModal
        isOpen={barcodeModalOpen}
        onClose={() => setBarcodeModalOpen(false)}
        labelData={barcodeData}
      />

      {/* MODAL 7: Operational Lifecycle Timeline Modal */}
      <LifecycleHistoryModal
        isOpen={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        order={activeOrder}
      />

      {/* MODAL 8: Module 13 Result Entry Modal */}
      <ResultEntryModal
        isOpen={resultModalOpen}
        onClose={() => setResultModalOpen(false)}
        order={activeOrder}
        onSuccess={handleResultSaved}
        showToast={showToast}
      />
      {/* Prompt 10E Part 9: Report preview of a saved result */}
      {previewOrderId !== null && (
        <ResultReportPreviewModal
          key={previewOrderId}
          isOpen
          onClose={() => setPreviewOrderId(null)}
          testOrderId={previewOrderId}
          source="lab"
          onFinalized={fetchData}
        />
      )}

      {/* Prompt 10E Part 7: Reassign to another room */}
      <Modal isOpen={reassignModalOpen} onClose={() => setReassignModalOpen(false)} title="Reassign to Another Room">
        {activeOrder && (
          <form onSubmit={handleSubmitReassign} className="space-y-4 text-xs">
            <div className="p-3 bg-[#F4F3F0] rounded-xl border border-[#DCDAD4] space-y-1">
              <span className="font-semibold text-[#1B1B0E] block">
                Order #{activeOrder.test_order_id}: {activeOrder.test_name}
              </span>
              <span className="text-[#6D6A60] block">Current room: {activeOrder.lab_section_label || 'none'}</span>
              <span className="text-[#6D6A60] block">Samples and results already entered are kept.</span>
            </div>
            <div>
              <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor="reassign-room-select">New room *</label>
              <select
                id="reassign-room-select"
                data-testid="reassign-room-select"
                required
                value={reassignRoom}
                onChange={(e) => setReassignRoom(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              >
                <option value="" disabled>Select a room…</option>
                {rooms
                  .filter((r) => r.code !== activeOrder.lab_section)
                  .map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.name} ({r.room}){r.active_technicians === 0 ? ' — no technician' : ''}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor="reassign-reason-input">Reason (optional)</label>
              <input
                id="reassign-reason-input"
                type="text"
                maxLength={255}
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
                placeholder="e.g. analyser down in this room"
                className="w-full px-3 py-2 bg-white border border-[#CAC7BE] rounded-xl focus:outline-none focus:border-[#525333]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-[#DCDAD4]">
              <button type="button" onClick={() => setReassignModalOpen(false)} className="px-4 py-2 font-medium text-[#54524A] hover:bg-[#F4F3F0] rounded-xl cursor-pointer">
                Cancel
              </button>
              <button
                type="submit"
                disabled={submittingReassign || !reassignRoom}
                className="px-4 py-2 font-semibold bg-[#525333] text-white rounded-xl hover:bg-[#3E3F27] disabled:opacity-50 cursor-pointer"
              >
                {submittingReassign ? 'Moving…' : 'Move Order'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};
