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
  DeliverableReportItem,
  BusinessDay,
  DashboardMetrics,
  GlobalSearchResult,
  Role,
  TechnicianWorklistItem,
  WorklistSummary,
  BarcodeLabelData,
  TestOrderEvent,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Active session state for headers aligned with seeded tenant and staff
let currentActor = {
  tenantId: 'center-seba-01',
  role: 'RECEPTIONIST' as Role,
  staffId: 1,
  name: 'Fatima Akter',
};

export const setApiActor = (role: Role, staffId?: number) => {
  if (role === 'ADMIN') {
    currentActor = {
      tenantId: 'center-seba-01',
      role: 'ADMIN',
      staffId: 2,
      name: 'Tariqul Islam',
    };
  } else if (role === 'LAB_TECH') {
    if (staffId === 4) {
      currentActor = {
        tenantId: 'center-seba-01',
        role: 'LAB_TECH',
        staffId: 4,
        name: 'Nasrin Sultana (Biochemistry)',
      };
    } else {
      currentActor = {
        tenantId: 'center-seba-01',
        role: 'LAB_TECH',
        staffId: 3,
        name: 'Kamal Hossain (Hematology)',
      };
    }
  } else {
    currentActor = {
      tenantId: 'center-seba-01',
      role: 'RECEPTIONIST',
      staffId: 1,
      name: 'Fatima Akter',
    };
  }
};

export const getApiActor = () => currentActor;

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${API_BASE_URL}${cleanPath}`;
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');
  headers.set('X-Tenant-Id', currentActor.tenantId);
  headers.set('X-Actor-Id', String(currentActor.staffId));
  headers.set('X-Actor-Role', currentActor.role);
  headers.set('X-Actor-Name', encodeURIComponent(currentActor.name || 'Fatima Akter'));

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (netErr: any) {
    throw new Error(`Network connection error: ${netErr.message || 'Failed to fetch API.'}`);
  }

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
      } else if (errorJson.message) {
        errorDetail = errorJson.message;
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
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
  reprintInvoice: (id: string | number, reason?: string) =>
    request<Invoice>(
      `/invoices/${id}/reprint${reason ? '?reason=' + encodeURIComponent(reason) : ''}`,
      {
        method: 'POST',
      }
    ),

  // Payments & Dues
  getDues: (search?: string) => {
    const q = search ? `?q=${encodeURIComponent(search)}` : '';
    return request<any[]>(`/dues${q}`);
  },
  createPayment: (data: { invoice_id: number | string; amount: number; channel?: string; method?: string; reference_no?: string; notes?: string }) =>
    request<any>('/payments', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  settleDue: (invoiceId: number | string, data: { amount: number; method: string; reference?: string; cash_tendered?: number }) =>
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
  assignTest: (testOrderId: string | number, destinationName: string, reason?: string) =>
    request<any>('/assignments/assign', {
      method: 'POST',
      body: JSON.stringify({
        test_order_id: Number(testOrderId),
        assigned_destination: destinationName,
        reason: reason || 'Front desk assignment',
      }),
    }),
  bulkAssign: (assignments: { test_order_id: string | number; destination_name?: string; destination_id?: string }[]) =>
    request<any>('/assignments/bulk-assign', {
      method: 'POST',
      body: JSON.stringify({
        assignments: assignments.map((a) => ({
          test_order_id: Number(a.test_order_id),
          destination_name: a.destination_name || a.destination_id || 'General Lab',
          destination_id: a.destination_id,
        })),
      }),
    }),

  // Refunds
  getRefunds: (status?: string) => {
    const q = status && status !== 'ALL' ? `?status=${encodeURIComponent(status)}` : '';
    return request<RefundRequestItem[]>(`/refunds/requests${q}`);
  },
  requestRefund: (data: { invoice_id: number | string; invoice_line_id?: number | string; amount: number; reason: string }) =>
    request<RefundRequestItem>('/refunds/request', {
      method: 'POST',
      body: JSON.stringify({
        invoice_id: Number(data.invoice_id),
        invoice_line_id: data.invoice_line_id ? Number(data.invoice_line_id) : undefined,
        amount: data.amount,
        reason: data.reason,
      }),
    }),
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

  // Business Day
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
  closeBusinessDay: (data?: { notes?: string }) =>
    request<any>('/business-day/close', {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

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
    }),
  rejectSample: (
    testOrderId: string | number,
    data: { rejection_reason: string; notes?: string; spoil_type?: string }
  ) =>
    request<TechnicianWorklistItem>(`/worklist/${testOrderId}/reject-sample`, {
      method: 'POST',
      body: JSON.stringify(data),
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
