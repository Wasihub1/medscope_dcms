# MedScope DCMS — Scope and Permissions Specification

## 1. System Mission & Product Purpose

MedScope is a multi-tenant Diagnostic Center Management System (DCMS) designed for medium-sized diagnostic centers in Bangladesh (such as upazila town centers with small staff and intermittent connectivity). It manages the entire clinical and operational lifecycle of a diagnostic center: patient registration, visit tracking, investigation billing, discount control, payments and dues settlement, pre-sample refund requests, workstation routing, specimen collection, laboratory result entry and verification, report delivery with financial hold gating, inventory, cashier day sessions, referral doctor commissions, double-entry accounting, and platform administration.

### Core Product Principles
1. **Money Never Changes Silently:** Bills, payments, financial ledgers, inventory deductions, and audit logs are append-only. Corrections require new ledger adjustments with mandatory audit justification.
2. **Catch, Do Not Block:** Front desk judgment calls (such as line discounts) are allowed within strict mathematical limits and reported, rather than blocking patients at intake counters.
3. **Small Center Optimization:** Support for merged staff roles, shared workstations with rapid PIN switching, and resilient offline queueing.
4. **Owner Visibility vs. Counter Secrecy:** Referral commission rates, doctor payout amounts, and test reagent cost prices are strictly confidential to the Owner/Admin. Technicians and receptionists never see reagent margins or referral commissions.
5. **Bilingual Intake:** Patient names, addresses, and clinical remarks accept both Bangla and English script.
6. **Strict Clinical Invariants:** Test cancellation or monetary refund is strictly forbidden once a laboratory specimen has been drawn (`sample.status == 'COLLECTED'`).

---

## 2. User Roles & Operational Boundaries

MedScope defines two levels of identity: **Tenant Staff** and **Platform Dev**.

### Tenant Roles
| Role | Primary Responsibility | Financial / Secret Visibility |
| :--- | :--- | :--- |
| **Owner** | Full executive and financial control across the center; manages staff, test catalog, referrers, commission percentages, and accounts. | Full visibility across all ledgers, revenues, profits, and referral commissions. |
| **Admin** | Operational supervisor; manages staff accounts, inventory, overrides due holds, approves refunds, and configures tests. | Full visibility into operations and billing; commission settings and owner accounts are restricted. |
| **Receptionist** | Front desk intake, invoice creation, discount processing, payment collection, workstation routing, pre-sample refund requests, and report delivery. | Counter visibility only (prices, discounts, receipts, dues). Referral commissions, doctor payouts, and test cost prices are completely hidden. Cannot close business day. |
| **Cashier** | Counter cash collection, invoice receipting, dues settlement, and drawer reconciliation. | Identical front-desk navigation and operational permissions as Receptionist. |
| **Lab Tech** | Laboratory workstation queues, specimen collection, result entry, test verification, and report authorization. | Clinical view only (test orders, specimens, reference ranges). All financial figures, prices, and payments are completely hidden. |

### Platform Developer (Platform Dev)
- Platform-level superuser distinct from tenant roles.
- Enters Master ID, password, and TOTP at platform login.
- Governs multi-tenant provisioning, database migration execution, and global health monitoring.
- Can enter any tenant in a supervised session; all actions are permanently logged in the tenant's audit trail under the Developer's identity.

---

## 3. Implemented Permissions Matrix

