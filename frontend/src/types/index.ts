export type Gender = 'MALE' | 'FEMALE' | 'OTHER';
export type PaymentStatus = 'PAID' | 'PARTIAL' | 'DUE' | 'REFUNDED' | 'CANCELLED';
export type DiscountType = 'PERCENT' | 'FIXED' | 'NONE';
/** Prompt 10E: exactly the backend channels. The label "Card" is POS_CARD; OTHER needs a typed name. */
export type PaymentChannel = 'CASH' | 'BKASH' | 'NAGAD' | 'ROCKET' | 'POS_CARD' | 'BANK_TRANSFER' | 'OTHER';
export type BusinessDayStatus = 'OPEN' | 'CLOSED';
export type RefundStatus = 'PENDING_ADMIN_APPROVAL' | 'APPROVED' | 'REJECTED' | 'COMPLETED';
export type ReportStatus = 'DRAFT' | 'PRELIMINARY' | 'AUTHORIZED' | 'DELIVERED';
export type Role = 'RECEPTIONIST' | 'ADMIN' | 'CASHIER' | 'LAB_TECH' | 'OWNER' | 'DOCTOR';

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
  /** Prompt 10E: age from the latest visit snapshot (New Invoice prefill) */
  last_age_value?: number | null;
  last_age_unit?: string | null;
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
  /** Prompt 10E: backend-computed urgent fee of this line (informational, never refunded) */
  line_urgent_fee?: number;
  lab_section?: string | null;
  sample_collected: boolean;
  sample_status?: string | null;
  is_locked?: boolean;
  locked_reason?: string | null;
  outcome?: string | null;
  d15_refund_status?: string | null;
  d15_refund_reason?: string | null;
  /** Prompt 13: NONE | CANCELLATION_REQUESTED | CANCELLED_REFUND_PENDING | CANCELLED | CANCELLED_REFUNDED */
  cancellation_state?: string;
  /** Prompt 13: label to show; cancellation/refund states take precedence over the sample status */
  display_status?: string | null;
  can_request_cancellation?: boolean;
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
  /** Prompt 10D: DRAFT or CONFIRMED (CANCELLED reserved). */
  status?: string;
  is_draft?: boolean;
  draft_payload?: Record<string, any> | null;
  finalized_at?: string | null;
  /** Prompt 10E: backend urgent fee (part of net) and the visit snapshot */
  urgent_fee?: number;
  age_value?: number | null;
  age_unit?: string | null;
  visit_gender?: string | null;
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
  status?: string;
  is_draft?: boolean;
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
  lab_section?: string | null;
  lab_section_label?: string | null;
}

/** Prompt 10E: a lab room (routing target) */
export interface LabRoom {
  code: string;
  name: string;
  room: string;
  destination: string;
  label?: string | null;
  active_technicians: number;
}

/** Prompt 13: read-only cancellation numbers from the single backend calculation (whole taka). */
export interface CancellationBreakdown {
  invoice_line_id: number;
  test_name: string;
  invoice_total: number;
  paid_total: number;
  line_price: number;
  retained_amount: number;
  refund_amount: number;
  due_after: number;
  net_after: number;
  can_request: boolean;
  blocker?: string | null;
  snapshot_refund_amount?: number | null;
  differs_from_snapshot?: boolean | null;
}

export interface InvoiceCancellationBreakdown {
  invoice_id: number;
  can_cancel: boolean;
  blocker?: string | null;
  blocker_message?: string | null;
  invoice_total: number;
  paid_total: number;
  lines: { invoice_line_id: number; test_name: string; line_price: number; refund_amount: number }[];
  total_refund: number;
  retained_amount: number;
  due_after: number;
  net_after: number;
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
  has_snapshot?: boolean;
  approval_rule?: string | null;
}

export interface ChannelBalance {
  channel: PaymentChannel;
  opening_balance: number;
  current_balance: number;
  collections_count: number;
}

