import {
  Patient,
  PatientHistory,
  Referrer,
  TestItem,
  TestDestination,
  Invoice,
  InvoiceSummary,
  UnassignedTestOrder,
  RefundRequestItem,
  CancellationBreakdown,
  InvoiceCancellationBreakdown,
  TestRanges,
  RangeVersion,
  RangeBandInput,
  DeliverableReportItem,
  BusinessDay,
  BusinessDayState,
  DashboardMetrics,
  GlobalSearchResult,
  Role,
  TechnicianWorklistItem,
  WorklistSummary,
  BarcodeLabelData,
  TestOrderEvent,
  AuthUser,
  AuthMessageResponse,
  UserAdminMeta,
  ManagedUser,
  ManagedUserDetail,
  LabRoom,
  AssignedTestOrder,
  ReadyReportItem,
  ResultPreview,
  ApprovalQueue,
  DuesCallList,
  WriteOffRecord,
  DoctorBalances,
  CenterSettings,
  DayScreen,
  JournalEntryRow,
  FinalizeReportResult,
  ApprovalQueueItem,
  ApprovalRecord,
  ApprovalDetail,
  DeletedItem,
  AuditLogPage,
  AuditLogMeta,
  AuditLogQuery,
} from '../types';

import { announceSampleChange } from '../utils/sampleChangeEvents';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Global 401 callback listener
let onUnauthorizedCallback: (() => void) | null = null;
export const setUnauthorizedCallback = (callback: (() => void) | null) => {
  onUnauthorizedCallback = callback;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${API_BASE_URL}${cleanPath}`;
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');
  headers.set('X-Requested-With', 'XMLHttpRequest');

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      credentials: 'include',
      headers,
    });
  } catch (netErr: any) {
    throw new Error(`Network connection error: ${netErr.message || 'Failed to fetch API.'}`);
  }

  if (response.status === 401 && !path.includes('/auth/login')) {
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
  }

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`;
    let errorCode: string | undefined;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        if (typeof errorJson.detail === 'string') {
          errorDetail = errorJson.detail;
        } else if (typeof errorJson.detail?.message === 'string') {
          // Prompt 13: structured conflicts ({code, message}) e.g. SAMPLE_ALREADY_TAKEN
          errorDetail = errorJson.detail.message;
          errorCode = errorJson.detail.code;
        } else {
          errorDetail = JSON.stringify(errorJson.detail);
        }
      } else if (errorJson.message) {
        errorDetail = errorJson.message;
      }
    } catch {
      // ignore json parse error
    }
    const err: Error & { code?: string; status?: number } = new Error(errorDetail);
    err.code = errorCode;
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export const api = {
  // Authentication (Prompt 09)
  login: (username: string, password: string, role?: string) =>
    request<AuthUser>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password, role }),
    }),

  logout: () =>
    request<AuthMessageResponse>('/auth/logout', {
      method: 'POST',
    }),

  getMe: () =>
    request<AuthUser>('/auth/me'),

  // Prompt 10D Part 5: user management (requires 'user.manage')
  getUserAdminMeta: () => request<UserAdminMeta>('/users/meta'),
  listUsers: () => request<ManagedUser[]>('/users'),
  getUser: (id: number) => request<ManagedUserDetail>(`/users/${id}`),
  createUser: (data: {
    username: string;
    display_name: string;
    password: string;
    role: string;
    department?: string | null;
    lab_section?: string | null;
    doctor_profile_id?: number | null;
    email?: string | null;
    phone?: string | null;
    active: boolean;
    permission_overrides: Record<string, boolean>;
  }) => request<ManagedUserDetail>('/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id: number, data: Record<string, any>) =>
    request<ManagedUserDetail>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  setUserRole: (id: number, role: string, lab_section?: string | null) =>
    request<ManagedUserDetail>(`/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role, lab_section }) }),
  setUserActive: (id: number, active: boolean) =>
    request<ManagedUserDetail>(`/users/${id}/${active ? 'reactivate' : 'deactivate'}`, { method: 'POST' }),
  resetUserPassword: (id: number, new_password: string) =>
    request<AuthMessageResponse>(`/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify({ new_password }) }),
  setUserPermissions: (id: number, overrides: Record<string, boolean | null>) =>
    request<ManagedUserDetail>(`/users/${id}/permissions`, { method: 'PUT', body: JSON.stringify({ overrides }) }),

  changePassword: (old_password: string, new_password: string) =>
    request<AuthMessageResponse>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password, new_password }),
    }),

  adminResetPassword: (userId: number, new_password: string) =>
    request<AuthMessageResponse>(`/auth/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password }),
    }),

  adminUnlockUser: (userId: number) =>
    request<AuthMessageResponse>(`/auth/users/${userId}/unlock`, {
      method: 'POST',
    }),
  // Dashboard
  getDashboard: () => request<DashboardMetrics>('/dashboard'),

  // Global Search
  searchGlobal: async (query: string): Promise<GlobalSearchResult[]> => {
    const data = await request<any>(`/search?q=${encodeURIComponent(query)}`);
    if (Array.isArray(data)) return data;
    const flat: GlobalSearchResult[] = [];
    if (data?.patients) {
      flat.push(
        ...data.patients.map((p: any) => ({
          category: 'PATIENT' as const,
          id: String(p.id),
          title: p.title,
          subtitle: p.subtitle,
          status: p.badge,
        }))
      );
    }
    if (data?.invoices) {
      flat.push(
        ...data.invoices.map((inv: any) => ({
          category: 'INVOICE' as const,
          id: String(inv.id),
          title: inv.title,
          subtitle: inv.subtitle,
          status: inv.badge,
        }))
      );
    }
    if (data?.reports) {
      flat.push(
        ...data.reports.map((r: any) => ({
          category: 'REPORT' as const,
          id: String(r.id),
          title: r.title,
          subtitle: r.subtitle,
          status: r.badge,
        }))
      );
    }
    if (data?.tests) {
      flat.push(
        ...data.tests.map((t: any) => ({
          category: 'TEST' as const,
          id: String(t.id),
          title: t.title,
          subtitle: t.subtitle,
          status: t.badge,
        }))
      );
    }
    if (data?.samples) {
      flat.push(
        ...data.samples.map((s: any) => ({
          category: 'SAMPLE' as const,
          id: String(s.id),
          title: s.title,
          subtitle: s.subtitle,
          status: s.badge,
        }))
      );
    }
    return flat;
  },

  // Patients
  getPatients: (search?: string) => {
    const q = search ? `?q=${encodeURIComponent(search)}` : '';
    return request<Patient[]>(`/patients${q}`);
  },
  getPatient: (id: string | number) => request<Patient>(`/patients/${id}`),
  getPatientHistory: async (id: string | number): Promise<PatientHistory> => {
    const raw = await request<any>(`/patients/${id}/history`);
    const pat = raw.patient || {};
    return {
      id: String(pat.id || id),
      tenant_id: pat.tenant_id || '',
      mrn: pat.mrn || pat.patient_code || '',
      full_name: pat.full_name || pat.name || '',
      phone: pat.phone || '',
      gender: pat.gender || 'OTHER',
      address: pat.address || '',
      created_at: pat.created_at || '',
      patient: pat,
      visits: raw.visits || [],
      invoices: (raw.invoices || []).map((inv: any) => ({
        id: String(inv.invoice_id || inv.id),
        invoice_id: inv.invoice_id || inv.id,
        invoice_number: inv.invoice_no || inv.invoice_number,
        invoice_no: inv.invoice_no || inv.invoice_number,
        created_at: inv.created_at,
        patient_name: pat.name || pat.full_name,
        patient_phone: pat.phone,
        patient_mrn: pat.patient_code || pat.mrn,
        gross_amount: inv.gross ?? inv.gross_amount ?? 0,
        net_amount: inv.net ?? inv.net_amount ?? 0,
        paid_amount: inv.paid ?? inv.paid_amount ?? 0,
        due_amount: inv.due ?? inv.due_amount ?? 0,
        payment_status: inv.payment_status,
        lines_count: (inv.tests_summary || []).length,
        tests_summary: inv.tests_summary || [],
        sample_status: inv.sample_status,
        report_status: inv.report_status,
        report_delivery_status: inv.report_delivery_status,
      })),
      payments: (raw.payments || []).map((p: any) => ({
        id: p.id,
        invoice_id: p.invoice_id,
        invoice_no: p.invoice_no,
        amount: p.amount,
        method: p.method,
        reference: p.reference,
        received_at: p.received_at,
      })),
      total_visits: (raw.visits || []).length || raw.total_invoices_count || 0,
      total_spent: raw.total_billed_amount ?? 0,
      total_due: raw.total_outstanding_due ?? 0,
      total_paid: raw.total_paid_amount ?? 0,
    };
  },
  createPatient: (data: Partial<Patient>) =>
    request<Patient>('/patients', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Referrers
  getReferrers: (search?: string, type?: string) => {
    const params = new URLSearchParams();
    if (search) params.set('q', search);
    if (type) params.set('type', type);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<Referrer[]>(`/referrers${qs}`);
  },
  createReferrer: (data: Partial<Referrer> & { commission_rate?: number; commission_type?: string }) =>
    request<Referrer>('/referrers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Tests & Destinations
  getTests: (search?: string, department?: string, limit: number = 2500) => {
    const params = new URLSearchParams();
    if (search) params.set('q', search);
    if (department && department !== 'ALL') params.set('department', department);
    params.set('limit', String(limit));
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<TestItem[]>(`/tests${qs}`);
  },
  getDestinations: () => request<TestDestination[]>('/tests/destinations'),

  // Invoices
  getInvoices: (params?: { search?: string; payment_status?: string; start_date?: string; end_date?: string }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set('q', params.search);
    if (params?.payment_status && params.payment_status !== 'ALL' && params.payment_status !== 'All Payments') {
      q.set('status', params.payment_status);
    }
    if (params?.start_date) q.set('date_from', params.start_date);
    if (params?.end_date) q.set('date_to', params.end_date);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<InvoiceSummary[]>(`/invoices${qs}`);
  },
  getInvoice: (id: string | number) => request<Invoice>(`/invoices/${id}`),
  createInvoice: (data: any) =>
    request<Invoice>('/invoices', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  // Prompt 11: soft delete / restore / Deleted views / draft discard / audit log
  deleteUser: (id: number, reason: string) =>
    request<ManagedUserDetail>(`/users/${id}/delete`, { method: 'POST', body: JSON.stringify({ reason }) }),
  restoreUser: (id: number) => request<ManagedUserDetail>(`/users/${id}/restore`, { method: 'POST' }),
  getDeletedUsers: () => request<DeletedItem[]>('/users/deleted'),
  updateReferrer: (id: number | string, data: { name?: string; referrer_type?: string; phone?: string | null; registration_no?: string | null; specialty?: string | null; chamber_address?: string | null }) =>
    request<Referrer>(`/referrers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteReferrer: (id: number | string, reason: string) =>
    request<DeletedItem>(`/referrers/${id}/delete`, { method: 'POST', body: JSON.stringify({ reason }) }),
  restoreReferrer: (id: number | string) => request<any>(`/referrers/${id}/restore`, { method: 'POST' }),
  getDeletedReferrers: () => request<DeletedItem[]>('/referrers/deleted'),
  deleteTest: (id: number | string, reason: string) =>
    request<DeletedItem>(`/tests/${id}/delete`, { method: 'POST', body: JSON.stringify({ reason }) }),
  restoreTest: (id: number | string) => request<any>(`/tests/${id}/restore`, { method: 'POST' }),
  getDeletedTests: () => request<DeletedItem[]>('/tests/deleted'),
  discardInvoiceDraft: (id: string | number) =>
    request<{ message: string; discarded_invoice_id: number; temp_invoice_id?: string | null }>(`/invoices/${id}/draft`, { method: 'DELETE' }),
  getAuditLogs: (p: AuditLogQuery) => {
    const q = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== '' && v !== null) q.set(k, String(v)); });
    return request<AuditLogPage>(`/audit-logs${q.toString() ? `?${q.toString()}` : ''}`);
  },
  /** Prompt 19B: CSV of the audit log with the filters currently applied (the export is itself audited server side). */
  downloadAuditCsv: async (p: AuditLogQuery) => {
    const q = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (k !== 'page' && k !== 'size' && v !== undefined && v !== '' && v !== null) q.set(k, String(v)); });
    const res = await fetch(`${API_BASE_URL}/audit-logs/export${q.toString() ? `?${q.toString()}` : ''}`, { credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit-log.csv';
    a.click();
    URL.revokeObjectURL(url);
  },
  unlockInvoiceLine: (lineId: number | string, reason: string) =>
    request<{ message: string; invoice_line_id: number; is_locked: boolean }>(`/invoices/lines/${lineId}/unlock`, { method: 'POST', body: JSON.stringify({ reason }) }),
  getAuditMeta: () => request<AuditLogMeta>('/audit-logs/meta'),

  // Prompt 10D: Draft / Finalize workflow
  createInvoiceDraft: (data: any) =>
    request<Invoice>('/invoices/drafts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateInvoiceDraft: (id: string | number, data: any) =>
    request<Invoice>(`/invoices/${id}/draft`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  finalizeInvoice: (id: string | number, data?: any) =>
    request<Invoice>(`/invoices/${id}/finalize`, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),
  reprintInvoice: (id: string | number, reason?: string) =>
    request<Invoice>(
      `/invoices/${id}/reprint${reason ? '?reason=' + encodeURIComponent(reason) : ''}`,
      {
        method: 'POST',
      }
    ),

  // Payments & Dues
  getDues: (search?: string, bucket?: string) => {
    const q = new URLSearchParams();
    if (search) q.set('q', search);
    if (bucket) q.set('bucket', bucket);
    return request<any[]>(`/dues${q.toString() ? `?${q.toString()}` : ''}`);
  },
  // Prompt 17 (Module 18): call list, write-off (D11), doctor balances (D43), center settings
  getDuesCallList: (bucket?: string, search?: string) => {
    const q = new URLSearchParams();
    if (bucket) q.set('bucket', bucket);
    if (search) q.set('q', search);
    return request<DuesCallList>(`/dues/call-list${q.toString() ? `?${q.toString()}` : ''}`);
  },
  writeOffDue: (invoiceId: number | string, data: { amount: number; reason: string }) =>
    request<WriteOffRecord>(`/invoices/${invoiceId}/write-off`, { method: 'POST', body: JSON.stringify(data) }),
  listWriteOffs: (status?: string) => request<WriteOffRecord[]>(`/dues/write-offs${status ? `?status=${status}` : ''}`),
  decideWriteOff: (id: number, approve: boolean, note?: string) =>
    request<WriteOffRecord>(`/dues/write-offs/${id}/${approve ? 'approve' : 'reject'}`, { method: 'POST', body: JSON.stringify({ note }) }),
  getDoctorBalances: () => request<DoctorBalances>('/doctor-balances'),
  getCenterSettings: () => request<CenterSettings>('/settings'),
  updateCenterSettings: (data: Partial<CenterSettings>) => request<CenterSettings>('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  createPayment: (data: { invoice_id: number | string; amount: number; channel?: string; method?: string; channel_detail?: string; reference_no?: string; notes?: string }) =>
    request<any>('/payments', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  settleDue: (invoiceId: number | string, data: { amount: number; method: string; reference?: string; channel_detail?: string; cash_tendered?: number }) =>
    request<any>(`/invoices/${invoiceId}/settle-due`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Assignments
  getUnassignedTests: (search?: string, department?: string) => {
    const params = new URLSearchParams();
    if (department && department !== 'ALL') params.set('department', department);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<UnassignedTestOrder[]>(`/assignments/unassigned${qs}`);
  },
  /** Prompt 10E: assigns to a ROOM by its key (never a destination id, never a technician). */
  assignTest: (testOrderId: string | number, labSection: string, reason?: string) =>
    request<any>('/assignments/assign', {
      method: 'POST',
      body: JSON.stringify({
        test_order_id: Number(testOrderId),
        lab_section: labSection,
        reason: reason || 'Front desk assignment',
      }),
    }),
  /** Prompt 10F (F1): Assigned Tests view (money-free). Reassign uses reassignRoom below. */
  getAssignedOrders: (params?: { status?: string; lab_section?: string; q?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status && params.status !== 'ALL') q.set('status', params.status);
    if (params?.lab_section && params.lab_section !== 'ALL') q.set('lab_section', params.lab_section);
    if (params?.q) q.set('q', params.q);
    if (params?.limit) q.set('limit', String(params.limit));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<AssignedTestOrder[]>(`/assignments/orders${qs}`);
  },
  getRooms: () => request<LabRoom[]>('/worklist/rooms'),
  reassignRoom: (testOrderId: string | number, labSection: string, reason?: string) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/reassign`, {
      method: 'POST',
      body: JSON.stringify({ lab_section: labSection, reason: reason || undefined }),
    }),
  bulkAssign: (assignments: { test_order_id: string | number; lab_section: string }[]) =>
    request<any>('/assignments/bulk-assign', {
      method: 'POST',
      body: JSON.stringify({
        assignments: assignments.map((a) => ({
          test_order_id: Number(a.test_order_id),
          lab_section: a.lab_section,
        })),
      }),
    }),

  // Refunds
  getRefunds: (status?: string) => {
    const q = status && status !== 'ALL' ? `?status=${encodeURIComponent(status)}` : '';
    return request<RefundRequestItem[]>(`/refunds/requests${q}`);
  },
  // Prompt 13A/13B: cancel ONE unlocked line at once (no approval step). No amount is ever sent: the server
  // calculates it. Cancelling never pays out; disbursement is the separate disburseRefund call.
  requestRefund: (data: { invoice_id: number | string; invoice_line_id: number | string; reason?: string }) =>
    request<RefundRequestItem>('/refunds/request', {
      method: 'POST',
      body: JSON.stringify({
        invoice_id: Number(data.invoice_id),
        invoice_line_id: Number(data.invoice_line_id),
        reason: data.reason || undefined,
      }),
    }),
  // Prompt 13A: cancel every line of an invoice together (only when no line is locked).
  previewInvoiceCancellation: (invoiceId: number | string) =>
    request<InvoiceCancellationBreakdown>(`/refunds/preview-invoice/${invoiceId}`),
  cancelInvoice: (data: { invoice_id: number | string; reason?: string }) =>
    request<RefundRequestItem[]>('/refunds/cancel-invoice', {
      method: 'POST',
      body: JSON.stringify({
        invoice_id: Number(data.invoice_id),
        reason: data.reason || undefined,
      }),
    }),
  getCancellationPreview: (lineId: number | string) =>
    request<CancellationBreakdown>(`/refunds/preview/${lineId}`),
  getRefundBreakdown: (requestId: number | string) =>
    request<CancellationBreakdown>(`/refunds/requests/${requestId}/breakdown`),
  reviewRefund: (id: string | number, data: { status?: 'APPROVED' | 'REJECTED'; action?: 'APPROVE' | 'REJECT'; rejection_reason?: string; review_notes?: string }) =>
    request<RefundRequestItem>(`/refunds/review/${id}`, {
      method: 'POST',
      body: JSON.stringify({
        action: data.action || (data.status === 'APPROVED' ? 'APPROVE' : 'REJECT'),
        review_notes: data.review_notes || data.rejection_reason,
      }),
    }),
  disburseRefund: (id: string | number, data: { method: string; reference?: string; notes?: string }) =>
    request<RefundRequestItem>(`/refunds/disburse/${id}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Reports
  getDeliverableReports: (params?: { search?: string; status?: string; has_due?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set('q', params.search);
    if (params?.status && params.status !== 'ALL') q.set('delivery_status', params.status);
    if (params?.has_due !== undefined) q.set('has_due', String(params.has_due));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<DeliverableReportItem[]>(`/reports/deliverable${qs}`);
  },
  deliverReport: (id: string | number, data: { recipient_name: string; recipient_phone?: string; recipient_relation: string; notes?: string }) =>
    request<any>(`/reports/deliver/${id}`, {
      method: 'POST',
      body: JSON.stringify({
        delivered_to_name: data.recipient_name,
        delivered_to_phone: data.recipient_phone,
        delivered_to_relation: data.recipient_relation,
      }),
    }),
  overrideReportHold: (id: string | number, data: { override_reason: string; recipient_name: string; recipient_relation: string }) =>
    request<any>(`/reports/deliver/${id}`, {
      method: 'POST',
      body: JSON.stringify({
        delivered_to_name: data.recipient_name,
        delivered_to_relation: data.recipient_relation,
        admin_due_override_reason: data.override_reason,
      }),
    }),
  getPrintableReport: (id: string | number) => request<any>(`/reports/printable/${id}`),
  /** Prompt 10F (F3): Ready results from all rooms (not issued reports). */
  getReadyReports: (params?: { q?: string; lab_section?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.q) q.set('q', params.q);
    if (params?.lab_section && params.lab_section !== 'ALL') q.set('lab_section', params.lab_section);
    if (params?.limit) q.set('limit', String(params.limit));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<ReadyReportItem[]>(`/reports/ready${qs}`);
  },
  /**
   * Prompt 10F (F2): read-only preview of a saved result (DRAFT or ENTERED).
   * 'lab' = My Work (room access, worklist.view); 'reports' = sidebar Ready Reports (report.view).
   */
  getResultPreview: (testOrderId: string | number, source: 'lab' | 'reports' = 'lab') =>
    request<ResultPreview>(
      source === 'reports' ? `/reports/ready/${testOrderId}/preview` : `/worklist/${testOrderId}/result-preview`
    ),

  // Prompt 16 (Module 14): finalize a report; stored content of a Final report
  finalizeReport: (testOrderId: number) =>
    request<FinalizeReportResult>(`/worklist/${testOrderId}/finalize-report`, { method: 'POST' }),
  getReportSnapshot: (reportVersionId: string | number) => request<ResultPreview>(`/reports/${reportVersionId}/snapshot`),

  // Prompt 15 (D22): doctor sign-off (Admin/Owner on a doctor's behalf, or the DOCTOR login for own orders)
  getApprovalQueue: (params?: { doctor_id?: number; q?: string }) => {
    const q = new URLSearchParams();
    if (params?.doctor_id) q.set('doctor_id', String(params.doctor_id));
    if (params?.q) q.set('q', params.q);
    return request<ApprovalQueue>(`/doctor-approvals/queue${q.toString() ? `?${q.toString()}` : ''}`);
  },
  getApprovalDetail: (testOrderId: number) => request<ApprovalDetail>(`/doctor-approvals/${testOrderId}`),
  approveResult: (testOrderId: number, data: { doctor_id?: number; attestation?: boolean; notes?: string }) =>
    request<ApprovalRecord>(`/doctor-approvals/${testOrderId}/approve`, { method: 'POST', body: JSON.stringify(data) }),
  assignApprovalDoctor: (testOrderId: number, doctorId: number | null) =>
    request<ApprovalQueueItem>(`/doctor-approvals/${testOrderId}/assign-doctor`, { method: 'POST', body: JSON.stringify({ doctor_id: doctorId }) }),

  // Business Day
  // Prompt 14 (D24): reference-range versions (Admin/Owner)
  getReferenceRanges: (testId: number | string) => request<TestRanges>(`/reference-ranges/tests/${testId}`),
  addRangeBand: (componentId: number, data: RangeBandInput) =>
    request<RangeVersion>(`/reference-ranges/components/${componentId}/bands`, { method: 'POST', body: JSON.stringify(data) }),
  newRangeVersion: (versionId: number, data: RangeBandInput) =>
    request<RangeVersion>(`/reference-ranges/versions/${versionId}/new-version`, { method: 'POST', body: JSON.stringify(data) }),
  retireRangeBand: (versionId: number, reason: string) =>
    request<RangeVersion>(`/reference-ranges/versions/${versionId}/retire`, { method: 'POST', body: JSON.stringify({ reason }) }),
  getBusinessDayState: () => request<BusinessDayState>('/business-day/state'),
  getCurrentBusinessDay: () => request<BusinessDay | null>('/business-day/status'),
  openBusinessDay: (data: { opening_float?: number; opening_balance?: number; channel_balances?: { channel: string; opening_balance: number }[]; notes?: string }) =>
    request<BusinessDay>('/business-day/open', {
      method: 'POST',
      body: JSON.stringify({
        opening_float: data.opening_float ?? data.opening_balance ?? 0,
        channel_balances: data.channel_balances,
        notes: data.notes,
      }),
    }),
  closeBusinessDay: (data: { counted_cash: number; counted_channels?: Record<string, number>; variance_reason?: string; notes?: string; day_id?: number }) =>
    request<any>('/business-day/close', { method: 'POST', body: JSON.stringify(data) }),
  getDayScreen: () => request<DayScreen>('/business-day/day-screen'),
  addDayMovement: (data: { kind: string; amount: number; note?: string }) =>
    request<any>('/business-day/movements', { method: 'POST', body: JSON.stringify(data) }),
  reopenBusinessDay: (dayId: number, reason: string) =>
    request<any>(`/business-day/${dayId}/reopen`, { method: 'POST', body: JSON.stringify({ reason }) }),
  postDayAdjustment: (dayId: number, data: { reason: string; reverse_entry_id?: number; lines?: { account: string; debit?: number; credit?: number }[] }) =>
    request<any>(`/business-day/${dayId}/adjustments`, { method: 'POST', body: JSON.stringify(data) }),
  getJournal: (q: { from?: string; to?: string; business_day_id?: number }) => {
    const p = new URLSearchParams();
    if (q.from) p.set('from', q.from);
    if (q.to) p.set('to', q.to);
    if (q.business_day_id) p.set('business_day_id', String(q.business_day_id));
    return request<{ entries: JournalEntryRow[] }>(`/accounting/journal?${p.toString()}`);
  },
  getAccountingReport: (report: 'cash-book' | 'income-expense' | 'dues' | 'cost-by-referrer', q: { from?: string; to?: string; channel?: string }) => {
    const p = new URLSearchParams();
    if (q.from) p.set('from', q.from);
    if (q.to) p.set('to', q.to);
    if (q.channel) p.set('channel', q.channel);
    return request<any>(`/accounting/${report}?${p.toString()}`);
  },
  /** Excel-friendly CSV of a report (no export mechanism existed before Prompt 18). */
  downloadAccountingCsv: async (report: string, q: { from?: string; to?: string; channel?: string }) => {
    const p = new URLSearchParams({ format: 'csv' });
    if (q.from) p.set('from', q.from);
    if (q.to) p.set('to', q.to);
    if (q.channel) p.set('channel', q.channel);
    const res = await fetch(`${API_BASE_URL}/accounting/${report}?${p.toString()}`, { credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Profile
  getProfile: () => request<any>('/profile/me'),
  updateProfile: (data: { full_name?: string; display_name?: string; phone?: string; email?: string; address?: string }) =>
    request<any>('/profile/me', {
      method: 'PUT',
      body: JSON.stringify({
        display_name: data.display_name || data.full_name || 'Fatima Akter',
        phone: data.phone,
        email: data.email,
        address: data.address,
      }),
    }),

  // Worklist (Module 11)
  getWorklist: (params?: {
    status?: string;
    department?: string;
    urgent_only?: boolean;
    q?: string;
    staff_id?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.status && params.status !== 'ALL') q.set('status', params.status);
    if (params?.department && params.department !== 'ALL') q.set('department', params.department);
    if (params?.urgent_only) q.set('urgent_only', 'true');
    if (params?.q) q.set('q', params.q);
    if (params?.staff_id) q.set('staff_id', String(params.staff_id));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<TechnicianWorklistItem[]>(`/worklist${qs}`);
  },
  getWorklistSummary: (staffId?: number) => {
    const q = staffId ? `?staff_id=${staffId}` : '';
    return request<WorklistSummary>(`/worklist/summary${q}`);
  },
  recordSampleTaken: (
    testOrderId: string | number,
    data: { collected_at?: string; sample_type?: string; temp_sample_id?: string; notes?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/sample-taken`, {
      method: 'POST',
      body: JSON.stringify(data),
    }).then((r) => {
      announceSampleChange(); // Prompt 12: Invoice View refetches
      return r;
    }),
  rejectSample: (
    testOrderId: string | number,
    data: { rejection_reason: string; notes?: string; spoil_type?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/reject-sample`, {
      method: 'POST',
      body: JSON.stringify(data),
    }).then((r) => {
      announceSampleChange();
      return r;
    }),
  recordPatientContact: (
    testOrderId: string | number,
    data: { contact_status: string; notes?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/patient-contact`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  recordImagingPerformed: (
    testOrderId: string | number,
    data: { performed_at?: string; notes?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/imaging-performed`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  recordCultureStage: (
    testOrderId: string | number,
    data: { stage: string; notes?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/culture-stage`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  recordOutsourcedStage: (
    testOrderId: string | number,
    data: { action: string; lab_name?: string; ref_no?: string; timestamp?: string; notes?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/outsourced`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getOrderEvents: (testOrderId: string | number) =>
    request<TestOrderEvent[]>(`/worklist/${testOrderId}/events`),
  getBarcodeLabel: (testOrderId: string | number) =>
    request<BarcodeLabelData>(`/worklist/${testOrderId}/barcode`),
  updateWorklistStatus: (
    testOrderId: string | number,
    data: { status: string; notes?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/status`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Module 13: Result Entry & Report Data
  getResultTemplate: (testOrderId: string | number) =>
    request<any>(`/worklist/${testOrderId}/result-template`),
  /** Prompt 10E Part 9: saved result for the report preview (technician-safe, no money). */
  getOrderResult: (testOrderId: string | number) =>
    request<any>(`/worklist/${testOrderId}/result`),
  saveResult: (testOrderId: string | number, data: any) =>
    request<any>(`/worklist/${testOrderId}/result`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  submitD15RefundRequest: (testOrderId: string | number, notes: string = '') =>
    request<any>(`/worklist/${testOrderId}/d15-refund-request?notes=${encodeURIComponent(notes)}`, {
      method: 'POST',
    }),
};
