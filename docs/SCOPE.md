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
| **Cashier** | Counter cash collection, invoice receipting, dues settlement, and drawer reconciliation. | Own explicit default permission set (`backend/app/core/permissions.py`). Prompt 10E: equal to the Receptionist set — `report.release_with_due` was removed, so a Cashier can no longer release a report while a due exists. Can diverge per user via overrides. |
| **Lab Tech** | The worklist of **their lab room** (Prompt 10E: every technician of a room sees all of the room's orders), specimen collection, result entry; own My Profile (Prompt 10E). Must belong to exactly one room. | Clinical view only (test orders, specimens, reference ranges). All financial figures, prices, and payments are completely hidden; money permissions can never be granted. |
| **Doctor** (Prompt 10E) | Visiting doctor / radiologist: the doctor queue (Awaiting Doctor orders from all rooms) and the related results; completes doctor-routed tests through the existing status action; **approves its own assigned results on the Doctor Sign-off screen (Prompt 15)**; own My Profile. No lab room. | Money-restricted exactly like Lab Tech: no invoicing, payment, refund or business-day access; money permissions can never be granted. |

### Platform Developer (Platform Dev)
- Platform-level superuser distinct from tenant roles.
- Enters Master ID, password, and TOTP at platform login.
- Governs multi-tenant provisioning, database migration execution, and global health monitoring.
- Can enter any tenant in a supervised session; all actions are permanently logged in the tenant's audit trail under the Developer's identity.

---

## 3. Implemented Permissions Matrix

> **Prompt 10D:** every row below is enforced by the central permission layer (`backend/app/core/permissions.py`): each route requires a named permission key, role defaults reproduce this matrix, and an Owner/Admin can add or remove individual permissions per user (User Management, `/users`). Money permissions can never be granted to LAB_TECH or DOCTOR. Only an Owner can create, modify or assign the Owner role. **Prompt 10E:** Doctor column added; technician worklists are room based; CASHIER no longer releases reports with a due; LAB_TECH has My Profile; `worklist.reassign` (Admin/Owner) added. **Prompt 10F:** Assigned Tests view (view only for Receptionist/Cashier, reassign for Admin/Owner); Ready Results on `/reports` for the front desk; no new permission key (35).

| Capability | Owner | Admin | Receptionist | Cashier | Lab Tech | Doctor | Platform Dev |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dashboard View** | Executive | Operational | Front Desk | Front Desk | Laboratory | Doctor (money-free) | Platform Registry |
| **Patient Registration & Search** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Patient History & Timeline** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Invoice Creation & Billing** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Individual Line Discount (up to test price)** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Master Invoice Discount** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Payment Collection & Receipts** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Reprint Money Receipts (Watermarked)** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Dues Collection & Settlement** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Dues write-off (bad debt) and doctor balances** | Yes (write-off up to the limit; Owner above it) | Yes | No | No | No | No | Yes (Tenant Mode) |
| **Workstation Order Assignment** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Technician Worklist (My Work)** | Yes | Yes | No | No | **Yes (Own Room)** | **Doctor queue** | Yes (Tenant Mode) |
| **Quick Route Sample Collection** | Yes | Yes | No | No | **Yes** | No | Yes (Tenant Mode) |
| **Cancel unlocked line / whole invoice (pre-lock, no approval; payout is a separate step)** (see §8) | Yes | Yes | **Yes (narrow, see §8)** | **Yes (narrow, see §8)** | No | No | Yes (Tenant Mode) |
| **Approve / Reject Refund Request** (D15 "Not Performed" requests) | Yes | Yes | **No (403)** | **No (403)** | No | No | Yes (Tenant Mode) |
| **Sample Collection** | Yes | Yes | No | No | Yes | No | No |
| **Result Entry & Verification** | Yes | Yes | No | No | Yes | Doctor-routed | No |
| **Report Authorization** | Yes | Yes | No | No | Yes | No | No |
| **Report Delivery (Without Due)** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Report Delivery (Due Hold Override)** | Yes | **Yes (Reason Req)** | **No (Locked)**| **No (Locked)**| No | No | Yes (Tenant Mode) |
| **Print Authorized Reports** | Yes | Yes | Yes | Yes | Yes | No | Yes (Tenant Mode) |
| **Business Day Open** | Yes | Yes | Yes | Yes | No | No | Yes (Tenant Mode) |
| **Reassign Order to Another Room (until Completed)** | Yes | Yes | No | No | No | No | Yes (Tenant Mode) |
| **Assigned Tests view (Assign Tests page, 10F)** | Yes (reassign) | Yes (reassign) | View only | View only | No | No | Yes (Tenant Mode) |
| **Ready Results list + Preview (`/reports`, 10F)** | Yes (with due) | Yes (with due) | Yes (with due) | Yes (with due) | No | No | Yes (Tenant Mode) |
| **Preview of a saved result in My Work (10F)** | Yes | Yes | No | No | Yes (Own Room) | Doctor queue | Yes (Tenant Mode) |
| **My Profile (own record)** | Yes | Yes | Yes | Yes | Yes | Yes | No |
| **Business Day Close** | Yes | Yes | **No (403)** | **No (403)** | No | No | Yes (Tenant Mode) |
| **Manage Test Catalog & Prices** | Yes | Yes | No | No | No | No | Yes (Tenant Mode) |
| **Manage Referrers** | Yes | Yes | No | No | No | No | Yes (Tenant Mode) |
| **Manage Referral Commissions** | **Yes** | **No** | **No** | **No** | No | No | No |
| **Manage Staff Accounts** | Yes | Yes (Non-Owner)| No | No | No | No | Yes (Platform) |
| **Inventory Management** | Yes | Yes | View Only | View Only | Use Only | No | Yes (Tenant Mode) |
| **Financial Accounting Ledgers** | Yes | No | No | No | No | No | Yes (Tenant Mode) |
| **Audit Logs & Reprint History** | Yes | Yes | No | No | No | No | Yes (Tenant Mode) |

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
- **Refund amount (Prompt 10E):** cancelling a line gives `refund = max(0, retained_paid − net_after)` where `net_after` = invoice net without that line (never below the urgent fee) and `retained_paid` = paid − refunds already approved/disbursed; the remaining `due = max(0, net_after − (retained_paid − refund))`. A refund and a due never coexist; refunds never exceed what was paid; the server computes the amount (client amounts are ignored).
- **Pre-lock path (the only one):** Receptionist, Cashier, Admin and Owner use **Cancel Test** on one **unlocked** test line of a Confirmed invoice, or **Cancel Whole Invoice** (every remaining line together, only when **no** line is locked; if any is locked the whole action is refused with 409 and nothing changes). The refund amount is **never typed**: the modal shows the system's read-only breakdown (invoice total, paid so far, line price, amount retained, refund amount, new due; for the whole invoice the per-line refunds and totals). **There is no approval step** (§8): the cancellation takes effect at once. **Cancelling never pays money out:** the refund record is left `APPROVED` (refund due, awaiting payout) or `COMPLETED` when the amount is 0, and paying out is always its own deliberate step (`refund.disburse`) with its own amount and channel confirmation. Reason is optional. A second cancellation of the same line is refused (409).
- **Boundary at the lock event:** once the sample is taken (or rejected/spoiled, or a no-sample test completes) the line is locked. A cancellation of a locked line is refused with HTTP 409 `SAMPLE_ALREADY_TAKEN` and the UI shows the "Sample already taken" dialog: cancellation then follows the **D15 "Not Performed"** path (Lab Tech submits, Admin/Owner approve). A refund request that is already pending Admin/Owner approval can still be approved (reason required) or rejected, and cannot be approved after the sample was taken (409).
- Receptionists cannot approve their own refund requests (HTTP 403). An Admin or Owner must review, log justification, and authorize the disbursement.

### 4.4 Report Delivery Due Hold
- Finalized diagnostic reports with unpaid invoice balances are held under automated financial lock (`is_held_due_to_balance == True`).
- Front desk staff cannot hand over the report until the patient settles the due balance at the counter or an Administrator authorizes release with a recorded clinical/administrative justification.
- Prompt 10E: RECEPTIONIST **and CASHIER** are blocked (403, even with a reason); only `report.release_with_due` holders (Admin/Owner by default) may release, and the override reason is required.

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
- A technician cannot view another room's orders by altering query parameters or URLs; access is bounded to the technician's room (`test_orders.lab_section == staff.lab_section`, Prompt 10E; before 10E it was `assigned_to_id == actor.id`). A DOCTOR is bounded to the doctor queue.
- Visiting doctor investigations (such as Ultrasound) are placed into `AWAITING_DOCTOR` queue until the visiting specialist performs the scan.

### 4.10 Specimen Lifecycle, Line Locking, and Rejected Sample Workflow (Module 12)
- **Line Lock (Prompt 12):** a sample-based test locks when its sample is collected; a test that needs no sample (imaging included) locks at **result completion**, not at `IMAGING_PERFORMED`. `InvoiceLine.is_locked = True`. Ordinary pre-sample cancellation and counter refunds are strictly blocked under the D15 invariant rule.
- **Spoiled / Rejected Specimen Workflow:** Authorized technicians can record an unsuitable or spoiled sample with a mandatory clinical reason. The order and sample transition to `REJECTED` or `SPOILED`.
- **Patient Follow-up Requirement:** The patient is marked for telephone follow-up. If the patient agrees to recollection, a new invoice line and new sample ID are required (no free re-runs). If the patient requests a refund, it follows the Not Performed Admin/Owner refund exception.
- **Department-Specific Extensions:**
  - Imaging lines (Prompt 12, supersedes the older "lock at scan execution" rule and the "imaging started, not completed" approval exception): `PERFORMED` is only a status label; the line locks at result completion; cancelling before that is the ordinary unlocked-line path. The owner same-day unlock (D14) applies to every locked line, imaging included.
  - Culture tests progress through `INCUBATING`, `PRELIMINARY`, and `FINAL` stages.
  - Outside laboratory referrals track `SENT` and `RECEIVED` with external reference numbers.
- **Stock Boundary:** Sample lock triggers an integration event for reagent deduction; complete batch and reagent inventory management is deferred to Module 16.

### 4.11 Clinical Result Entry & Data Verification (Module 13)
- **Three Template Formats:**
  1. `NUMERIC_TABLE`: Structured component grid with units, reference ranges, live flag badges (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`), and impossible-value limits. Delta visual indicators are excluded by D25.
  2. `NARRATIVE`: Free-text reporting with Findings, Impression, and Comments (`results.findings`, `results.impression`, `results.comments`).
  3. Structured `ULTRASOUND`: Organ-by-organ reporting (Liver, Gallbladder, Spleen, Pancreas, Kidneys, Bladder, Pelvic Organs) with consolidated Impression.
- **Automatic Flag Mechanics:**
  - Evaluates numeric component values against configured reference bounds: `LOW`, `HIGH`, `CRITICAL`, `NORMAL`.
  - Automatic flags are **kept** (superseding earlier drop discussions); technicians **cannot** select or override flags (computed deterministically by the system).
  - Safe `None` Fallback: Incomplete or missing reference ranges NEVER silently default to NORMAL; flag remains `None`. Automatic critical-result alerts remain excluded.
- **Physiological Impossible-Value Rejection:**
  - Absurd inputs outside physiological viability limits (e.g., Hemoglobin `2.0 - 25.0 g/dL`) are immediately rejected with HTTP 400 Bad Request.
- **Reference Range Snapshot Invariant (D24):**
  - Result entry permanently snapshots reference intervals and units into `result_items` at the time of entry to prevent historical reports from drifting when catalog values are updated. Ranges and critical limits are versioned by sex and age band in days (§9); the snapshot records which band version was used.
- **Strict Module 14 Boundary (Exclusions):**
  - Module 13 strictly handles data entry and draft/entered saving.
  - Built in Module 14 (Prompt 16, section 11): Draft to Final, per-test finalization, immutable Final content, the Issued Reports view. Still excluded: signature image / seal upload, report printing / PDF, multi-specialist verification, public authenticity QR codes, corrections (Module 15) and real SMS (Module 25).

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
- **One Login = One Fixed Role (Prompt 10D; supersedes the Prompt 09 multi-role rule M1.1):**
  - Each staff member holds exactly one role (`staff_roles` has one row per user, constraint `uq_staff_roles_staff_id`). The former dual-role accounts were split into `reception_fatima` + `cashier_fatima` and `admin_tariq` + `owner_tariq`.
  - Permissions are validated against that role's defaults plus any per-user overrides.
- **Acting Role Attribution on Every Action (Rule D57):**
  - All audit log events and operational records persist the user's role (`acting_role` always equals the single role).
  - Acting-role switching was removed in Prompt 10D (`POST /api/v1/auth/acting-role` no longer exists; a login asking for another role gets HTTP 403).
- **Brute-Force Account Lockout (Rules M1, D58):**
  - 5 consecutive failed password attempts trigger automated account lockout (`locked_at = utc_now()`).
  - Locked accounts are barred from authentication (HTTP 403 Forbidden) across all channels until explicitly unlocked by an Admin or Owner.
- **Permanent Removal of Development Role Switcher:**
  - Header-based role spoofing (`X-Staff-Id`, `X-Staff-Role`) is completely eliminated.
  - All protected endpoints strictly mandate an active, cryptographically hashed server-side session.
- **Landing Route (Prompt 10D; replaces the per-role landing routes):**
  - Every role lands on `/dashboard`. Front desk, Admin and Owner see the financial dashboard; LAB_TECH sees a money-free laboratory view. Each role gets a link to its main work page (Invoices, My Worklist, User Management).

### 4.16 Public Entry Surface, Role-Based Route Gating & Brand Standards (Prompt 10)
- **Public Entry Point Isolation:**
  - Route `/` serves as the public branded marketing and overview surface for prospective clients and staff.
  - Route `/login` serves as the public workstation gateway.
  - Route `/dashboard` serves as the authenticated operational dashboard for authorized staff.
- **Signed-In User Redirection:**
  - Authenticated staff opening `/` or `/login` are redirected to `/dashboard` (Prompt 10D: every role).
- **Clinical Privacy & Decorative Invariants:**
  - Public marketing illustrations (ECG line, sample tube, progress dot) are strictly decorative; zero real or fabricated patient data, test numbers, prices, or doctor names may appear on public surfaces.
- **Extensible Workflow Strip:**
  - The workflow stages marquee strip is driven by a data array (`WORKFLOW_STEPS`), allowing center leadership to append or reorder clinical operational phases without modifying presentation markup.
- **Accessible & Self-Hosted Typography:**
  - Typography is 100% self-hosted (`@fontsource/manrope`, `@fontsource/noto-sans-bengali`); zero external CDN or Google Fonts calls.
- **Motion (current behavior):**
  - There is **no** `@media (prefers-reduced-motion: reduce)` fallback. It was removed on purpose in Prompt 10 so that the landing and login animations still run on Windows machines with animations disabled, where the old fallback froze the ECG line and broke the marquee. The owner has not yet decided on a "Pause animations" control.

### 4.17 Prompt 10E Invariants (rooms, samples, invoice payload, channels, urgent fee)
- **Room-based routing:** a test order is routed to a lab room, never to one technician; every active LAB_TECH of the room sees and works it; `assigned_to_id` only records who acted. Rooms with no active technician hold orders as UNASSIGNED (visible to Admin/Owner) until a technician joins (automatic release, audited). Admin/Owner (`worklist.reassign`, grantable) can move an order to another room until it is COMPLETED. The Assign Tests page routes UNASSIGNED orders to a room and never stores destination ids.
- **Sample rule (10E, superseded by §4.18):** one helper decides whether a sample is required; under 10E imaging tests and tests whose `sample_type` was empty/"None"/"N/A" never blocked on a sample.
- **Visit age and gender:** required to Finalize (a draft may omit them); infants in months or days; no default age or gender.
- **Payment channels:** CASH, BKASH, NAGAD, ROCKET, POS_CARD ("Card"), BANK_TRANSFER, OTHER (typed name required and stored on the payment).
- **Urgent fee:** computed only by the backend (`max(100, round(20% of the line price))` per urgent line), never discounted, never refunded on cancellation.

### 4.18 Prompt 10F Invariants (owner findings #1–#3, decisions A5 and A11)
- **Assigned Tests (F1):** the Assign Tests page has an **Assigned Tests** tab listing every test order with room, the room's active technicians or UNASSIGNED, status, urgent flag and created time; money-free. Receptionist/Cashier: view only (backend refuses reassign with 403). Admin/Owner (`worklist.reassign`): Reassign Room on rows not COMPLETED, cancelled or Not Performed; the backend refuses those with 409. One reassign endpoint (`POST /worklist/{id}/reassign`) with reason, append-only history and audit.
- **Ready (F3, owner expectation):** a result is Ready when it is submitted (`ENTERED`, not DRAFT) and the order is not cancelled, not Not Performed (rejected/spoiled) and not Awaiting Doctor. Operational Complete is **not** required. One backend definition feeds the Lab tile count, the Lab Ready tab and the sidebar Ready Reports list. Ready is not an issued report (no `report_versions` row); a result with a Final report is Issued, not Ready (section 11).
- **Preview (F2):** any order with a saved result (DRAFT or ENTERED) offers Preview Report right after save; a DRAFT preview is marked "DRAFT, not a final report". The preview is read-only, money-free and uses the stored result snapshots. No print, finalize, signature, QR or SMS.
- **Sample rule (F4, owner decision A5):** imaging tests (Ultrasonography room, USG/X-ray/radiology/imaging departments, narrative template) never need a sample; an explicit `None`/`N/A`/`NA`/`No sample` means no sample; **NULL or empty `sample_type` on any other test means a sample is required**. Result save (draft and submit), result entry, Complete, culture stage and outsourced dispatch are refused until Sample Taken. Catalog data is not changed by the system; the owner fills `sample_type`.
- **Empty room (F5, owner decision A11 "Unassigned thakbe"):** when a room loses its last active technician (deactivate, room change, role change, CLI role change), its orders that are only ASSIGNED (no sample, no result, no culture/outsourced step) become UNASSIGNED and stay visible to Admin/Owner; orders with any progress keep their state. Adding a technician releases them again. Audited per order, in the same transaction as the user change.

---

## 5. Owner Decisions (Prompt 10C) — Status after Prompt 10F

Decision log entries: `docs/ARCHITECTURE.md` ADL-032 to ADL-039 (10C/10D), ADL-040 to ADL-047 (Prompt 10E) and ADL-048 to ADL-051 (Prompt 10F).

| # | Decision | Status |
| :-: | :--- | :--- |
| 1 | **One login = one fixed role.** No acting-role switching (supersedes ADL-028). | **Implemented (10D).** Switcher and `/auth/acting-role` removed; dual-role accounts split. |
| 2 | **Every login lands on the Dashboard.** | **Implemented (10D).** Role-safe dashboard; LAB_TECH sees no money. |
| 3 | **More roles and users;** one default LAB_TECH per lab section/room. | **Implemented (10D).** Roles kept in one place (`ROLES`; DOCTOR added in 10E = six roles); `cashier_fatima`, `owner_tariq`, `tech_micro`, `tech_usg` created; rooms Hematology (Room 101), Biochemistry (Room 102), Microbiology (Room 105), Ultrasonography (Room 204). Since 10E routing is by room (ADL-041). |
| 4 | **"Create User" tab** with role assignment and per-user permission add/remove (first step of the central permission layer). | **Implemented (10D).** `/users` page and `/api/v1/users` endpoints; central layer ADL-038. |
| 5 | **Invoice Draft / Finalize.** | **Implemented (10D).** "Save Draft" + "Finalize"; invoice number assigned at Finalize. |
| 6 | **D15 refund logic fix.** | **Implemented (10D), rule replaced in 10E (ADL-040):** `refund = max(0, retained paid − net after cancellation)`; never with a due; never more than paid. |
| 7 | **Work order:** Prompt 10B related work, then Prompt 11 (soft delete, deactivate with confirm dialogs). | Prompt 11 **implemented** (soft delete, draft discard, confirm dialogs, audit viewer; see §6). |
| 8 | **A5 (10E risk), owner decision in 10F:** NULL `sample_type` = unknown = sample required; the owner fills the catalog himself. | **Implemented (10F, ADL-050).** No catalog data changed. |
| 9 | **A11 (10E risk), owner decision in 10F "Unassigned thakbe":** an emptied room's assigned orders become UNASSIGNED. | **Implemented (10F, ADL-051).** Only assigned-only orders; progress kept. |
| 10 | **Owner findings #1–#3 (10F):** Assigned Tests view; Preview after save; Ready Reports must fill. | **Implemented (10F, ADL-048/049).** Owner browser acceptance pending. |

### 5.1 Routing — implemented behavior and remaining gaps (Prompt 10E, updated 10F)
- **Implemented (ADL-041):** tests map to rooms through one mapping (`backend/app/core/lab_sections.py`; `tests.lab_section`); orders are routed to the room at Finalize; every technician of the room sees them; empty rooms hold UNASSIGNED orders until a technician joins; Admin/Owner reassign rooms until COMPLETED; the Assign Tests page stores room names; existing orders were re-routed once (`backend/scripts/reroute_orders_to_rooms.py`). `URINE_C_S` and the Microbiology catalog reach Room 105, ultrasonography Room 204.
- **Remaining gaps:**
  - **Doctor sign-off screen:** built in Prompt 15 (section 10). `approval_rule` DOCTOR_REQUIRED / BOTH_SIGNATURES now drives the approval queue. The DOCTOR queue/worklist and the generic status action are unchanged.
  - **`performing_role` normalization:** not done. The free-text values are kept; routing no longer depends on them (the mapping reads them only as a last hint).
  - **Tests without a room:** 671 catalog tests (Clinical Pathology, Endocrinology & Immunology, Histopathology, X-ray, Serology & Immunology, Cardiology, …) map to no room and are routed as UNASSIGNED for Admin/Owner or the Assign Tests page. Adding rooms or keywords in `SECTION_KEYWORDS` changes that in one place.
  - **Room left without technicians:** ~~orders already ASSIGNED stay ASSIGNED~~ **Implemented in 10F (ADL-051):** assigned-only orders become UNASSIGNED when the room loses its last active technician; orders with progress keep their state.
  - **Still open (owner to decide later):** room mapping of the 671 unmapped tests; the urgent-fee floor/cap rule (A1); master-discount behaviour (A3); a reject / send-back path for the doctor sign-off; `performing_role` normalization; the reduced-motion "Pause animations" control.

## 6. Prompt 11 — Delete / Discard Decision Table (implemented; owner browser acceptance pending)

| Category | Entities | Rule |
|---|---|---|
| **A — soft delete** (reason required, hidden from normal lists, restorable in the Admin/Owner Deleted view) | User/Staff, Doctor, 3rd Party/Referrer, Catalog Test | "New selection blocked only": existing bills, lines, results, referrals, commission and ledger rows are untouched. User delete is separate from deactivate (ADL-053). |
| **B — hard delete** (no reason, no restore, no Deleted view) | Draft Invoice only | Creator or ADMIN/OWNER; DRAFT status only; one audit row survives (ADL-054). |
| **C — never deletable / deactivatable** | Patient, Confirmed/Finalized Invoice, Payment, Refund, Result, Sample, Audit row, Business day, Ledger entry, Stock movement | No delete UI, no API. |

- **Audit Log viewer (Module 23, completed in Prompt 19B):** see section 15. Rows are append-only (database trigger) and kept forever; the viewer filters, searches and exports under `audit.view`.
- **Stray test users:** the leftover `LAB_TECH` fixtures in `medscope_test` were cleaned up with the new soft delete (98 users, not the 5 recorded in 10E; see the Prompt 11 report). `medscope_dcms` was not touched.

## 7. Prompt 12 Notes

- **Imaging lock / unlock:** see §4.10 and ADL-056. Owner same-day unlock: OWNER only (`invoice.line_unlock`), reason required, same business day.
- **Audit Log permission:** **Default of `audit.view`: OWNER = yes, ADMIN = no (the Owner can grant it to an Admin per user), every other role = no.** This is intended and matches the permission-matrix convention for owner-controlled, grantable keys (like "Pay commission / hand over visit fee"). An Admin who does not see **Audit Log** in the sidebar by default is correct, not a defect.
- **M11.4 barcode scan-to-task-open:** **deferred to the product-finishing phase by explicit owner decision** (not forgotten, not stubbed).
- **Test infrastructure:** test fixtures no longer accumulate in `medscope_test` (ADL-057).

## 8. Pre-Lock Cancellation and Business Day Status (owner decisions, 2026-11-14)

- **Permission matrix decision (recorded here only; the master context file is not edited):** for **pre-lock cancellation only**, the "Cancel/amend unlocked line" cell is **Receptionist, Cashier, Admin and Owner = Yes (cancel, no approval gate)**. Owner's reasoning: no sample has been taken, so no money or stock has been consumed; an approval step adds delay without protecting anything. This grants no ability to change price, discount, payment, or add/edit lines, and there is no generic "Edit Invoice" action.
- **Cancelling and paying out are different actions:** cancelling a line or invoice never accepts a payout channel and never pays money; the refund waits for the separate Disburse step. Owner's reasoning: a one-click combination makes a wrong amount or channel harder to catch or walk back.
- **Still approval-gated:** D15 "Not Performed" (post-lock; Lab Tech submits, Admin/Owner approve), imaging-started-not-completed cancellation, and owner same-day unlock (OWNER only, reason required). Segregation of duties (D56): the requester never approves their own request.
- **Two paths, one boundary (the lock event):** pre-lock = Cancel Test / Cancel Whole Invoice (`PRE_SAMPLE_CANCELLATION`, immediate) then Disburse; post-lock = D15 (`D15_NOT_PERFORMED`) then Admin/Owner approval then Disburse.
- **Whole-invoice action:** cancels **every remaining line together**, only when no line is locked or pending (M29 "Whole bill cancelled: only if no line locked"). Already-cancelled lines are skipped; it never cancels just the unlocked subset and never picks one line on the invoice's behalf.
- **Permission keys:** no new key. Cancelling needs `refund.request`, paying out needs `refund.disburse` (both held by Receptionist, Cashier, Admin and Owner by default; Lab Tech and Doctor hold neither). `refund.approve` and `refund.request_d15` apply to D15 only.
- **Business Day status:** there is one open business day at a time and its open/closed state is identical for every role, including Lab Tech, through the money-free `GET /business-day/state`. Lab Tech has no `business_day.view`, sees no cash or channel figure, and gets 403 from `/business-day/status` (M11.3).

## 9. Reference Ranges Versioned by Sex and Age Band (D24, Prompt 14)

- **Rule (master D24 / B3 3.2, 3.5):** a component's reference range and critical limits are versioned by **sex** (`ANY`, `MALE`, `FEMALE`) and **age band in total days**. Changing a band creates a **new version**; it applies to future results only. Every result stores the range used at entry, so editing a range never changes an old result or report.
- **Age:** the age entered at the visit (days, months or years) is converted to total days using the visit date (calendar spans counted back from the visit date; leap years and month lengths respected). Only the age entered at the visit is known, not a date of birth.
- **Band choice at result entry:** the current band for the patient's sex whose age span contains the age; otherwise the current `ANY` band for that age (shown as "any-sex range used"); otherwise **no band fits**: the row shows "No range for this age/sex: review manually", no flag is computed (never "Normal" by guess) and the row is marked `NO_BAND`. A patient whose gender is Other or Unknown only matches `ANY` bands.
- **Impossible-value validation** (Prompt 07) is unchanged and stays a per-component limit; **critical limits and reference limits** come from the chosen band.
- **Admin/Owner management** is inside **Catalog & Deleted → Reference ranges**: add a band, make a new version of a band, or retire a band (reason required). Rows are never edited or deleted. Two current bands of the same sex cannot overlap in age; an `ANY` band may sit beside sex-specific bands.
- **Data carried forward:** every pre-existing component range became **version 1** (sex Any, age 0 to no limit) with no value changed. The owner's demo values are not clinical truth: no new clinical numbers were invented; the owner adds real bands.
- **Permission:** the existing `test_catalog.manage` key (Admin and Owner by default, not a money key) covers it; no new key.

## 10. Doctor Sign-off per Test (D22, Prompt 15)

- **Rule (master D22 / M5 / M14, B2 item 3):** a test's approval rule is `TECHNICIAN_FINAL`, `DOCTOR_REQUIRED` or `BOTH_SIGNATURES`. Technician-final tests never reach the sign-off screen. For the other two, once the technician has submitted the result (status `ENTERED`) a doctor-side approval is recorded. For `BOTH_SIGNATURES` the technician's own sign-off is the existing result submission (Module 13); the doctor approval is the second signature, stored beside it.
- **Two ways to approve, same printed identity:**
  1. **Admin / Owner on a doctor's behalf** (the only way for visiting doctors, who have no login): pick the doctor, tick the attestation ("I confirm Dr. X has reviewed and approved this result, and I am recording the approval on their behalf"), optional notes, Confirm.
  2. **The DOCTOR login** approves its own assigned results: one Approve action, no doctor picker, no attestation tick.
  Both write the same doctor name and registration number (snapshotted on the approval). The audit log tells them apart: `DOCTOR_APPROVED_OWN_RESULT` versus `DOCTOR_APPROVAL_RECORDED_BY_STAFF` (the actor is the staff member who clicked).
- **Who sees what:** Admin/Owner see every doctor's pending results and can filter by doctor and assign an order to a doctor. A DOCTOR login sees only results assigned to its own doctor profile (a DOCTOR user must be linked to a doctor profile in User Management). Receptionist, Cashier and Lab Tech cannot reach the screen (403).
- **A doctor needs a registration number:** the report must print the doctor's name and registration number, so approval is refused for a doctor without one (add it to the doctor's profile first). Agents, clinics and institutions cannot approve.
- **After approval:** the order moves to the existing `COMPLETED` status, the line locks for no-sample tests, the report is finalized in the same transaction (section 11) and the screen shows who approved and how. Culture tests stay open, and are finalized when the culture stage is FINAL.
- **Not built (separate decisions):** rejecting or sending a result back to the technician. A both-signature result is still listed as Ready before the doctor signs (the Ready definition only excludes Awaiting Doctor and orders that have a Final report); it cannot be finalized until the doctor approves.
- **Permission:** the existing `result.complete_doctor_routed` key (Admin, Owner, Doctor by default; not a money key). No new key. The service also checks the role, so a per-user grant never lets another role attest for a doctor.

## 11. Draft to Final Report (Module 14, Prompt 16)

- **States:** Draft = a result saved as DRAFT (can be saved repeatedly; no report exists). Final = one immutable report version for the test order, version 1 (corrections and new versions are Module 15). `COMPLETED` on a test order is operational and does not mean the report is Final.
- **Who finalizes (D22):** `TECHNICIAN_FINAL` = the technician (or Admin / Owner with `result.enter` in that room) clicks **Finalize report** once the result is submitted; this is a separate step from submitting. `DOCTOR_REQUIRED` = the doctor approval (Prompt 15) finalizes automatically, in the same transaction. `BOTH_SIGNATURES` = automatically when the doctor approval is recorded, and only if the technician's sign-off (the submitted result) is also present. Cultures: finalization waits for the culture's own stage FINAL (an earlier doctor approval then finalizes automatically; a technician-final culture needs the click).
- **Never finalizable:** cancelled, rejected, spoiled or Not Performed orders, rejected / spoiled samples, a draft or missing result, a doctor-rule test without approval, a culture before FINAL, a report that is already Final.
- **Immutable:** the Final report keeps the content, reference ranges, flags and signatures as they were at finalization. Changes to the result, test or reference ranges afterwards never change it; the result of an order with a Final report or a doctor approval can no longer be saved.
- **Signatures (text only):** technician name and time, and for doctor rules the doctor's name and registration number (and whether staff recorded it on the doctor's behalf), stored on the report for later printing. Signature images / seals are not uploaded in this module.
- **Issued Reports:** the `/reports` Issued Reports tab lists Final reports (and the seeded older ones, which have no stored result view); **View result** shows the stored content. Delivery, due-hold and print preview work as before.
- **Report-ready SMS:** only a placeholder: a `notification_log` row `PENDING_INTEGRATION` and an audit row mark that a notification is due. No SMS, WhatsApp or QR is built or sent.
- **Concurrency:** saving a result with a stale view returns a "changed by X" conflict (simple check, not collaborative editing). There is no auto-save in the result modal.
- **Permission:** no new key: `result.enter` (+ room access) finalizes; `report.view` shows the stored report.

## 12. Report Handover and Dues (Modules 17 and 18, Prompt 17)

**Module coverage now (this repository; the module dashboard in the master context file was not edited and still shows Module 17 as "Not established", which is no longer accurate):**

| Module | Covered now | Not built |
|---|---|---|
| 17 Handover | Search by bill no. (final or temporary), patient no., test, mobile, name; held-while-due with the Admin/Owner release and reason; the hold is an Owner-editable center setting; take the due on the same screen; every handover logs staff and time (`report_deliveries` + audit); reprint is logged and marked Duplicate; third-party collection needs no special record | Online viewing, courier (deferred, M17.4 to 17.6) |
| 18 Dues | Dues derived from bills and payments; age buckets 7 / 30 / 90 days; call list; write-off with the Admin limit and Owner approval, kept apart from discounts; patient dues and doctor balances kept separate; the doctor's two labeled balances shown apart | SMS reminders, corporate dues (deferred); the data that fills the doctor balances (Modules 20 / 28); promised-payment-date notes |

- **Held report (M17):** a center setting, on by default (the behavior before Prompt 17). On: a report whose bill has a due cannot be handed over by the front desk; an Admin or the Owner can release it with a reason, which is logged. Off: reports are never held and a due does not block anything. The setting is changed by the Owner only (Settings page) and every change is audited.
- **Handover screen:** the Issued Reports tab of Ready Reports & Delivery. One search box finds a report by bill number (final or temporary), patient number, test name, mobile or name; the Paid / Held filter works. A held row shows the due and **Take payment** (the same payment modal as the Dues page) before **Deliver**; Admin/Owner also get **Override & Deliver** with a reason. Handing a report over twice is not blocked (each handover is logged).
- **Dues (M18):** a bill's age is counted from the bill date: 0-7, 8-30, 31-90 and over 90 days. The Dues page lists bills with age and filters by bucket; the **Call list** groups patients with unpaid balances, oldest first, for follow-up calls. Nothing is stored: every figure is derived on request.
- **Write-off (D11):** Admin or Owner, with a reason, on a bill with a due. An Admin can write off up to the **Admin write-off limit** (setting, default 500 Taka) per bill **in total** (repeated small write-offs cannot get around it); a larger Admin request waits for the Owner, who approves or rejects it; the Owner can write off any amount directly. The write-off lowers the due and raises `invoices.written_off`; it is kept in its own bad-debt record and never changes the invoice discount or any discount figure. No cash moves and no journal entry is posted. Money written off is not owed again if a line is cancelled later.
- **Doctor balances (D43):** a read-only view (Admin, Owner) with two separate figures per doctor: the **wholesale receivable** (the doctor owes the center) and the **professional-fee payable** (the center owes the doctor). They are never added together. No data source exists yet (wholesale billing, visit-fee holding and payouts are Modules 28 / 20), so the figures are 0 until those modules write the source rows.
- **Permissions:** new keys `settings.manage` (Owner), `due.writeoff` (Admin, Owner; money) and `doctor_balance.view` (Admin, Owner; money). Dues viewing and payment use the existing `payment.view` / `payment.take`; handover uses `report.view` / `report.deliver` / `report.release_with_due`.

## 13. Accounting and Day Open / Close (Modules 21 and 22, Prompt 18)

**Module coverage now:**

| Module | Covered now | Not built |
|---|---|---|
| 21 Accounting | Double-entry journal (balanced, append-only, reversal = a new entry); postings for the events below; cash book, daily income and expense, dues, cost by referrer with a flexible date range and CSV export for Excel | Postings for commission accrued / reversed / paid, visit-fee handover, consultant fee, outside-lab cost (Modules 19 / 20 / 28 do not exist); P&L, balance sheet, cash flow (not required now; the model can support them); no fiscal year |
| 22 Day Open / Close | Open with opening cash; close with counted cash, variance and reason; wallet / bank channels counted on their own lines; Owner-only reopen with a reason and adjusting entries only; bank deposit, owner withdrawal and small expense from the day screen | A real unsynced-items check (offline sync is not built; the condition always passes); payout terms of the D45 formula for commission, visit fee, consultant and outside lab (0 until those modules exist) |

- **Postings (the only ones):** *bill confirmed* Dr Patient receivable (net) and Dr Discount given, Cr Test revenue (gross) and Cr Urgent fee revenue; *payment received* Dr the channel account (Cash, bKash, Nagad, Rocket, Card, Bank, Other), Cr Patient receivable; *line cancelled* Dr Test revenue, Cr Patient receivable by the net reduction and Cr Discount given for the rest of the price, plus Dr Patient receivable / Cr Refunds payable for a refund owed; *refund paid* Dr Refunds payable, Cr the channel account; *due written off* Dr Bad debt, Cr Patient receivable (not a discount, not cash); *cash variance* shortage Dr Cash variance / Cr the channel, overage the reverse; *bank deposit* Dr Bank, Cr Cash; *owner withdrawal* Dr Owner drawings, Cr Cash; *small expense* Dr Operating expense, Cr Cash. No visit-fee liability line is posted because no visit-fee line exists in the system.
- **The journal starts at deployment.** Bills and payments made before Prompt 18 have no entries and are not backfilled, so the reports show activity from then on.
- **Entries are never edited or deleted** (the database refuses it). A mistake is fixed by a reversing entry that references the original; an entry can be reversed once.
- **Reports** (`accounting.view`, Admin / Owner by default): cash book (any one money account, running balance), daily income and expense (billing basis: the day a bill is confirmed, not the day cash arrives), dues (the Prompt 17 data, by bill date), cost by referrer (billing per referrer is real; cost is **0** because commission, Module 19, is not built, and the report says so).
- **Expected cash (D45):** opening cash + cash collections - cash refunds - bank deposits - owner withdrawals - small expenses. Commission, visit-fee, consultant and outside-lab payouts contribute 0 and are listed on the screen as "not built yet". Write-offs are not cash and are not in the formula. Wallet and bank channels are expected = opening + collections - refunds on that channel and are counted on their own lines, never mixed into cash.
- **Variance (D46):** counted - expected. A reason is required when the absolute variance is above the Owner-set tolerance (`cash_variance_tolerance`, default 0 Taka, in Settings). The variance is posted to the journal for every counted channel.
- **Close, reopen (D47):** closing is Admin / Owner only (unchanged; the historical "Cashier can close" line stays superseded by Prompt 04). A closed day takes no payment, movement or ordinary entry. The Owner can reopen it with a reason; a reopened day takes **adjusting entries only** (a reversal of an entry of that day, or a balanced manual entry, Owner only, reason required). Closing it again posts only the difference in variance.
- **Movements (D48), clarified 2026-11-14:** **owner withdrawal is Owner only; bank deposit and small expense are Admin or Owner** (owner decision; each needs `business_day.close`). A small expense needs a what-for. They come out of the open day's cash, cannot exceed the cash expected in the drawer, and each posts its journal entry.
- **Permissions:** one new key, `accounting.view` (Admin, Owner; money). The day screen, movements, close, reopen and adjustments use the existing `business_day.close` key plus an Owner role check where stated.

- **Open-day rule, added 2026-11-14 (Prompt 18B):** payments, bill confirmation and refund payout need an **OPEN** business day. With no open day the action is refused: 409 when the latest day is closed or reopened, 400 when no day was ever opened; nothing is recorded without a day. Write-off and cancellation move no cash and keep working with no open day (their journal entry then carries no day).
- **One active day, 2026-11-14:** only one business day may be OPEN or REOPENED per tenant. A new day cannot be opened (400) until a reopened day is closed again. This replaces the earlier statement that other days could be opened while a day is reopened.
- **Adjusting entries and expected cash, 2026-11-14:** adjusting entries posted on a reopened day that touch a channel account (for example Cash) are an explicit term of that channel's expected cash ("adjusting entries"), so the Owner's correction does not create a new variance. Variance entries and their reversals are excluded (they are the count mechanism). The rest of the formula still comes from the source tables, not the journal.

## 14. Doctor / 3rd-party Maintenance (Prompt 19)

- **Edit (closes a gap, 2026-11-14):** before Prompt 19 a doctor or 3rd party could only be created or soft-deleted, so a wrong phone or registration number could not be corrected. Admin and Owner (`referrer.manage`, the same key as Delete) can now edit name, type, phone, registration number, specialty and chamber in place on Catalog & Deleted. The record keeps its id, so bills stay linked. Commission and rates are not edited there (no rate-card mechanism exists yet).
- **Snapshots:** a doctor approval keeps the name and registration number it was signed with. Bill and report listings show the referrer's **current** name (they store only the referrer id), so a rename shows on them; the registration number is not printed on bills. This is how those screens always worked and was not changed.

## 15. Audit Trail (Module 23, Prompt 19B)

- **One audit log.** `audit_logs` (who, acting role, when, action, entity, before, after) is the single audit mechanism. The separate `reprint_logs` table was folded into it: a print or reprint is now an `INVOICE_REPRINTED` / `REPORT_REPRINTED` row with the acting role and "N earlier print(s)" as before. The 49 legacy rows on `medscope_dcms` were copied with the acting role recorded as `UNKNOWN` (the old table never stored it) and the table was dropped.
- **Append-only, for everyone.** A database trigger refuses UPDATE, DELETE and TRUNCATE on `audit_logs`. There is no bypass or exception path in the trigger, no purge or archival job and no retention limit: rows are kept forever. The test-data cleanup script no longer exists in the repository.
- **Covered domains:** bills, discounts, payments, reports (including every report view), accounting, settings and permissions are all written to the log. **Stock** is still only the `STOCK_CONSUMPTION_INTEGRATION_TRIGGERED` marker, because no inventory module exists and there is nothing real to log.
- **New events (Prompt 19B):** `INVOICE_DISCOUNT_CHANGED` (draft save or edit, only when the discount setup changed), `INVOICE_DISCOUNT_CONFIRMED` (final discount state at confirm), `INVOICE_INITIAL_PAYMENT` (the payment taken at confirm: amount, channel, reference, payer, receiver; separate from `CONFIRM_INVOICE`), `REPORT_VIEWED` (one row per open of a report, no throttling), `REPORT_PREVIEW_VIEWED` (one row per open of a ready-result preview; its `entity_id` is the test order id because no report version exists yet) and `AUDIT_LOG_EXPORTED`.
- **Viewer (`audit.view`, Owner by default, unchanged):** filter by domain, action, entity type, person, acting role and date range; free-text search over action, entity type and id, and the before / after text; CSV export (UTF-8 with BOM, same format as the accounting export) of exactly the rows the current filters select. Every export writes an `AUDIT_LOG_EXPORTED` row (who, filters, row count). The screen has no edit or delete path.
- **Catalog edits:** there is still no catalog-test edit endpoint (only soft delete and restore, both audited), so no edit event exists or is needed.
- **Vendor / session log: deferred (decision of 2026-11-14).** "Vendor" has no current subject in this system. The idea comes from the legacy Streamlit prototype's Platform Dev, which has no equivalent in the FastAPI backend and no connection to this audit log. No Vendor role, session table or permission was created. It will be scoped as its own module when multi-tenancy and vendor-profile work begins.
- **Not decided or built:** a structured (JSON) before / after column and an action registry (actions stay free text; the domain grouping lives in `backend/app/core/audit_domains.py`).