| Capability | Owner | Admin | Receptionist | Cashier | Lab Tech | Platform Dev |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dashboard View** | Executive | Operational | Front Desk | Front Desk | Laboratory | Platform Registry |
| **Patient Registration & Search** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Patient History & Timeline** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Invoice Creation & Billing** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Individual Line Discount (up to test price)** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Master Invoice Discount** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Payment Collection & Receipts** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Reprint Money Receipts (Watermarked)** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Dues Collection & Settlement** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Workstation Order Assignment** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Technician Worklist (My Work)** | Yes | Yes | No | No | **Yes (Own Tasks)** | Yes (Tenant Mode) |
| **Quick Route Sample Collection** | Yes | Yes | No | No | **Yes** | Yes (Tenant Mode) |
| **Pre-Sample Refund Request** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Approve / Reject Refund Request** | Yes | Yes | **No (403)** | **No (403)** | No | Yes (Tenant Mode) |
| **Sample Collection** | Yes | Yes | No | No | Yes | No |
| **Result Entry & Verification** | Yes | Yes | No | No | Yes | No |
| **Report Authorization** | Yes | Yes | No | No | Yes | No |
| **Report Delivery (Without Due)** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Report Delivery (Due Hold Override)** | Yes | **Yes (Reason Req)** | **No (Locked)**| **No (Locked)**| No | Yes (Tenant Mode) |
| **Print Authorized Reports** | Yes | Yes | Yes | Yes | Yes | Yes (Tenant Mode) |
| **Business Day Open** | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Business Day Close** | Yes | Yes | **No (403)** | **No (403)** | No | Yes (Tenant Mode) |
| **Manage Test Catalog & Prices** | Yes | Yes | No | No | No | Yes (Tenant Mode) |
| **Manage Referrers** | Yes | Yes | No | No | No | Yes (Tenant Mode) |
| **Manage Referral Commissions** | **Yes** | **No** | **No** | **No** | No | No |
| **Manage Staff Accounts** | Yes | Yes (Non-Owner)| No | No | No | Yes (Platform) |
| **Inventory Management** | Yes | Yes | View Only | View Only | Use Only | Yes (Tenant Mode) |
| **Financial Accounting Ledgers** | Yes | No | No | No | No | Yes (Tenant Mode) |
| **Audit Logs & Reprint History** | Yes | Yes | No | No | No | Yes (Tenant Mode) |

---

## 4. Operational Boundaries & Security Constraints

### 4.1 Commission and Margin Secrecy
- The backend API filters out `commission_rate`, `commission_amount`, and `cost_price` whenever an endpoint is accessed by a `RECEPTIONIST`, `CASHIER`, or `LAB_TECH` actor role.
- Database queries executed under front-desk contexts omit referrer financial ledgers.

### 4.2 Cash Control & Business Day Lifecycle
- Each tenant operates under a single active business day (`status = 'OPEN'`) at any given time, enforced by the partial unique index `idx_business_day_single_open`.
- Receptionists can initialize the morning business day by entering the opening float.
- Receptionists are strictly prohibited from closing the business day (`POST /business-day/close` returns HTTP 403 Forbidden). Day closure requires an Owner or Admin PIN to reconcile physical drawer cash against recorded system receipts.

### 4.3 Pre-Sample Refund State Machine
- Receptionists can initiate a refund request for an invoice line only while the sample has not yet been collected.
- Attempting to submit a refund for a collected sample fails with HTTP 400 Bad Request.
- Once submitted, the refund enters `PENDING_ADMIN_APPROVAL`. Receptionists cannot approve their own refund requests (HTTP 403 Forbidden). An Admin or Owner must review, log justification, and authorize the disbursement.

### 4.4 Report Delivery Due Hold
- Finalized diagnostic reports with unpaid invoice balances are held under automated financial lock (`is_held_due_to_balance == True`).
- Front desk staff cannot hand over the report until the patient settles the due balance at the counter or an Administrator authorizes release with a recorded clinical/administrative justification.

### 4.5 Two Independent Referral Fields (Prescriber vs Referrer)
- Invoices persist two separate, independent relationships:
  1. `prescribed_by_id`: References a medical Doctor (`type = 'Doctor'`) who wrote the clinical prescription.
  2. `referrer_id`: References a Doctor or commercial Third Party (Agent, Broker, Partner Clinic).
- Both fields support inline addition during intake without clearing entered patient or investigation data. Both are optional for walk-in patients.

### 4.6 Confidential Write-Only Commission Setup
- During inline doctor or referrer creation at the front desk, an initial `commission_rate` (0-100%) and `commission_type` may be entered.
- The stored rate is strictly write-only: all read endpoints (`GET /referrers`, search, detail, and creation responses) omit commission fields so the counter cannot inspect existing rates, payout histories, or ledger balances.

