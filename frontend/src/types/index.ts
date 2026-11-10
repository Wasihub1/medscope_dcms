export type Gender = 'MALE' | 'FEMALE' | 'OTHER';
export type PaymentStatus = 'PAID' | 'PARTIAL' | 'DUE' | 'REFUNDED' | 'CANCELLED';
export type DiscountType = 'PERCENT' | 'FIXED' | 'NONE';
export type PaymentChannel = 'CASH' | 'BKASH' | 'NAGAD' | 'ROCKET' | 'CARD' | 'BANK_TRANSFER';
export type BusinessDayStatus = 'OPEN' | 'CLOSED';
export type RefundStatus = 'PENDING_ADMIN_APPROVAL' | 'APPROVED' | 'REJECTED' | 'COMPLETED';
export type ReportStatus = 'DRAFT' | 'PRELIMINARY' | 'AUTHORIZED' | 'DELIVERED';
export type Role = 'RECEPTIONIST' | 'ADMIN' | 'CASHIER' | 'LAB_TECH' | 'OWNER';

export interface Patient {
  id: string;
  tenant_id: string;
  mrn: string;
  full_name: string;
  phone: string;
  alternate_phone?: string | null;
  email?: string | null;
  gender: Gender;
  dob?: string | null;
  age_years?: number | null;
  age_months?: number | null;
  age_days?: number | null;
  address?: string | null;
  blood_group?: string | null;
  national_id?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PatientHistoryPayment {
  id: number;
  invoice_id: number;
  invoice_no: string;
  amount: number;
  method: string;
  reference?: string | null;
  received_at: string;
}

export interface PatientHistoryVisit {
  visit_id: number;
  visit_number: string;
  visit_date: string;
  age_summary: string;
  gender: string;
}

export interface PatientHistory {
  id: string;
  tenant_id: string;
  mrn: string;
  full_name: string;
  phone: string;
  gender: Gender;
  address?: string | null;
  created_at: string;
  updated_at?: string;
  patient?: any;
  visits?: PatientHistoryVisit[];
  invoices: any[];
  payments?: PatientHistoryPayment[];
  total_visits: number;
  total_spent: number;
  total_due: number;
  total_paid?: number;
}

export interface Referrer {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  referrer_type?: string;
  degree?: string | null;
  designation?: string | null;
  institution?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  specialty?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TestDestination {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  department: string;
  room_no?: string | null;
  floor?: string | null;
  is_active: boolean;
}

export interface TestItem {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  department: string;
  specimen_type?: string | null;
  default_price: number;
  discount_cap_percent: number;
  turnaround_hours: number;
  performing_role?: string;
  requires_doctor?: boolean;
  report_template?: string;
  approval_rule?: string;
  is_outsourced?: boolean;
  is_active: boolean;
  default_destination_id?: string | null;
  destination_name?: string | null;
}

export interface InvoiceLine {
  id: string;
  invoice_id: string;
  test_id: string;
  test_code: string;
  test_name: string;
  department: string;
  price: number;
  discount_type: DiscountType;
  discount_value: number;
  discount_amount: number;
  net_amount: number;
  is_urgent: boolean;
  urgent_fee: number;
  sample_collected: boolean;
  sample_status?: string | null;
  is_locked?: boolean;
  locked_reason?: string | null;
  outcome?: string | null;
  d15_refund_status?: string | null;
  d15_refund_reason?: string | null;
  sample_id?: string | null;
  test_order_id?: string | null;
  assigned_destination_id?: string | null;
  assigned_destination_name?: string | null;
}

export interface PaymentRecord {
  id: string;
  invoice_id: string;
  receipt_no: string;
  amount: number;
  channel: PaymentChannel;
  reference_no?: string | null;
  notes?: string | null;
  created_at: string;
  received_by_id: string;
  received_by_name?: string | null;
}

export interface Invoice {
  id: string;
  tenant_id: string;
  invoice_number: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  patient_mrn: string;
  patient_age_display?: string | null;
  patient_gender?: Gender | null;
  prescribed_by_id?: string | null;
  prescribed_by_name?: string | null;
  referrer_id?: string | null;
  referrer_name?: string | null;
  referrer_code?: string | null;
  gross_amount: number;
  master_discount_type: DiscountType;
  master_discount_value: number;
  master_discount_amount: number;
  line_discount_total: number;
  urgent_fee_total: number;
  net_amount: number;
  paid_amount: number;
  due_amount: number;
  payment_status: PaymentStatus;
  refund_status?: string;
  notes?: string | null;
  created_at: string;
  created_by_id: string;
  created_by_name?: string | null;
  lines: InvoiceLine[];
  payments: PaymentRecord[];
  refund_requests?: any[];
  is_reprint?: boolean;
  is_duplicate_reprint?: boolean;
  reprint_count?: number;
}

export interface InvoiceSummary {
  id: string;
  invoice_number: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  patient_mrn: string;
  prescribed_by_name?: string | null;
  referrer_name?: string | null;
  gross_amount: number;
  discount_amount: number;
  net_amount: number;
  paid_amount: number;
  due_amount: number;
  payment_status: PaymentStatus;
  refund_status?: string;
  lines_count: number;
  created_at: string;
  created_by_name?: string | null;
}

export interface UnassignedTestOrder {
  id: string;
  invoice_id: string;
  invoice_number: string;
  patient_name: string;
  patient_phone: string;
  test_id: string;
  test_code: string;
  test_name: string;
  department: string;
  is_urgent: boolean;
  order_status: string;
  created_at: string;
  suggested_destination_id?: string | null;
  suggested_destination_name?: string | null;
  assigned_destination_id?: string | null;
  assigned_destination_name?: string | null;
  assigned_staff_id?: string | null;
}

export interface RefundRequestItem {
  id: string;
  invoice_id: string;
  invoice_number: string;
  invoice_line_id?: string | null;
  test_name?: string | null;
  patient_name: string;
  amount: number;
  reason: string;
  status: RefundStatus;
  requested_by_id: string;
  requested_by_name?: string | null;
  approved_by_id?: string | null;
  approved_by_name?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  processed_at?: string | null;
  request_type?: string | null;
  disbursed_at?: string | null;
  disbursed_by_name?: string | null;
  disbursement_method?: string | null;
  disbursement_reference?: string | null;
}

export interface DeliverableReportItem {
  id: string;
  report_version_id?: string | number;
  test_order_id: string;
  invoice_id: string;
  invoice_number: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  patient_mrn: string;
  test_name: string;
  department: string;
  due_amount: number;
  report_status: ReportStatus;
  version_number: number;
  authorized_at?: string | null;
  authorized_by_name?: string | null;
  is_delivered: boolean;
  delivered_at?: string | null;
  delivered_to_name?: string | null;
  delivered_to_relation?: string | null;
  can_deliver: boolean;
}

export interface ChannelBalance {
  channel: PaymentChannel;
  opening_balance: number;
  current_balance: number;
  collections_count: number;
}

export interface BusinessDay {
  id: string;
  tenant_id: string;
  day_number: number;
  business_date: string;
  status: BusinessDayStatus;
  opened_at: string;
  opened_by_id: string;
  opened_by_name?: string | null;
  closed_at?: string | null;
  closed_by_name?: string | null;
  opening_balance: number;
  total_collections: number;
  total_refunds: number;
  current_balance: number;
  notes?: string | null;
  channel_balances: ChannelBalance[];
}

export interface DashboardMetrics {
  business_day?: BusinessDay | null;
  today_invoices_count: number;
  today_gross_amount: number;
  today_net_amount: number;
  today_paid_amount: number;
  today_due_amount: number;
  today_refund_amount: number;
  active_patients_today: number;
  unassigned_tests_count: number;
  ready_reports_count: number;
  held_reports_count: number;
  pending_refunds_count: number;
  recent_invoices: InvoiceSummary[];
}

export interface GlobalSearchResult {
  category: 'PATIENT' | 'INVOICE' | 'REPORT' | 'TEST' | 'SAMPLE';
  id: string;
  title: string;
  subtitle: string;
  status?: string | null;
  extra?: string | null;
}

export interface TechnicianWorklistItem {
  test_order_id: number;
  invoice_id: number;
  invoice_no: string;
  status: string;
  urgent: boolean;