/** Prompt 13B: money-free open/closed state, readable by every role (incl. Lab Tech). */
export interface BusinessDayState {
  is_open: boolean;
  day_number?: number | null;
  business_date?: string | null;
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
  /** Prompt 10E */
  requires_sample?: boolean;
  is_imaging?: boolean;
  lab_section?: string | null;
  lab_section_label?: string | null;
  report_ready?: boolean;
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
  ready_count?: number;
  unassigned_count?: number;
  lab_section?: string | null;
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
  /** Prompt 14 (D24): band chosen for this patient (sex + age in days) and how it matched */
  reference_range_version_id?: number | null;
  range_match?: 'MATCHED' | 'FALLBACK_ANY' | 'NO_BAND' | null;
}

export interface RangeVersion {
  id: number;
  test_component_id: number;
  sex: 'ANY' | 'MALE' | 'FEMALE';
  age_days_min: number;
  age_days_max?: number | null;
  ref_min?: number | null;
  ref_max?: number | null;
  critical_min?: number | null;
  critical_max?: number | null;
  reference_range_text?: string | null;
  version_no: number;
  is_current: boolean;
  effective_from: string;
  retired_at?: string | null;
  change_note?: string | null;
}

export interface ComponentRanges {
  component_id: number;
  code: string;
  name: string;
  unit?: string | null;
  versions: RangeVersion[];
}

export interface TestRanges {
  test_id: number;
  test_name: string;
  components: ComponentRanges[];
}