### 4.7 Two-Stage Invoice Creation Flow & Dual-Copy Print
- The invoice entry flow operates in two distinct stages:
  `Form Entry -> Generate Preview (Non-Final) -> Back & Correct OR Save [and Print] -> Persist -> Dual-Copy Print`.
- Generating a preview does NOT assign a permanent invoice number or persist financial rows.
- Clicking `Back & Correct` returns to the form with 100% of entered state intact.
- Final save commits the invoice atomically. The form resets to a clean state with Paid Amount = ৳0 only after persistence succeeds.
- Dual-Copy print renders **Patient Copy** and **Office / Lab Copy** side-by-side on A4 landscape.

### 4.8 Standardized Payment and Separate Refund Status Presentation
- **Payment Status:**
  - Zero paid (`paid_amount == 0` or `UNPAID` / `DUE`): Displayed as **Unpaid**.
  - Partially paid (`paid_amount > 0` and `due_amount > 0`): Displayed as **Partial Due**.
  - Fully paid (`due_amount == 0`): Displayed as **Paid**.
- **Refund Status (Separate Column):**
  - Dynamically computed from pre-sample cancellation requests: `No Refund`, `Refund Pending`, `Partially Refunded`, `Fully Refunded`, or `Refund Rejected`. Distinguishes pending approval from money actually disbursed.

### 4.9 Strict Financial Data Isolation for Technicians (Module 11)
- Laboratory Technicians operate exclusively on clinical data: patient identifiers, investigation type, specimen condition, turnaround clocks, and status.
- All financial attributes (unit price, line discount, master discount, net payable, amount paid, due balance, referrer commission, and reagent cost price) are strictly removed from API response payloads (`TechnicianWorklistItemResponse`).
- A technician cannot view another technician's tasks by altering query parameters or URLs; access is bounded to `assigned_to_id == actor.id`.
- Visiting doctor investigations (such as Ultrasound) are placed into `AWAITING_DOCTOR` queue until the visiting specialist performs the scan.

### 4.10 Specimen Lifecycle, Line Locking, and Rejected Sample Workflow (Module 12)
- **Line Lock at Specimen Collection:** When a biological sample is collected (or an imaging examination is performed), `InvoiceLine.is_locked = True`. Ordinary pre-sample cancellation and counter refunds are strictly blocked under the D15 invariant rule.
- **Spoiled / Rejected Specimen Workflow:** Authorized technicians can record an unsuitable or spoiled sample with a mandatory clinical reason. The order and sample transition to `REJECTED` or `SPOILED`.
- **Patient Follow-up Requirement:** The patient is marked for telephone follow-up. If the patient agrees to recollection, a new invoice line and new sample ID are required (no free re-runs). If the patient requests a refund, it follows the Not Performed Admin/Owner refund exception.
- **Department-Specific Extensions:**
  - Imaging lines lock at scan execution (`PERFORMED`), not at sample collection.
  - Culture tests progress through `INCUBATING`, `PRELIMINARY`, and `FINAL` stages.
  - Outside laboratory referrals track `SENT` and `RECEIVED` with external reference numbers.
- **Stock Boundary:** Sample lock triggers an integration event for reagent deduction; complete batch and reagent inventory management is deferred to Module 16.