  patient_id: number;
  patient_name: string;
  patient_code: string;
  patient_gender?: string | null;
  patient_age?: string | null;
  patient_phone?: string | null;

  test_id: number;
  test_code: string;
  test_name: string;
  department: string;
  sample_type?: string | null;
  sample_route: string;
  report_template: string;
  approval_rule: string;
  requires_doctor?: boolean;

  sample_id?: number | null;
  sample_code?: string | null;
  temp_sample_id?: string | null;
  sample_status: string;
  sample_collected_at?: string | null;
  is_line_locked?: boolean;
  rejection_reason?: string | null;
  outcome?: string | null;
  result_status?: string | null;
  has_result?: boolean;

  patient_followup_required?: boolean;
  patient_contact_status?: string | null;
  patient_contact_notes?: string | null;
  d15_refund_status?: string | null;

  culture_stage?: string | null;
  outsourced_status?: string | null;
  outsourced_lab_name?: string | null;
  outsourced_sent_at?: string | null;
  outsourced_received_at?: string | null;
  outsourced_ref_no?: string | null;

  assigned_to_id?: number | null;
  assigned_to_name?: string | null;
  assigned_destination?: string | null;
  assigned_at?: string | null;

  turnaround_hours?: number | null;
  tat_display: string;
  ordered_at: string;
  patient_clock_elapsed_mins: number;
  patient_clock_display: string;
  lab_clock_elapsed_mins?: number | null;
  lab_clock_display?: string | null;
  is_late: boolean;
  late_reason?: string | null;
}

export interface WorklistSummary {
  technician_id: number;
  technician_name: string;
  department?: string | null;
  total_assigned: number;
  urgent_count: number;
  sample_pending_count: number;
  in_progress_count: number;
  awaiting_doctor_count: number;
  late_count: number;
  completed_count: number;
  rejected_count?: number;
  culture_count?: number;
  imaging_count?: number;
  outsourced_count?: number;
}

export interface BarcodeLabelData {
  test_order_id: number;
  sample_code: string;
  temp_sample_id?: string | null;
  patient_name: string;
  patient_code: string;
  patient_gender?: string | null;
  patient_age?: string | null;
  test_code: string;
  test_name: string;
  department: string;
  sample_type?: string | null;
  collected_at?: string | null;
  barcode_svg: string;
  barcode_format: string;
}

export interface TestOrderEvent {
  id: number;
  test_order_id: number;
  event_type: string;
  stage?: string | null;
  description: string;
  notes?: string | null;
  actor_id?: number | null;
  actor_name?: string | null;
  actor_role?: string | null;
  created_at: string;
}

// Module 13: Result Entry & Report Data Types
export interface TestComponent {
  id: number;
  test_id: number;
  code: string;
  name: string;
  unit?: string | null;
  reference_range_text?: string | null;
  ref_min?: number | null;
  ref_max?: number | null;
  critical_min?: number | null;
  critical_max?: number | null;
  impossible_min?: number | null;
  impossible_max?: number | null;
  sort_order: number;
}

export interface ComponentResultInput {
  component_id?: number | null;
  component_name: string;
  component_code?: string | null;
  value: string;
  unit?: string | null;
  reference_range?: string | null;
  ref_min?: number | null;
  ref_max?: number | null;
  critical_min?: number | null;
  critical_max?: number | null;
  impossible_min?: number | null;
  impossible_max?: number | null;
  comment?: string | null;
  sort_order?: number;
}

export interface ResultEntryPayload {
  status: 'DRAFT' | 'ENTERED';
  findings?: string;
  impression?: string;
  comments?: string;
  structured_data?: Record<string, any>;
  items: ComponentResultInput[];
}

export interface ResultItem {
  id: number;
  test_component_id?: number | null;
  component_name: string;
  component_code?: string | null;
  value: string;
  numeric_value?: number | null;
  unit?: string | null;
  reference_range?: string | null;
  ref_min?: number | null;
  ref_max?: number | null;
  critical_min?: number | null;
  critical_max?: number | null;
  impossible_min?: number | null;
  impossible_max?: number | null;
  flag?: 'NORMAL' | 'LOW' | 'HIGH' | 'CRITICAL' | null;
  comment?: string | null;
  sort_order: number;
}

export interface ResultRecord {
  id: number;
  test_order_id: number;
  result_type: string;
  status: string;
  findings?: string | null;
  impression?: string | null;
  comments?: string | null;
  structured_data?: Record<string, any> | null;
  entered_by_id: number;
  entered_by_name?: string | null;
  entered_at: string;
  updated_at: string;
  items: ResultItem[];
}

export interface ResultTemplateData {
  test_order_id: number;
  invoice_no: string;
  test_id: number;
  test_code: string;
  test_name: string;
  department: string;
  sample_code?: string | null;
  sample_type?: string | null;
  report_template: string;
  approval_rule: string;
  requires_doctor: boolean;
  patient_name: string;
  patient_code: string;
  patient_gender?: string | null;
  patient_age?: string | null;
  components: TestComponent[];
  existing_result?: ResultRecord | null;
}