export interface RangeBandInput {
  sex?: string;
  age_days_min?: number;
  age_days_max?: number | null;
  ref_min?: number | null;
  ref_max?: number | null;
  critical_min?: number | null;
  critical_max?: number | null;
  reference_range_text?: string | null;
  note?: string | null;
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
  updated_by_name?: string | null;
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

export interface AuthUser {
  id: number;
  tenant_id: string;
  username: string;
  display_name: string;
  /** Prompt 10D: always exactly one role */
  roles: Role[];
  acting_role: Role;
  role?: Role;
  department?: string | null;
  lab_section?: string | null;
  email?: string | null;
  phone?: string | null;
  home_route: string;
  /** Prompt 10D: effective permission keys (role defaults + per-user overrides) */
  permissions?: string[];
}

// Prompt 10D Part 5: user management
export interface PermissionDef {
  key: string;
  label: string;
  group: string;
  exposes_money: boolean;
}

export interface LabSection {
  code: string;
  name: string;
  room: string;
  label: string;
}

export interface UserAdminMeta {
  roles: Role[];
  permissions: PermissionDef[];
  role_defaults: Record<string, string[]>;
  money_restricted_roles: string[];
  lab_sections: LabSection[];
}

export interface ManagedUser {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  department?: string | null;
  lab_section?: string | null;
  lab_section_label?: string | null;
  doctor_profile_id?: number | null;
  doctor_profile_name?: string | null;
  email?: string | null;
  phone?: string | null;
  active: boolean;
  is_locked: boolean;
  last_login_at?: string | null;
  override_count: number;
}

export interface ManagedUserDetail extends ManagedUser {
  permissions: {
    role: Role;
    defaults: string[];
    overrides: Record<string, boolean>;
    effective: string[];
  };
}

export interface AuthMessageResponse {
  message: string;
  success: boolean;
}





/** Prompt 10F (F1): one row of the Assigned Tests view. Money-free by design. */
export interface AssignedTestOrder {
  test_order_id: number;
  invoice_id: number;
  invoice_no: string;
  patient_id: number;
  patient_name: string;
  patient_code: string;
  test_code: string;
  test_name: string;
  department?: string | null;
  lab_section?: string | null;
  lab_section_label?: string | null;
  /** Active technicians of the room; empty when the order is UNASSIGNED */
  technician_names: string[];
  assignment_state: 'ASSIGNED' | 'UNASSIGNED';
  status: string;
  urgent: boolean;
  result_status?: string | null;
  worked_by_name?: string | null;
  created_at: string;
  can_reassign: boolean;
  reassign_block_reason?: string | null;
}

/** Prompt 10F (F3): a Ready result (ENTERED, not issued). Due keys only for money-permitted roles. */
export interface ReadyReportItem {
  test_order_id: number;
  invoice_id: number;
  invoice_no: string;
  patient_id: number;
  patient_name: string;
  patient_code: string;
  patient_phone?: string | null;
  test_code: string;
  test_name: string;
  department?: string | null;
  lab_section?: string | null;
  lab_section_label?: string | null;
  order_status: string;
  urgent?: boolean;
  result_status: string;
  result_entered_at?: string | null;
  result_entered_by_name?: string | null;
  approval_rule?: string | null;
  doctor_approved?: boolean;
  can_finalize?: boolean;
  finalize_blocker?: string | null;
  has_due?: boolean;
  invoice_due?: number;
}

/** Prompt 10F (F2): read-only preview of a saved result (stored snapshots only). */
export interface ResultPreviewItem {
  component_name: string;
  component_code?: string | null;
  value: string;
  unit?: string | null;
  reference_range?: string | null;
  ref_min?: number | null;
  ref_max?: number | null;
  critical_min?: number | null;
  critical_max?: number | null;
  flag?: string | null;
  comment?: string | null;
}

export interface ResultPreview {
  test_order_id: number;
  invoice_no: string;
  patient_name: string;
  patient_code: string;
  patient_gender?: string | null;
  patient_age?: string | null;
  test_code: string;
  test_name: string;
  department?: string | null;
  lab_section_label?: string | null;
  sample_code?: string | null;
  sample_type?: string | null;
  sample_collected_at?: string | null;
  order_status: string;
  report_template?: string | null;
  result_status: string;
  is_draft: boolean;
  is_ready: boolean;
  findings?: string | null;
  impression?: string | null;
  comments?: string | null;
  structured_data?: Record<string, string> | null;
  entered_by_name?: string | null;
  entered_at?: string | null;
  updated_at?: string | null;
  // Prompt 16 (Module 14)
  approval_rule?: string | null;
  doctor_approved?: boolean;
  report_status?: 'NONE' | 'FINAL';
  report_version_id?: number | null;
  report_no?: string | null;
  can_finalize?: boolean;
  finalize_blocker?: string | null;
  signatures?: {
    technician?: { name?: string | null; role?: string | null; signed_at?: string | null } | null;
    doctor?: { name?: string | null; registration_no?: string | null; approved_at?: string | null; recorded_by_role?: string | null; is_attestation?: boolean } | null;
  } | null;
  items: ResultPreviewItem[];
}

export interface FinalizeReportResult {
  report_version_id: number;
  report_no: string;
  version: number;
  status: string;
  finalized_at: string;
  finalized_by_name?: string | null;
  test_order_id: number;
}

// Prompt 11: soft delete / audit log
export interface DeletedItem {
  id: number;
  kind: 'USER' | 'REFERRER' | 'TEST';
  title: string;
  subtitle?: string | null;
  deleted_at: string;
  deleted_by_id?: number | null;
  deleted_by_name?: string | null;
  delete_reason?: string | null;
}
export interface AuditLogItem {
  id: number;
  created_at: string;
  actor_id?: number | null;
  actor_name?: string | null;
  acting_role: string;
  action: string;
  domain: string;
  entity_type: string;
  entity_id: string;
  reason?: string | null;
  before_value?: string | null;
  after_value?: string | null;
}
export interface AuditLogPage { items: AuditLogItem[]; total: number; page: number; size: number; pages: number }
export interface AuditLogMeta {
  actions: string[];
  entity_types: string[];
  domains: { key: string; label: string }[];
  roles: string[];
  actors: { id: number; name: string }[];
}
export interface AuditLogQuery {
  action?: string; entity_type?: string; actor_id?: number; domain?: string; acting_role?: string; q?: string;
  date_from?: string; date_to?: string; page?: number; size?: number;
}

// Prompt 15 (D22): doctor sign-off
export interface DoctorRef {
  id: number;
  name: string;
  registration_no?: string | null;
  specialty?: string | null;
}

export interface ApprovalQueueItem {
  test_order_id: number;
  invoice_no: string;
  patient_name: string;
  patient_code: string;
  test_code: string;
  test_name: string;
  department?: string | null;
  lab_section_label?: string | null;
  approval_rule: 'DOCTOR_REQUIRED' | 'BOTH_SIGNATURES' | string;
  order_status: string;
  urgent: boolean;
  technician_name?: string | null;
  result_entered_at?: string | null;
  assigned_doctor?: DoctorRef | null;
}

export interface ApprovalQueue {
  scope: 'OWN' | 'ALL';
  my_doctor?: DoctorRef | null;
  items: ApprovalQueueItem[];
}

export interface ApprovalRecord {
  id: number;
  doctor: DoctorRef;
  approved_by_user_id: number;
  approved_by_name?: string | null;
  approved_by_role: string;
  is_attestation: boolean;
  notes?: string | null;
  approved_at: string;
}

export interface ApprovalDetail {
  test_order_id: number;
  approval_rule: string;
  order_status: string;
  path: 'DOCTOR_OWN' | 'STAFF_ATTESTATION';
  can_approve: boolean;
  blocked_reason?: string | null;
  technician_name?: string | null;
  technician_signed_at?: string | null;
  assigned_doctor?: DoctorRef | null;
  my_doctor?: DoctorRef | null;
  approval?: ApprovalRecord | null;
  preview: ResultPreview;
}

// Prompt 17 (Modules 17 / 18)
export interface CenterSettings {
  report_hold_when_due: boolean;
  writeoff_admin_limit: number;
  cash_variance_tolerance: number;
}

// Prompt 18 (Module 22): day screen (Admin/Owner)
export interface DayChannelLine {
  channel: string;
  opening: number;
  collections: number;
  refunds: number;
  paid_out: number;
  expected: number;
  counted: number | null;
  variance: number | null;
}

export interface DayScreen {
  day: null | {
    id: number;
    day_number: number;
    status: 'OPEN' | 'CLOSED' | 'REOPENED';
    opened_at: string;
    closed_at: string | null;
    opening_cash: number;
    counted_cash: number | null;
    variance: number | null;
    variance_reason: string | null;
    reopen_reason: string | null;
    reopened_at: string | null;
  };
  tolerance: number;
  unsynced_items: number;
  channels?: DayChannelLine[];
  cash?: {
    opening_cash: number;
    cash_collections: number;
    cash_refunds: number;
    bank_deposits: number;
    owner_withdrawals: number;
    expenses: number;
    adjusting_entries: number;
    deferred_payouts: Record<string, number>;
    expected_cash: number;
  };
  movements?: { id: number; kind: string; amount: number; note: string | null; created_at: string }[];
}

export interface JournalEntryRow {
  id: number;
  date: string;
  event: string;
  memo: string | null;
  business_day_id: number | null;
  reverses_entry_id: number | null;
  is_adjustment: boolean;
  lines: { account: string; debit: number; credit: number }[];
}

export interface DuesCallListInvoice {
  invoice_id: number;
  invoice_no: string;
  due: number;
  age_days: number;
  age_bucket: string;
}

export interface DuesCallListPatient {
  patient_id: number;
  patient_code: string;
  patient_name: string;
  patient_phone: string;
  total_due: number;
  invoice_count: number;
  oldest_age_days: number;
  age_bucket: string;
  invoices: DuesCallListInvoice[];
}

export interface DuesCallList {
  bucket_totals: Record<string, number>;
  total_due: number;
  patients: DuesCallListPatient[];
}

export interface WriteOffRecord {
  id: number;
  invoice_id: number;
  invoice_no?: string | null;
  patient_name?: string | null;
  amount: number;
  reason: string;
  status: 'APPLIED' | 'PENDING_OWNER' | 'REJECTED';
  admin_limit_at_request: number;
  requested_by_name?: string | null;
  requested_by_role: string;
  decided_by_name?: string | null;
  decided_at?: string | null;
  decision_note?: string | null;
  created_at: string;
  invoice_due_now?: number | null;
}

export interface DoctorBalanceRow {
  referrer_id: number;
  name: string;
  registration_no?: string | null;
  wholesale_receivable: number;
  professional_fee_payable: number;
  last_entry_at?: string | null;
}

export interface DoctorBalances {
  items: DoctorBalanceRow[];
  entry_count: number;
  note: string;
}