### 4.11 Clinical Result Entry & Data Verification (Module 13)
- **Three Template Formats:**
  1. `NUMERIC_TABLE`: Structured component grid with units, reference ranges, live flag badges (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`), and impossible-value limits. Delta visual indicators are excluded by D25.
  2. `NARRATIVE`: Free-text reporting with Technique, Findings, Impression, and Recommendations.
  3. Structured `ULTRASOUND`: Organ-by-organ reporting (Liver, Gallbladder, Spleen, Pancreas, Kidneys, Bladder, Pelvic Organs) with consolidated Impression.
- **Automatic Flag Mechanics:**
  - Evaluates numeric component values against configured reference bounds: `LOW`, `HIGH`, `CRITICAL`, `NORMAL`.
  - Automatic flags are **kept** (superseding earlier drop discussions); technicians **cannot** select or override flags (computed deterministically by the system).
  - Safe `None` Fallback: Incomplete or missing reference ranges NEVER silently default to NORMAL; flag remains `None`. Automatic critical-result alerts remain excluded.
- **Physiological Impossible-Value Rejection:**
  - Absurd inputs outside physiological viability limits (e.g., Hemoglobin `2.0 - 25.0 g/dL`) are immediately rejected with HTTP 400 Bad Request.
- **Reference Range Snapshot Invariant (D24):**
  - Result entry permanently snapshots reference intervals and units into `result_items` at the time of entry to prevent historical reports from drifting when catalog values are updated. (Sex/age-band dynamic versioning is deferred).
- **Strict Module 14 Boundary (Exclusions):**
  - Module 13 strictly handles data entry and draft/entered saving.
  - Excluded and deferred to Module 14: Doctor digital approval signatures, report finalization, multi-specialist verification, public authenticity QR codes, and report printing/handover.

### 4.12 Module 12 Corrections & Fix Invariants (FIX 1 – FIX 4)
- **FIX 1 (Line Lock UI Decoupling):** Removed the `Line Locked` badge from Technician Worklist and Specimen Lifecycle UI to eliminate technician distraction, while preserving 100% of backend line-lock restrictions and financial audits.
- **FIX 2 (STAT Urgent Badge Persistence):** The STAT `URGENT` badge remains visible across all intermediate order states (`SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `REJECTED`, `SPOILED`) and is removed only upon authoritative task completion (`COMPLETED`).
- **FIX 3 (Authoritative Sample Status in Invoices):** Replaced undefined client-side evaluation with authoritative backend `sample_status` badges (`COLLECTED`, `REJECTED`, `SPOILED`, `PERFORMED`, `AWAITING COLLECTION`).
- **FIX 4 (D15 Not Performed Refund Exception & Disbursal):**
  - Unsuitable or spoiled specimens transition to `outcome = "NOT_PERFORMED"` under the D15 exception.
  - Technicians can submit a D15 refund request directly from the worklist (`request_type = "D15_NOT_PERFORMED"`, `status = "PENDING_ADMIN_APPROVAL"`).
  - Invoices view displays D15 status on the affected line and blocks generic pre-sample cancellation on locked lines.
  - Two-Stage Refund Separation: Admin approval marks the request `APPROVED` and invoice `REFUND_APPROVED`; money disbursement is separate and performed by the Cashier/Admin, recording the payout channel (`CASH`, `BKASH`, `NAGAD`, etc.), drawer deduction, and reversing referral commissions.

### 4.13 Prompt 07C Safety, Correctness, and Product Governance Invariants
- **Original Payment Channel Enforcement (Fix 1 / Rules 3.1, D18, M29):**
  - Refund disbursement is strictly restricted to payment methods actually recorded on the invoice. Non-cash refunds require mandatory transaction reference numbers. Per-channel disbursements cannot exceed the net amount received on that channel.
- **Segregation of Duties on Refund Approvals (Fix 2 / Rule 3.6, D56):**
  - Self-approval is blocked by default (`reviewer_id == requested_by_id` returns HTTP 403 Forbidden with audit row `REFUND_SELF_APPROVAL_BLOCKED`).
  - Isolated in `enforce_segregation_of_duties` for future customer configuration ("Small Center Mode").
  - Day open/close roles and who may disburse approved refunds are not permanently fixed: current settings are development defaults; a single centralized, configurable role-permission layer is planned. Only Admin/Owner approve refunds.
- **Culture Lifecycle Decoupling (Fix 3 / Rule D19, M12):**
  - Moving culture stage to `FINAL` does not auto-complete the order; culture order completion requires normal result entry and verification after reaching the `FINAL` stage.
- **Result-Save Guards (Fix 4 / Rules 3.2, D24, M13, B10):**
  - Modifying or resaving results on a `COMPLETED` order is rejected with HTTP 409 Conflict.
  - Saving a `DRAFT` result does not advance order status (order remains in current state, e.g. `IN_PROGRESS` or `SAMPLE_PENDING`).
  - Sample-based investigations reject saving results prior to specimen collection with HTTP 409 Conflict.
- **Technician Financial Data Isolation (Fix 5 / Rule M11.3, 3.8):**
  - Technician D15 refund requests return `D15RefundClinicalResponse` omitting amount, price, and refund values.
  - Historical and runtime order lifecycle events are sanitized to redact monetary amounts (`Tk` and `৳`) for `LAB_TECH` callers.

### 4.14 Prompt 08 Operational Invariants & Integrity Boundaries
- **In-Place Modal Overlay Pattern:**
  - Navigating from within an invoice detail or sub-view to inspect patient history must never alter the browser route (`/invoices`), unmount background components, or discard table search/status filters and scroll position.
  - Encapsulated within `PatientHistoryModal` and presented as an in-place modal overlay.
- **Strict Test Database Isolation:**
  - Automated testing is strictly barred from touching the primary operational database (`medscope_dcms`).
  - Pytest runs against `medscope_test` with a hard safety guard rejecting any target resolving to `medscope_dcms`.
- **Read-Only Test Record Identification & Backup:**
  - Forensic inspection of test records in `medscope_dcms` is strictly read-only; no automated or manual deletions may occur without a verified offline backup and explicit approval.

### 4.15 Real Role-Based Authentication & Multi-Role Governance (Prompt 09)
- **Multi-Role Assignment per Person (Rule M1.1):**
  - A staff member may hold multiple operational roles simultaneously (e.g. `RECEPTIONIST` and `CASHIER`, or `ADMIN` and `OWNER`), persisted in `staff_roles`.
  - Permissions are strictly validated against the user's active acting role within their authenticated session.
- **Acting Role Attribution on Every Action (Rule D57):**
  - All audit log events and operational records persist the user's current `acting_role`.
  - Multi-role users can switch acting role within their active session via `POST /api/v1/auth/acting-role`. Attempting to act in an unheld role is strictly rejected with HTTP 403 Forbidden.
- **Brute-Force Account Lockout (Rules M1, D58):**
  - 5 consecutive failed password attempts trigger automated account lockout (`locked_at = utc_now()`).
  - Locked accounts are barred from authentication (HTTP 403 Forbidden) across all channels until explicitly unlocked by an Admin or Owner.
- **Permanent Removal of Development Role Switcher:**
  - Header-based role spoofing (`X-Staff-Id`, `X-Staff-Role`) is completely eliminated.
  - All protected endpoints strictly mandate an active, cryptographically hashed server-side session.
- **Role-Based Workstation Landing Routes:**
  - `RECEPTIONIST` / `CASHIER` -> `/invoices` (Intake and billing counter)
  - `LAB_TECH` -> `/worklist` (Technician workbench with financial isolation)
  - `ADMIN` / `OWNER` -> `/dashboard` (Executive center dashboard)

### 4.16 Public Entry Surface, Role-Based Route Gating & Brand Standards (Prompt 10)
- **Public Entry Point Isolation:**
  - Route `/` serves as the public branded marketing and overview surface for prospective clients and staff.
  - Route `/login` serves as the public workstation gateway.
  - Route `/dashboard` serves as the authenticated operational dashboard for authorized staff.
- **Signed-In User Redirection:**
  - Authenticated staff opening `/` or `/login` are automatically redirected to their role's home route (`/invoices` for Receptionist/Cashier, `/worklist` for Lab Tech, `/dashboard` for Admin/Owner).
- **Clinical Privacy & Decorative Invariants:**
  - Public marketing illustrations (ECG line, sample tube, progress dot) are strictly decorative; zero real or fabricated patient data, test numbers, prices, or doctor names may appear on public surfaces.
- **Extensible Workflow Strip:**
  - The workflow stages marquee strip is driven by a data array (`WORKFLOW_STEPS`), allowing center leadership to append or reorder clinical operational phases without modifying presentation markup.
- **Accessible & Self-Hosted Typography:**
  - Typography is 100% self-hosted (`@fontsource/manrope`, `@fontsource/noto-sans-bengali`); zero external CDN or Google Fonts calls.
  - Respects `@media (prefers-reduced-motion: reduce)` by disabling animations and presenting static resting states.




