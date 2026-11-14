# MedScope DCMS — System Architecture Specification

## 1. Architectural Overview & Decoupling

MedScope operates on a modernized, dual-stack architecture designed to handle high-throughput diagnostic intake desks while preserving core clinical and double-entry accounting ledgers:

- **Frontend (`frontend/`):** React 19, TypeScript, Vite 8, Tailwind CSS v4, Lucide Icons, React Router v7. Provides sub-millisecond local state updates, zero-rerun keyboard shortcuts, and native print formatting.
- **Backend (`backend/`):** FastAPI, Pydantic v2, SQLAlchemy 2.0 ORM, and async-capable architecture. Provides strict OpenAPI schema contracts, sub-5ms API response latency, and modular REST design (79 paths / 92 operations across 16 endpoint modules, as of Prompt 10D).
- **Database:** PostgreSQL 18 on port 5432 (`medscope_dcms`, user: `medscope_app`) managed via Alembic migrations (37 domain entities, 38 tables total; single head `a19b5c7d9e31`).
- **Testing Infrastructure:** Automated pytest integration suite (80 test cases passing in-process against isolated `medscope_test`, Prompt 10D). Playwright specs exist under `frontend/e2e/` (see `docs/TESTING.md`).
- **Legacy Stack (`DCMS V1.py`, `accounting.py`):** Streamlit + SQLite preserved for internal laboratory analysis and specialized double-entry accounting routines.

```
+-----------------------------------------------------------------------------------+
|                            MedScope Operational Stack                            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Modern Client ]                 [ REST API Gateway ]           [ PostgreSQL ]  |
|  React 19 + Vite 8                 FastAPI (Python 3.14)          Version 18      |
|  - Bento Grid Layout               - 79 Paths / 92 Ops            - 28 Domain Tbl |
|  - 60-30-10 Palette                - Multi-tenant Isolation       - Alembic Migr. |
|  - A4 Landscape Dual-Copy Print    - Whole-Taka Integers          - Monotonic Seq.|
|  - Session Login + User Menu       - Central Permission Layer     - Concurrency   |
|         |                                   |                            |        |
|         +--- HTTP JSON (port 5173 -> 8000) -+                            |        |
|                                             +--- SQLAlchemy 2.0 (5432) --+        |
|                                                                                   |
|  [ Legacy Services ]                                              [ SQLite ]      |
|  DCMS V1.py & accounting.py -------------------------------------> medscope_data/ |
+-----------------------------------------------------------------------------------+
```

---

## 2. Directory Layout

```
MedScope/
├── backend/
│   ├── alembic/                      # Alembic environment and migration scripts
│   │   ├── versions/                 # 12 revisions, 5e7d6e556c9d … a4d8c2e6f1b7 (single head)
│   │   └── env.py                    # Migration execution runner
│   ├── app/
│   │   ├── api/v1/                   # REST API routes
│   │   │   ├── endpoints/            # Domain endpoint routers (16 modules, incl. users.py)
│   │   │   └── router.py             # Root v1 aggregator router
│   │   ├── core/                     # Core configs, database connection, security
│   │   │   ├── config.py             # Pydantic Settings
│   │   │   ├── database.py           # SQLAlchemy SessionLocal and engine
│   │   │   ├── security.py           # CurrentActor (single role + effective permissions)
│   │   │   ├── permissions.py        # Central role/permission layer (ROLES, keys, defaults, require_permission)
│   │   │   ├── lab_sections.py       # Lab rooms (101, 102, 105, 204) + the test -> room mapping (Prompt 10E)
│   │   │   ├── samples.py            # requires_sample / is_imaging_test / imaging_sql_clause (10E; rule replaced in 10F, ADL-050)
│   │   │   └── payment_channels.py   # Payment channel list and OTHER-name rule (Prompt 10E)
│   │   ├── models/                   # SQLAlchemy 2.0 ORM domain entities (28 tables)
│   │   ├── schemas/                  # Pydantic v2 request/response schemas
│   │   ├── services/                 # Business logic, audit logging, sequences (routing_service.py: room routing 10E + empty-room rule 10F; ready_report_service.py: the one Ready definition + result preview, 10F)
│   │   └── main.py                   # FastAPI application initialization & CORS
│   ├── scripts/                      # Seed, admin CLI, and dev/testing utilities (seed.py, manage_users.py, provision_prompt10d_users.py, reroute_orders_to_rooms.py; sql/cleanup_test_data.sql is git-ignored, local only)
│   └── requirements.txt              # Backend dependencies
├── frontend/
│   ├── e2e/                          # Real browser Playwright E2E test suites
│   │   ├── receptionist_corrections.spec.ts # Prompt 04 specs (updated 10D/10E; creates records, disposable DB only)
│   │   └── test_modal_regression.spec.ts    # Prompt 08 modal specs (updated 10D/10E; read-only)
│   │   └── support/auth.ts               # Shared login helper (password from MEDSCOPE_E2E_PASSWORD)
│   ├── playwright.config.ts          # Playwright configuration (Chromium, baseURL)
│   ├── src/
│   │   ├── api/                      # Client API connector (client.ts)
│   │   ├── components/               # Common UI widgets, Layout, Modals
│   │   │   └── common/
│   │   │       └── DualCopyInvoiceModal.tsx # A4 Landscape Patient/Office dual copy
│   │   ├── context/                  # AuthContext, ToastContext
│   │   ├── features/                 # Page features (Dashboard, Invoices, Patients, etc.; 10F: assignments/AssignedTestsPanel.tsx, reports/ReadyResultsPanel.tsx)
│   │   ├── utils/                    # Helpers (10F: useRefetchOnFocus.ts refetches lists on window focus)
│   │   ├── types/                    # TypeScript interfaces and domain enums
│   │   └── App.tsx                   # Main React entry & router configuration
│   ├── package.json                  # NPM packages, Playwright runner, build scripts
│   └── vite.config.ts                # Vite dev server and proxy rules
├── tests/                            # Automated pytest backend test suite
│   ├── conftest.py                   # Test DB fixtures + safety guard (refuses medscope_dcms)
│   ├── test_receptionist_e2e.py      # Prompt 03 integration tests
│   ├── test_prompt04_corrections.py  # Prompt 04 corrections
│   ├── test_prompt07_module13_and_fixes.py # Module 13 flags/limits
│   ├── test_prompt07c_fixes.py       # Prompt 07C safety fixes
│   ├── test_prompt09_auth.py         # Auth/session tests
│   ├── test_prompt10d_refunds.py     # Refund rule (rewritten in 10E: refund = max(0, retained paid - net after))
│   ├── test_prompt10d_drafts.py      # Draft / Finalize workflow
│   ├── test_prompt10d_roles_permissions.py # Single role, permissions, user management
│   ├── test_prompt10e_invoice_payment_samples.py # Sample rule, age/gender, channels, urgent fee
│   ├── test_prompt10e_rooms_roles_worklist.py    # Rooms, reassign, DOCTOR, profile, release with due, Ready/preview
│   └── test_prompt10f_owner_findings.py          # 10F: Assigned Tests, preview, shared Ready, A5 sample rule, A11 empty room (122 tests total)
├── docs/                             # Nine canonical documentation files
├── README.md                         # Project startup & environment guide
└── project-context.md                # Master state & invariants
```

---

## 3. Architecture Decision Log (ADL)

### ADL-001: Architecture Decoupling (FastAPI + React vs. Streamlit)
- **Decision:** Build a modern, decoupled client-server architecture for the high-volume Receptionist front desk while keeping legacy Streamlit modules operational.
- **Consequences:** Eliminates UI freezing caused by Streamlit reruns, provides sub-5ms API latency, enables keyboard navigation, and ensures crisp thermal and laser printing.

### ADL-002: Relational Database Strategy (PostgreSQL 18 vs. SQLite)
- **Decision:** Adopt PostgreSQL 18 managed through Alembic migrations for the modern stack.
- **Consequences:** Eliminates SQLite file locking (`database is locked`) during concurrent intake, allows partial indexes, foreign-key cascades, and transactional schema evolution.

### ADL-003: Monetary Representation (Whole-Taka Integer Invariant)
- **Decision:** All financial columns (`gross_amount`, `price`, `discount_amount`, `urgent_fee`, `net_amount`, `paid_amount`, `due_amount`, `opening_balance`, `current_balance`) are stored strictly as 64-bit/32-bit integers representing whole Bangladeshi Taka (৳).
- **Consequences:** Floating-point rounding errors (IEEE 754 drift) are strictly eliminated. Exact ledger balances: `net = gross - discount` and `due = net - paid`. Default paid amount for new invoices is ৳0.

### ADL-004: Discount Precedence & Line Price Ceiling
- **Decision:**
  1. Individual line item discount limit is the applicable test price (up to 100% or full test price; zero net value allowed, no negative values).
  2. Master Discount uses either percentage (up to 100%) or fixed amount (up to invoice subtotal).
  3. **Precedence Invariant:** When Master Discount is active (`master_discount_type != 'NONE'`), individual line discounts are superseded in net calculations. The Master Discount applies uniformly across the bill subtotal.
  4. Both modes (% and ৳) synchronize dynamically on input.
- **Consequences:** Prevents discount stacking while preserving entered line discount values in state should the master discount be toggled off.

### ADL-005: Pre-Sample Cancellation Refund State Machine
- **Decision:**
  - Pre-sample cancellation is allowed **only for an unlocked line** (the one lock check used everywhere; refused with 409 `SAMPLE_ALREADY_TAKEN` otherwise, see ADL-060).
  - **Pre-lock cancellation has no approval step** (ADL-062): the `RefundRequest` is created already `APPROVED` (or `COMPLETED` when 0) and takes effect at once; payout is the separate disburse step (ADL-065). **D15 "Not Performed"** requests start in `PENDING_ADMIN_APPROVAL`, and payout for a D15 request stays blocked until an Admin or Owner approves it.
- **Consequences:** Protects clinic revenue, prevents fraudulent unauthorized refunds, and provides complete traceability.

### ADL-006: Diagnostic Report Release Due Hold with Admin Override
- **Decision:**
  - Reports in status `AUTHORIZED` display an automatic `DUE HOLD` indicator if `invoice.due_amount > 0`.
  - Delivery action is strictly disabled for Receptionists when due balance is positive.
  - Settle Due workflow must be completed first to clear the balance to 0, which immediately unlocks standard delivery.
  - Exception: Emergency release is permitted only via the `Admin Due Override` endpoint, which mandates a documented justification and logs the authorizing Admin staff ID.
  - Prompt 10E: only holders of `report.release_with_due` (Admin/Owner by default) may release with a due, and the override reason is required (400 without it). RECEPTIONIST and CASHIER are refused (403) even with a reason.
- **Consequences:** Eliminates accidental delivery of unpaid reports while providing an auditable emergency pathway.

### ADL-007: Single Open Business Day Constraint
- **Decision:** Enforce a database-level partial unique index:
  ```sql
  CREATE UNIQUE INDEX idx_business_day_single_open ON business_days(tenant_id) WHERE status = 'OPEN';
  ```
- **Consequences:** Impossible for race conditions to open concurrent business days; opening a new day requires closing the prior day.

### ADL-008: Strict Receptionist Operational Boundaries & Business Day RBAC
- **Decision:**
  1. Pydantic schemas returned to Receptionists strictly omit `commission_rate`, `test_cost_price`, and accounting ledger tables.
  2. Closing a business day requires drawer cash counting and cashier reconciliation; the `/business-day/close` endpoint strictly rejects requests from `RECEPTIONIST` and `CASHIER` with HTTP 403 Forbidden. Only `ADMIN` and `OWNER` may close business days.
- **Consequences:** Enforces the principle of least privilege while providing receptionists all tools needed for smooth desk operations.

### ADL-009: Dual-Copy Printable Layout & Reprint Watermark
- **Decision:**
  - Invoices support A4 Landscape Dual-Copy print formatting rendering **Patient Copy** (left) and **Office / Lab Copy** (right) side-by-side with a vertical dashed cut line (`✂ Cut Here`).
  - Initial print produces the official `DIAGNOSTIC MONEY RECEIPT`.
  - Every subsequent print triggers `/invoices/{id}/reprint` which increments `reprint_count`, logs an audit entry, and renders a bold, diagonal `DUPLICATE` watermark across both copies.
- **Consequences:** Diagnostic centers retain a physical audit copy without double printing, and reprint abuse is visibly and auditably eliminated.

### ADL-010: Independent Prescriber vs. Referrer Data Modeling
- **Decision:**
  - Separate medical prescriber from referral agent:
    1. `Prescribed By (Doctor)`: strictly filtered to medical doctors (`type = 'Doctor'`), stored in `invoices.prescribed_by_id`.
    2. `Referred By (Doctor / Third Party)`: accepts doctors or third-party brokers/organizations, stored in `invoices.referrer_id`.
  - Both foreign keys reference `referrers.id` and are nullable for walk-in patients.
- **Consequences:** Clean attribution between clinical authority and commercial marketing referral channels.

### ADL-011: Write-Only Commission Privacy Boundary
- **Decision:**
  - Allow receptionists to enter initial commission information (`commission_rate`, `commission_type`) when registering a new doctor or referrer inline.
  - Omit commission data entirely from all read schemas (`ReferrerResponse`, search results, lists, and detail queries).
- **Consequences:** Receptionists cannot view confidential financial agreements, stored commission rates, or historical payouts.

### ADL-012: Two-Stage Non-Final Invoice Creation Lifecycle
- **Decision:**
  - Intake flow: `Form Entry -> Generate Preview -> Dual-Copy Preview Modal -> Back & Correct OR Save [and Print]`.
  - Generating preview performs pure in-memory calculation without generating an invoice number, writing to the database, or booking payments.
  - Successful save assigns a monotonic invoice number, writes transactionally, resets the entry form to a clean state with paid amount ৳0, and retains the saved invoice in preview context for printing.
- **Consequences:** Eliminates accidental invoice gap sequences and orphan records caused by pre-save cancels.

### ADL-013: Idempotent Split Task Routing & Visiting Doctor Queuing (Module 10)
- **Decision:**
  - Upon invoice confirmation, every invoice line item becomes an independent `TestOrder`. The bill itself is never assigned as a monolithic task.
  - **Superseded in Prompt 10E by ADL-041 (room-based routing).** Orders are routed to a lab room, never to one technician:
    * If `requires_doctor == True` or `performing_role == 'DOCTOR'`: Enters `AWAITING_DOCTOR` status (unchanged); the room is recorded when the test maps to one.
    * Outsourced tests: `PENDING` (unchanged).
    * Otherwise `ASSIGNED` to the test's room when the room has an active LAB_TECH, else `UNASSIGNED` (visible to Admin/Owner).
  - Order creation is strictly idempotent (`invoice_line_id` is unique on `test_orders`).
- **Consequences:** Eliminates manual front-desk routing delays while preventing unassigned tasks from becoming lost.

### ADL-014: Strict Financial-Data Isolation for Laboratory Technicians (Module 11)
- **Decision:**
  - Technicians operate under strict operational boundaries: zero visibility into test prices, discounts, master margins, dues, or referrer commissions.
  - This constraint is enforced at the backend Pydantic serialization layer via `TechnicianWorklistItemResponse`, not merely hidden in the frontend.
  - Worklist queries are hard-filtered by the technician's room (`test_orders.lab_section == staff.lab_section`) since Prompt 10E (before: `assigned_to_id == actor.id`). DOCTOR has the same money isolation (Prompt 10E).
- **Consequences:** Guarantees commercial margin secrecy from floor staff while providing full clinical and turnaround operational context.

### ADL-015: High-Capacity Catalog Ingestion & Multi-Tenant Scoping
- **Decision:**
  - Diagnostic centers maintain extensive investigation directories (1,200+ tests).
  - The `GET /api/v1/tests` endpoint provides high-capacity delivery with `limit: int = Query(default=2500, le=10000)` to supply the full catalog to front-desk intake on mount.
  - Test records are strictly scoped to `tenant_id` (e.g. `'center-seba-01'`) and indexed by `(tenant_id, code)` and `(tenant_id, name)`.
  - Client-side intake maintains instant autocomplete filtering and dynamic department category chips from the in-memory catalog, with deduplication against already selected tests.
- **Consequences:** Provides instantaneous, zero-latency autocomplete for receptionists handling high-volume billing while maintaining strict multi-tenant boundary isolation.

### ADL-016: Specimen Barcode Label Architecture & Pure-Python Vector Generation (Module 12)
- **Decision:**
  - Every collected specimen generates a Code 128 barcode label formatted for 50mm x 25mm / 50mm x 30mm thermal label printers.
  - Pure-Python vector SVG generation (`barcode_service.py`) eliminates external binary/npm dependencies while generating sharp, scanner-readable barcodes at any resolution.
  - The barcode encodes the unique sample code (`sample_code`), not merely the invoice number or patient code.
  - Labels omit all pricing, discounts, and payment metadata.
- **Consequences:** Provides direct scan-to-task laboratory worklist routing without proprietary driver dependencies or financial data leakage.

### ADL-017: Specimen Line Lock & D15 Rejection State Machine (Module 12)
- **Decision:**
  - At specimen collection, `InvoiceLine.is_locked = True`. Ordinary pre-sample cancellation is permanently locked.
  - Unsuitable or spoiled specimens transition to `REJECTED` or `SPOILED` with a mandatory recorded clinical reason.
  - Patient is flagged for telephone follow-up. Under the D15 invariant rule, recollection requires a new invoice line and new sample ID; there is no free re-run.
  - Line locking triggers a reagent stock deduction boundary event, with complete reagent batch ledger management deferred to Module 16.
- **Consequences:** Enforces strict clinical and revenue integrity, prevents ghost sample reruns, and establishes clean integration boundaries.

### ADL-018: Clinical Result Entry, Reference Range Snapshots & Automatic Flagging (Module 13)
- **Decision:**
  - Support three template formats: `NUMERIC_TABLE` (with components), `NARRATIVE` (Findings, Impression, Comments), and structured `ULTRASOUND` (organ-by-organ breakdown).
  - Absolute physiological boundaries (`impossible_min`, `impossible_max`) reject absurd inputs (e.g. Hemoglobin 150) immediately with HTTP 400.
  - Automatic clinical flags evaluate numeric values against configured reference bounds: `LOW`, `HIGH`, `CRITICAL`, or `NORMAL`. Incomplete or missing reference ranges NEVER silently default to NORMAL; flag remains `None`.
  - **D24 Snapshot Invariant:** When results are entered, the reference range, critical limits and units used are permanently snapshotted into `result_items` (with the id of the band version used, ADL-067). Future changes to the test catalog or to a range never drift historical clinical results.
  - Decouple `Result.status` (`DRAFT`, `ENTERED`) from `TestOrder.status` (`SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `COMPLETED`).
- **Consequences:** Provides clinical data fidelity, prevents malpractice from data corruption, and ensures immutable diagnostic history.

### ADL-019: Rejected Specimen D15 Refund Exception & Two-Stage Disbursal Separation (Module 12 Fix 4)
- **Decision:**
  - When a specimen is spoiled or rejected, `TestOrder.outcome = "NOT_PERFORMED"` under the D15 exception.
  - The technician can submit a D15 refund request directly from the worklist (`request_type = "D15_NOT_PERFORMED"`, `status = "PENDING_ADMIN_APPROVAL"`).
  - Invoices view blocks generic pre-sample cancellation on locked lines while displaying the authoritative D15 refund status.
  - **Two-Stage Refund Separation:** Admin review marks the request `APPROVED` and invoice `REFUND_APPROVED`. Money disbursement is an explicit separate action performed by the Cashier or Admin, recording the payout channel (`CASH`, `BKASH`, `NAGAD`, etc.), drawer deduction, and reversing referral commissions.
  - **Refund amount rule (Prompt 10E, ADL-040; replaces the Prompt 10D proportional allocation):** when a line is cancelled, `net_after = invoice net − the line's net price` (never below the invoice's urgent fee), `retained_paid = paid − all APPROVED and DISBURSED refunds`, `refund = max(0, retained_paid − net_after)` and `due = max(0, net_after − (retained_paid − refund))`. The amount is computed by the server when the request is created (preview) and recomputed at approval; client amounts are ignored. A refund and a due never coexist after a cancellation; refunds never exceed total paid. A zero-amount approval cancels the line and closes the request as `COMPLETED` (nothing to disburse).
- **Consequences:** Prevents phantom drawer shortages by ensuring cash is deducted only when physically paid out, while upholding the D15 invariant against unauthorized cancellations.

### ADL-020: Original Payment Channel Enforcement for Refunds (Rules 3.1, D18, M29)
- **Decision:**
  - `disburse_refund` strictly validates that the refund disbursement method matches one of the payment channels actually used on that invoice (`CASH`, `BKASH`, `NAGAD`, `ROCKET`, `POS_CARD`, `BANK_TRANSFER`, `OTHER` — Prompt 10E, ADL-042).
  - Mandatory transaction reference number on non-cash disbursements.
  - Enforce per-channel payment balance limits: cumulative disbursements through any channel cannot exceed what was paid via that channel.
  - Cash disbursements decrement the active business day drawer balance.
- **Consequences:** Prevents financial leakages, money laundering across payment methods, and unbalanced physical cash drawers.

### ADL-021: Segregation of Duties on Refund Approval (Rule 3.6, D56)
- **Decision:**
  - Self-approval of refund requests is blocked (`reviewer_id == requested_by_id` returns HTTP 403 Forbidden).
  - Emits immutable security audit log `REFUND_SELF_APPROVAL_BLOCKED`.
  - Check is encapsulated in a dedicated helper `enforce_segregation_of_duties` so it can be made configurable per customer ("Small Center Mode") in the future centralized permission layer.
- **Consequences:** Eliminates single-operator embezzlement risk while maintaining clean code architecture for small-center operational toggles.

### ADL-022: Culture Lifecycle Decoupling (Rule D19, M12)
- **Decision:**
  - Decouple culture stage progression (`INCUBATING` -> `PRELIMINARY` -> `FINAL`) from `TestOrder.status`.
  - Setting `culture_stage = "FINAL"` keeps order status as `IN_PROGRESS` (does NOT auto-complete).
  - Completing a culture test order requires entering results after reaching the `FINAL` stage.
- **Consequences:** Aligns system state with laboratory microbiology reality where incubation completion is not synonymous with verified report completion.

### ADL-023: Result-Save Guards & Completed Order Immutability
- **Decision:**
  - Modifying or resaving results on a `COMPLETED` order is strictly rejected with HTTP 409 Conflict. Post-completion edits belong to future Correction workflows (Module 15).
  - Saving a `DRAFT` result preserves `TestOrder.status` (does NOT advance intermediate state).
  - For sample-based tests, entering or saving results prior to specimen collection is strictly rejected with HTTP 409 Conflict.
- **Consequences:** Prevents accidental or fraudulent modification of completed clinical reports, enforces specimen collection prerequisite, and preserves draft state machines.

### ADL-024: Technician Financial Isolation (Rule M11.3, 3.8)
- **Decision:**
  - Technicians operate strictly on clinical data. `POST /api/v1/worklist/{id}/d15-refund-request` returns `D15RefundClinicalResponse` omitting all pricing, amount, and refund values.
  - Test order lifecycle timeline (`GET /api/v1/worklist/{id}/events`) dynamically sanitizes monetary figures (`Tk` and `৳`) for `LAB_TECH` callers, while maintaining raw audit rows for Admins/Owners.
- **Consequences:** Prevents commercial pricing leakage to floor staff while providing necessary operational timeline context.

### ADL-025: In-Place Patient Operational Profile Overlay (Prompt 08 Part A)
- **Context:** Opening patient details or history from an invoice detail modal previously triggered `navigate('/patients?id=...')`, which switched the background page/tab to Patients and lost Invoices search filters, status filters, and scroll position.
- **Decision:** Encapsulate the patient operational history view in a reusable `PatientHistoryModal` component. Screens such as `InvoicesPage` render patient history directly in an overlay modal without navigating or unmounting the underlying page.
- **Consequences:** Preserves the user's active page, filter criteria, and scroll state across detail inspection workflows.

### ADL-026: Test Database Isolation & Pytest Guard (Prompt 08 Part B)
- **Context:** Automated tests previously checked for a live server on port 8000 and issued HTTP requests to it, writing synthetic records into the primary development/QA database (`medscope_dcms`).
- **Decision:**
  - Mandate isolated test database execution via `TEST_DATABASE_URL` (e.g. `medscope_test`).
  - Introduce a hard guard in `tests/conftest.py` that halts test execution with `pytest.UsageError` if `TEST_DATABASE_URL` resolves to the main/QA database.
  - Execute the full Alembic migration chain from `<base>` to head at test session start.
  - Remove all live-server network probing; tests run strictly in-process via FastAPI's `TestClient`.
- **Consequences:** Completely prevents test data pollution in QA/production environments while verifying database migrations from scratch.

### ADL-027: Server-Side Session Authentication & HttpOnly Cookie Transport (Prompt 09)
- **Context:** The frontend previously trusted an unauthenticated development role switcher that passed arbitrary staff IDs and roles via request headers.
- **Decision:**
  - Replace header-based identity switching with stateful, server-side sessions stored in `auth_sessions`.
  - Pass raw 256-bit entropy tokens in `HttpOnly`, `SameSite=Lax`, `Path=/` cookies (`medscope_session`), or `Authorization: Bearer <token>` for API clients.
  - Store only SHA-256 hashes of session tokens in the database.
  - Enforce `X-Requested-With: XMLHttpRequest` custom header on all state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) as CSRF mitigation.
  - Enforce idle timeout (120 minutes) and absolute session lifetime (24 hours).
  - Hash passwords using Argon2id (`argon2-cffi`) with min 8 characters and non-username rule.
  - Trigger automatic account lockout after 5 consecutive failed login attempts.
- **Consequences:** Provides cryptographic security against session hijacking, XSS token extraction, and brute-force attacks, while completely removing identity spoofing from the application.

### ADL-028: Multi-Role Assignment & Acting Role Session State (Prompt 09)
- **Context:** Diagnostic centers often employ staff who operate in multiple roles (e.g. Receptionist during morning intake, Cashier during afternoon reconciliation; or Admin who is also an Owner).
- **Decision:**
  - Introduce `staff_roles` mapping table allowing multiple roles per person.
  - Maintain active `acting_role` inside `auth_sessions`.
  - Provide `POST /api/v1/auth/acting-role` to allow authenticated users to switch acting roles among their granted roles.
  - Route handlers continue using existing role guards (`require_receptionist`, `require_admin`, `require_lab_tech_or_admin`) bound to `actor.role = session.acting_role`.
- **Consequences:** Eliminates code refactoring in business services while supporting flexible role assignment with full audit trail traceability.
- **Status:** **Superseded by ADL-032 (implemented in Prompt 10D).** `staff_roles` and `auth_sessions.acting_role` remain, but each user now holds exactly one role and `POST /auth/acting-role` is removed.

### ADL-029: Self-Hosted Font Strategy (Prompt 10)
- **Context:** Low-bandwidth clinical center networks in Bangladesh frequently drop or throttle third-party CDN requests (such as Google Fonts), causing layout shift or missing fallback glyphs.
- **Decision:** Package Manrope (`@fontsource/manrope`) and Noto Sans Bengali (`@fontsource/noto-sans-bengali`) as local npm dependencies bundled directly into Vite build artifacts (`dist/assets/`). Prohibit all external CDN and runtime Google Fonts requests.
- **Consequences:** Zero external network dependencies for typography; 100% offline-resilient rendering of English and Bengali characters with identical baseline metrics.

### ADL-030: Public Routing, Role Home Redirection & Branded 404 (Prompt 10)
- **Context:** The application previously lacked public marketing and authentication entry points, and root `/` coupled directly to the internal dashboard.
- **Decision:**
  - Mount `/` as the public branded landing page.
  - Mount `/login` as the public animated sign-in page.
  - Mount `/dashboard` as the authenticated executive workbench.
  - Route unauthenticated access to protected routes to `/login`.
  - Redirect authenticated staff who open `/` or `/login` directly to their designated role home route (`/invoices` for Receptionist/Cashier, `/worklist` for Lab Tech, `/dashboard` for Admin/Owner).
  - Catch-all `*` renders a branded 404 page (`NotFoundPage`).
- **Status:** Public routes, `/dashboard` and the branded 404 are unchanged. The per-role home routes are **superseded by ADL-033 (implemented in Prompt 10D)**: every login, and every signed-in visit to `/` or `/login`, now goes to `/dashboard`.
- **Consequences:** Clean separation of public entry surfaces and authenticated operational workspaces without route collision or unauthorized data exposure.

### ADL-031: Lightweight CSS Keyframe Animation Architecture (Prompt 10)
- **Context:** High-motion marketing libraries (such as Three.js, Lottie, or heavy canvas runners) degrade front-desk hardware performance and violate the lightweight clinical footprint.
- **Decision:** Implement all interactive and medical scene animations (ECG heartbeat line, filling tube, travelling dot, sequential chips, pulsing peak marker, and marquee) strictly via pure vector SVG and native CSS keyframes animating only `transform`, `opacity`, and `stroke-dashoffset` using the weighted deceleration curve `cubic-bezier(0.22, 1, 0.36, 1)`.
  - **No reduced-motion fallback (intentional):** the `@media (prefers-reduced-motion: reduce)` fallback was removed on purpose during Prompt 10. Windows machines with animations disabled report `reduce` to Chromium, and the fallback froze the ECG line and stacked the marquee. `frontend/src/index.css` has keyframes only. The owner has not yet decided on a "Pause animations" control.
- **Consequences:** Ultra-fast rendering (~60fps on low-end hardware) with zero JavaScript execution overhead during animation frames. Users who prefer reduced motion currently still see the animations.

### ADL-032: One Login = One Fixed Role (Prompt 10C decision, implemented in Prompt 10D)
- **Status:** **Implemented (Prompt 10D).** Supersedes ADL-028.
- **Decision:** Each login carries exactly one fixed role. No acting-role switching.
- **Implementation:** `POST /api/v1/auth/acting-role` and the header switcher are removed. `staff.role` is authoritative; `get_current_actor` uses it (an old session's `acting_role` is ignored). `auth_sessions.acting_role` is kept and always set to the user's role. Constraint `uq_staff_roles_staff_id` (migration `d7e5a91c4f02`) allows one `staff_roles` row per user. The migration split the two former dual-role accounts: `reception_fatima` (RECEPTIONIST) + new `cashier_fatima` (CASHIER), and `admin_tariq` (ADMIN) + new `owner_tariq` (OWNER). The extra role rows were moved (not deleted), the existing password hash was copied, and each split wrote an `ACCOUNT_SPLIT_SINGLE_ROLE` audit row.

### ADL-033: Every Login Lands on the Dashboard (Prompt 10C decision, implemented in Prompt 10D)
- **Status:** **Implemented (Prompt 10D).** Supersedes the per-role home routes of ADL-030.
- **Implementation:** `get_home_route_for_role` and `getRoleHomeRoute` return `/dashboard` for every role. The Dashboard renders by permission: holders of `dashboard.view` (front desk, Admin, Owner) see the financial Bento dashboard; others (LAB_TECH by default) see a money-free view built only from `/worklist/summary`. Every role gets buttons to its main work page (Invoices / My Worklist / Manage Users). `GET /dashboard` stays refused (403) to LAB_TECH.

### ADL-034: Roles, Users, Create User Tab and Per-User Permissions (Prompt 10C decision, implemented in Prompt 10D)
- **Status:** **Implemented (Prompt 10D)**; the permission layer is ADL-038.
- **Implementation:** Owner/Admin "User Management" page (`/users`) with a **Create User** tab: details, initial password, single role, lab section (LAB_TECH only), active flag, and a permission editor (role defaults with per-user add/remove). User list with edit, deactivate/reactivate and reset password (confirm dialogs). Lab sections are defined in `backend/app/core/lab_sections.py` and stored in `staff.lab_section`. Default section users: `tech_kamal` (Hematology, Room 101), `tech_nasrin` (Biochemistry, Room 102), new `tech_micro` (Microbiology, Room 105), new `tech_usg` (Ultrasonography, Room 204), provisioned by `backend/scripts/provision_prompt10d_users.py`. CASHIER now has its own explicit default permission set, equal to its previous behavior.
- **Routing:** unchanged in 10D; replaced by room-based routing in Prompt 10E (ADL-041). Since 10E a LAB_TECH must have a room and DOCTOR is a sixth role (ADL-045).

### ADL-035: Invoice Draft and Finalize (Prompt 10C decision, implemented in Prompt 10D)
- **Status:** **Implemented (Prompt 10D).** Revises ADL-012.
- **Implementation:** "Save Draft" (in the preview header, next to the draft tag) stores a DRAFT invoice: status `DRAFT`, placeholder number `DRAFT-xxxxxxxxxx`, no visit, no lines, no test orders or worklist entries, no samples, no payment, no drawer change. The form is kept in `invoices.draft_payload`. "Finalize" (replaces "Save Invoice") assigns the real `SD-` number from the sequence and performs every confirmation side effect in place on the same row (`finalized_at` is set). Finalize is not repeatable (409) and edits after finalize are refused (409). Drafts are listed with a Draft badge and a "Continue Draft" action; payment filters, dues, dashboard, patient history and global search exclude drafts; payments and receipt reprints are refused on drafts. Deleting drafts belongs to Prompt 11.

### ADL-036: Refund Amount Capped at What Was Paid (Prompt 10C decision, implemented in Prompt 10D)
- **Status:** **Superseded by ADL-040 (Prompt 10E).** The cap ("never more than paid") still holds; the 10D proportional "line share" allocation and the "last line takes the remainder" logic (10D report assumptions A4/A6) were removed. Self-approval stays blocked through `enforce_segregation_of_duties`; disbursement must use a channel actually used on the invoice; technicians never see amounts.

### ADL-037: Work Order and Schema-Change Policy (Prompt 10C owner decision)
- **Work order:** Prompt 10D implemented the decided items above. Prompt 11 (soft delete, draft discard, confirm dialogs, audit viewer) is **implemented** (ADL-052 to ADL-055); deactivate/reactivate stays in User Management.
- **Schema policy (in force):** see §5 below.

### ADL-038: Central Role & Permission Layer with Per-User Overrides (Prompt 10D)
- **Decision:** One module, `backend/app/core/permissions.py`, holds the role list (`ROLES`), the permission keys (derived from the checks that existed before 10D), the default set per role (identical to the previous behavior), one check function (`has_permission`) and one FastAPI dependency (`require_permission(key)`). Every route uses `require_permission`; the old `require_receptionist` / `require_admin` / `require_lab_tech_or_admin` guards and the inline role checks in services were replaced.
- **Overrides:** table `staff_permission_overrides` (staff, key, granted true/false, changed_by, changed_at). Effective permissions = role defaults, then overrides.
- **Safety rules:** no self-change of role, permissions or active state; only an OWNER may create, modify or assign OWNER; nobody can grant a permission they do not hold; the last active user with `user.manage` cannot be deactivated, demoted or lose `user.manage`; money permissions can never apply to LAB_TECH (even a direct DB override is ignored); every user-management action is audited.
- **Quirk kept on purpose in 10D:** `report.release_with_due` was in the CASHIER default set because the old check blocked only RECEPTIONIST. **Reversed in Prompt 10E** (owner decision): CASHIER no longer holds it; LAB_TECH gained `profile.manage`; new keys `worklist.reassign` and `worklist.doctor_queue`; DOCTOR added (ADL-045). 35 keys, 20 of them money keys; money keys can never apply to LAB_TECH or DOCTOR.

### ADL-039: Invoice Number Assigned at Finalize (Prompt 10D)
- **Decision:** Drafts never consume invoice numbers. A draft stores a unique placeholder (`DRAFT-` + 10 hex characters) in `invoice_no` / `temp_invoice_id`; the real `SD-` number is taken from `sequence_counters` only at Finalize. `invoices.visit_id` became nullable because the visit is created at Finalize.

### ADL-040: Refund Rule on Line Cancellation (Prompt 10E)
- **Status:** **Implemented (Prompt 10E).** Supersedes ADL-036's allocation and the 10D report assumptions A4/A6.
- **Rule (whole taka):** `net_after = invoice net − cancelled line's net price` (floored at the invoice urgent fee); `retained_paid = paid − (APPROVED + DISBURSED refunds)`; `refund = max(0, retained_paid − net_after)`; `due = max(0, net_after − (retained_paid − refund))`.
- **Examples (A 600 + B 400, cancel B):** paid 500 → refund 0, due 100; paid 800 → refund 200, due 0; paid 1000 → refund 400, due 0; paid 0 → refund 0, due 600.
- **Where:** `compute_cancellation_outcome` in `backend/app/services/refund_service.py`; used for eligibility, request creation (preview) and approval (binding, recomputed). Client-supplied amounts are ignored. `net`, `due`, `payment_status`, `refund_due` and `refund_status` are recomputed on every approval. Two-stage approval, self-approval block, original-channel disbursement and the technician money isolation are unchanged.

### ADL-041: Room-Based Routing and Reassignment (Prompt 10E)
- **Status:** **Implemented (Prompt 10E).** Replaces the department → first-technician routing and the `assigned_to_id` visibility rule.
- **Principle:** a test order is routed to a **room** (lab section), never to one technician. Rooms: Hematology 101, Biochemistry 102, Microbiology 105, Ultrasonography 204 (`backend/app/core/lab_sections.py`).
- **Mapping (one place):** `SECTION_KEYWORDS` / `section_for_test_fields` in `lab_sections.py` map `default_assignee`, then `department`, then the `performing_role` label to a room (e.g. "Microbiology & Parasitology"/"Microbiologist" → MICROBIOLOGY). Stored in `tests.lab_section` (backfilled by migration `f3c9a1d7e5b2`); tests that map to no room stay NULL.
- **Finalize:** `test_orders.lab_section` is set from the test (`routing_service.route_new_order`). Doctor-routed tests still go to `AWAITING_DOCTOR` and outsourced tests to `PENDING` (unchanged), with the room recorded. Otherwise `ASSIGNED` when the room has an active LAB_TECH, else `UNASSIGNED`.
- **Visibility:** LAB_TECH sees every order whose room equals their `staff.lab_section`; `worklist.view_all` (Admin/Owner) sees everything; DOCTOR sees the doctor queue (ADL-045). `assigned_to_id` only records who acted (sample taken / result saved).
- **Unassigned release:** creating, reactivating or moving a LAB_TECH into a room promotes that room's `UNASSIGNED` orders to `ASSIGNED` (audit `ORDER_ROOM_RELEASED`).
- **Empty room (Prompt 10F, ADL-051):** the reverse rule is now implemented: a room that loses its last active technician demotes its assigned-only orders to `UNASSIGNED`.
- **Reassign:** permission `worklist.reassign` (Admin/Owner by default, grantable) moves an order to another room any time before `COMPLETED` (Prompt 10F: also refused for cancelled and Not Performed orders, one rule `reassign_block_reason`; UI on the Assign Tests page, ADL-048) (`POST /worklist/{id}/reassign`, audit `REASSIGN_ROOM`; results and samples kept). The Assign Tests page sends the room key and stores the room name, never an id; front desk (`assignment.manage`) may route `UNASSIGNED` orders only.
- **Technician needs a room:** enforced by the user service and the Create User tab; DB CHECK `chk_staff_lab_tech_has_section` added where all rows comply (dev DB yes; the test DB has leftover test users without a room, so the CHECK was skipped there and the service rule applies).
- **One-off re-route:** `backend/scripts/reroute_orders_to_rooms.py` (dry run by default) set the room on existing open orders (dev DB: 34 orders changed, one audit row each).

### ADL-042: Payment Channels (Prompt 10E)
- **Decision:** channels are `CASH`, `BKASH`, `NAGAD`, `ROCKET`, `POS_CARD`, `BANK_TRANSFER`, `OTHER` (`backend/app/core/payment_channels.py`). The UI label "Card" is `POS_CARD`; the old frontend value `CARD` was removed (still accepted as an alias by the API). `OTHER` requires a typed channel name stored in `payments.channel_detail` and shown in invoice/payment views and receipts. `OTHER` is one business-day balance bucket. Business-day channel rows missing on an existing day are created safely when money arrives (`get_or_create_channel_balance`); migration `e8b2f4a6c1d3` added them to the open day. Refund disbursement through `OTHER` needs a reference and must match a channel used on the invoice.

### ADL-043: Urgent Fee Computed by the Backend (Prompt 10E)
- **Decision:** the backend is the single source of truth. It replicates the former UI rule exactly: for each urgent line `fee = max(100, round(20% × list price))` (half-up, whole taka; the UI's `Math.max(100, …)` is a **minimum** of 100). The fee is added after discounts (it is never discounted), included in `net`/`due`, stored in `invoices.urgent_fee` (and per line in `invoice_lines.urgent_fee` for display), and never refunded when a line is cancelled. Client-supplied fee amounts are ignored; the UI preview uses the same formula and shows the backend totals after save. Percentage discounts now round half-up like the UI.

### ADL-044: Age and Gender in the Invoice Payload (Prompt 10E)
- **Decision:** the invoice create/draft schema takes `age_value`, `age_unit` (`years`, `months` or `days`, so infants are recorded properly) and `gender` (`Male`, `Female`, `Other`). The silent defaults (age 30, Male) were removed. A draft may omit them; Finalize requires both (400). The visit stores the snapshot; the patient's stored gender is updated from the form; age is prefilled from the latest visit (`patients` has no age column). Limits are equivalent to 0–130 years.

### ADL-045: DOCTOR Role (Prompt 10E)
- **Decision:** sixth role in `ROLES`. No lab room. Defaults (assumption): `worklist.view`, `worklist.doctor_queue`, `worklist.update`, `result.enter`, `result.complete_doctor_routed`, `profile.manage` — money-free Dashboard, the doctor queue (`AWAITING_DOCTOR` from all rooms, plus completed doctor-routed orders) and its results, completion through the existing status endpoint. Money-restricted exactly like LAB_TECH (money keys can never be granted). The doctor sign-off screen was added in Prompt 15 (ADL-069); the Awaiting Doctor workflow itself is unchanged.

### ADL-046: Sample Requirement Rule (Prompt 10E)
- **Status:** **Superseded by ADL-050 (Prompt 10F, owner decision A5).** NULL/empty `sample_type` no longer means "no sample"; `requires_doctor` no longer makes a test imaging.
- **Decision:** one helper, `requires_sample(test, order)` in `backend/app/core/samples.py`: false for imaging tests (doctor-routed, narrative, ultrasonography room, USG/X-ray/radiology/imaging departments) and for `sample_type` NULL / empty / "None" / "N/A"; true otherwise (or on the FULL sample route). Used by status transitions, the result-entry guard, invoice sample status ("No sample needed"), worklist badges (`requires_sample`, `is_imaging`) and the Sample Taken action. Migration `e8b2f4a6c1d3` normalized "None"/"N/A" strings to NULL.
- **Note (historical, 10E):** 1,224 imported catalog tests had no `sample_type`, so they were "no sample required" under this rule. Reversed by ADL-050.

### ADL-047: Worklist Bento Tiles Are Filters; Ready Reports and Result Preview (Prompt 10E)
- **Status:** tiles-as-filters unchanged. The Ready definition (COMPLETED + ENTERED) and the preview source (`GET /worklist/{id}/result`) are **superseded by ADL-049 (Prompt 10F)**.
- **Decision:** on `/worklist` each KPI tile is a button that applies the matching filter (same as the status tabs), shows the active state (`aria-pressed`) and clears on a second click (`frontend/src/features/worklist/worklistTiles.ts`). New filters/tiles: **Ready Reports** (`status=READY`: COMPLETED orders with an ENTERED result), **Late** (`status=LATE`), **Unassigned** (Admin/Owner). Rows with a saved result have a **Preview Report** action that opens a money-free preview built from `GET /worklist/{id}/result`.
- **Final reports (Module 14, Prompt 16):** a report version is created only by finalization (ADL-070); `/reports` (Ready Reports & Delivery) lists seeded reports and every Final report.

### ADL-048: Assigned Tests View and Its Permissions (Prompt 10F, F1)
- **Status:** **Implemented (Prompt 10F).**
- **Decision:** the existing **Assign Tests** page (`/assignments`) is the home of the view (no duplicate page). It has two tabs: **Unassigned** (the existing routing list) and **Assigned Tests** (new). The new tab lists every test order with invoice number, patient, test, room, the room's active technician names or the explicit state `UNASSIGNED`, status, urgent flag and created time, with room/status filters and search. Backend: `GET /assignments/orders` (`assignment_service.list_assigned_test_orders`). **No money field** in the payload.
- **Permissions (existing keys reused, count stays 35):** viewing needs `assignment.manage` (RECEPTIONIST, CASHIER, ADMIN, OWNER by default; never LAB_TECH or DOCTOR). Moving needs `worklist.reassign` (ADMIN, OWNER by default, grantable). RECEPTIONIST/CASHIER are view only: no control is rendered and `POST /worklist/{id}/reassign` returns 403.
- **One reassign path:** the Reassign Room action reuses `POST /worklist/{id}/reassign` (`routing_service.move_order_to_room`: optional reason, append-only `assignment_history`, audit `REASSIGN_ROOM`). One rule, `reassign_block_reason`, decides reassignability for the endpoint, the list (`can_reassign`, `reassign_block_reason`) and the UI: refused with **409** for `COMPLETED`, cancelled (order or invoice line) and Not Performed (`REJECTED`/`SPOILED` or outcome `NOT_PERFORMED`).
- **Refresh:** after a move the list refetches; every list page also refetches on window focus (`frontend/src/utils/useRefetchOnFocus.ts`), so the receiving room sees the order on its next fetch.

### ADL-049: One Shared Ready Definition; Read-Only Result Preview (Prompt 10F, F2/F3)
- **Status:** **Implemented (Prompt 10F).** Supersedes the Ready rule and preview source of ADL-047.
- **Ready (owner expectation):** a result is Ready when `results.status = ENTERED` (submitted, not DRAFT) and the order is not cancelled (order or invoice line), not Not Performed (`REJECTED`/`SPOILED`, outcome `NOT_PERFORMED`, or a rejected/spoiled sample) and not `AWAITING_DOCTOR`. **Operational Complete is not required.** Reason: the owner expects a submitted result to be Ready at once; for `TECHNICIAN_FINAL` tests saving ENTERED already completes the order, but `BOTH_SIGNATURES` tests and cultures before stage FINAL stay `IN_PROGRESS`, and the old rule (COMPLETED + ENTERED) hid them.
- **Single source:** `ready_report_service.ready_clause()` is the only definition. It drives the Lab tile count (`/worklist/summary.ready_count`, counted in SQL on the same visible set), the Lab Ready tab/tile list (`/worklist?status=READY`), the row flag `report_ready`, and the sidebar list `GET /reports/ready` (all rooms). They cannot disagree.
- **Not an issued report:** Ready creates no `report_versions` row; the clause excludes orders that already have a Final report (they are Issued).
- **Preview:** `GET /worklist/{id}/result-preview` (`worklist.view` + room access) and `GET /reports/ready/{id}/preview` (`report.view`) both call `build_result_preview`: read-only, money-free, built only from the stored result snapshots (component, unit, reference range, critical limits as saved), available for DRAFT and ENTERED. It applies no result-entry guard, so completed, rejected or legacy orders with a saved result stay previewable. A DRAFT is shown with a "DRAFT, not a final report" banner. No print button, finalize, signature, QR, SMS or report version.
- **Money on `/reports/ready`:** `invoice_due` / `has_due` are returned only when the actor is not money-restricted and holds `payment.view` (`ready_report_service.can_see_money`); otherwise the keys are omitted.

### ADL-050: Sample Requirement Rule, Owner Decision A5 (Prompt 10F, F4)
- **Status:** **Implemented (Prompt 10F).** Supersedes ADL-046.
- **Decision (one helper, `requires_sample` in `backend/app/core/samples.py`):** (1) imaging tests never need a sample; (2) an explicit marker `None`, `N/A`, `NA` or `No sample` (trimmed, any case) means no sample; (3) **NULL or empty `sample_type` on a non-imaging test means unknown, so a sample IS required**; (4) any other value names a specimen. An order on the FULL sample route still needs a sample unless imaging.
- **Imaging (one place, `is_imaging_test` + `imaging_sql_clause` from the same constants):** lab room `ULTRASONOGRAPHY`, or a department containing `ultrasono`, `usg`, `x-ray`, `xray`, `radiolog` or `imaging`, or report template `NARRATIVE`. `requires_doctor` / performing role DOCTOR alone no longer count (dev catalog: TC-410 "Duodenal Tissue (M)" is doctor-read but needs a specimen). The worklist `IMAGING` filter uses the same definition. Dev catalog: 51 imaging tests, 1,199 needing a sample.
- **Gates (backend first, plain message "Take the sample before …: the specimen has not been collected yet"):** result template (400), result save DRAFT and ENTERED (409), operational Complete (400); **new in 10F:** culture stage change (400) and outsourced dispatch SENT (400). The line lock still happens only at Sample Taken (or imaging Perform Scan); invoice sample status shows "Awaiting collection" until then and "No sample needed" only for an explicit marker. Legacy orders completed without a sample under the 10E rule are not changed and show "Completed without sample".
- **Data:** no catalog value was changed, backfilled or seeded. The owner fills `sample_type`; until then NULL non-imaging tests require a sample (safe direction).

### ADL-051: Empty Room Demotes Assigned-Only Orders (Prompt 10F, F5, owner decision A11 "Unassigned thakbe")
- **Status:** **Implemented (Prompt 10F).** Replaces the 10E behaviour "ASSIGNED orders stay ASSIGNED".
- **Rule:** when a room loses its last active LAB_TECH, its orders in the assigned-only state become `UNASSIGNED` (room kept, so they stay visible to Admin/Owner and are released again when a technician joins).
- **Assigned-only (demoted):** status `ASSIGNED` with no sample row, no result (not even a DRAFT), no culture stage and no outsourced step, on a non-cancelled line. **Left as is:** `SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `PENDING`, `COMPLETED`, `CANCELLED`, `REJECTED`/`SPOILED`, and `ASSIGNED` orders with any recorded work. Reason: `test_orders.status` mixes assignment and progress; only the pure assignment state is reversible without losing work.
- **One routine for every path:** `routing_service.apply_technician_room_change` (demote the room left, release the room joined) runs after the staff change is flushed, in the same transaction, from create, deactivate, reactivate, room change and role change in `user_admin_service`, and from the `manage_users.py assign-role` CLI. Per demoted order: audit `ORDER_UNASSIGNED_ROOM_EMPTY`, event `ROOM_EMPTIED` and an append-only `assignment_history` row (CLI: no staff actor, so no history row; audit acting role `SYSTEM_CLI`). The user-action audit (`USER_DEACTIVATED`, `USER_UPDATED`, `USER_ROLE_CHANGED`) is in the same transaction.
- **Transaction fix:** `auth_service.revoke_all_user_sessions` committed on its own; on deactivate/role change/password reset it committed the user change before the audit row. User-management calls now pass `commit=False`, so the user change, its audit row and any demotion commit once.

---

## 4. Security & Authentication Architecture (Prompt 09)

Header-based identity switching (`X-Staff-Role`, `X-Staff-Id`) was **completely removed** in Prompt 09. Authentication is strictly enforced via cryptographically validated server-side sessions:

### Session Lifecycle & Storage
- **Session Table:** `auth_sessions` tracks `session_token_hash` (SHA-256), `staff_id`, `tenant_id`, `acting_role`, `created_at`, `expires_at`, `last_seen_at`, `revoked_at`, `user_agent`, `ip_address`.
- **Token Delivery:**
  - Browser UI: Transports via `HttpOnly`, `SameSite=Lax`, `Path=/` cookie named `medscope_session`. JavaScript cannot access the token.
  - Headless / API Clients: Transports via `Authorization: Bearer <raw_token>` or `X-Session-Token` header.
- **CSRF Defense:** State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) authenticated via cookie require a non-empty `X-Requested-With` header (e.g. `XMLHttpRequest`).
- **Session Timeouts:**
  - Idle Timeout: Sessions inactive for more than 120 minutes are revoked automatically.
  - Absolute Lifetime: Sessions expire 24 hours after creation regardless of activity.
- **Password Security:**
  - Hasher: Argon2id via `argon2-cffi`.
  - Password Policies: Minimum 8 characters; password cannot match username.
  - Brute-Force Lockout: 5 consecutive failed attempts trigger automated account lock (`locked_at = utc_now()`). Requires Admin/Owner unlock.
- **Role Governance (single role per user since Prompt 10D):**
  - Table `staff_roles` maps staff members to permitted operational roles (`RECEPTIONIST`, `CASHIER`, `ADMIN`, `OWNER`, `LAB_TECH`, `DOCTOR` — DOCTOR added in Prompt 10E), one row per user (`uq_staff_roles_staff_id`).
  - Each user holds exactly one role (Prompt 10D, ADL-032); the session's `acting_role` equals it and cannot be switched. `/auth/acting-role` was removed.
  - Authorization is the central permission layer (ADL-038): `CurrentActor.permissions` = role defaults + per-user overrides, checked by `require_permission(key)`.
  - All audit log events persist the user's `acting_role`.

---

### ADL-052: Soft Delete for User, Doctor, 3rd Party and Catalog Test (Prompt 11)
- **Status:** **Implemented (Prompt 11); owner browser acceptance pending.**
- **Rule:** four entities (User/Staff, Doctor and 3rd Party/Referrer, Catalog Test) get a reason-required soft delete: `deleted_at`, `deleted_by_id`, `delete_reason` (nullable, on `staff`, `referrers`, `tests`; migration `a4d8c2e6f1b7`). NULL `deleted_at` = not deleted. A deleted row keeps every column and reference; it is hidden from every normal list and from NEW selection only. Existing bills, lines (they carry their own snapshot), orders, results, commission and ledger rows are untouched. Doctors and 3rd parties share one table (`referrers.referrer_type`), so one delete/restore covers both.
- **History:** delete and restore each write an append-only audit row (`*_SOFT_DELETED`, `*_RESTORED`) in the same transaction; the reason is in the delete row's `after_value`. A restore clears the three columns, so a later re-delete never overwrites the earlier trail (it lives in the audit log).
- **Deleted views:** Admin/Owner only (the manage permission of each entity); one shared screen `Catalog & Deleted` for all four entities.
- **Permissions:** `user.manage` (existing) for users; two new keys `referrer.manage` and `test_catalog.manage` (Admin and Owner by default, grantable) because the existing keys (`referrer.create`, `test_catalog.view`) are front-desk keys that Receptionist/Cashier also hold, so reusing them would let a Receptionist delete a doctor.
- **Not touched:** Patient, Confirmed/Finalized Invoice, Payment, Refund, Result, Sample, Audit row, Business day, Ledger entry and Stock movement stay permanently non-deletable.

### ADL-053: Deleted Is Not Inactive (User) (Prompt 11)
- **Status:** **Implemented.** `set_user_active` (deactivate/reactivate, no reason) is unchanged. Delete is a separate heavier state: a deleted user is **also forced inactive** (so the 10F room-emptying routine and `revoke_all_user_sessions(commit=False)` run exactly as for deactivate) **and** `deleted_at` is checked at login and session validation, so a deleted user never works even if someone flags them active. Reactivating a deleted user is refused (restore first). **Restore** clears the delete fields only; the user stays inactive until an Admin/Owner uses Reactivate (which runs the normal release-on-join). Restore moves no orders. Same guards as deactivate: no self-delete, Owner accounts only by Owner, last active user-manager protected.

### ADL-054: Draft Invoice Discard Is a Real Delete (Prompt 11)
- **Status:** **Implemented.** `DELETE /invoices/{id}/draft` permanently removes a DRAFT invoice (no reason, no restore, no soft-delete flag). Allowed for the draft's creator or any ADMIN/OWNER, backend-enforced; any non-DRAFT invoice returns 409. A draft by design has no visit, lines, orders, samples, payments or commission; if any such row is found the discard is refused (409) instead of deleting data another record depends on. One `INVOICE_DRAFT_DISCARDED` audit row (with the `DRAFT-...` placeholder number) is written before the delete, in the same transaction, so a durable record survives. Reason for the different rule: a draft is scratch work with no legal or financial standing; everything else is a record that must stay.

### ADL-055: Minimal Audit Log Viewer and the Shared Confirm Dialog (Prompt 11)
- **Status:** **Implemented.** A deliberately small slice of Module 23: read-only `GET /audit-logs` (+ `/audit-logs/meta`) over the existing `audit_logs` table, filters action / entity type / actor / date range, newest first, paginated; permission `audit.view` (Owner by default, grantable to Admin, never LAB_TECH/DOCTOR; it is a money-exposing key because audit text can contain amounts). No write, delete or export. **Module 23 still needs:** export logging, report-view logging, vendor session log, retention/legal-hold policy, audit-coverage review of actions outside Prompt 11's own.
- **Frontend convention:** `components/common/ConfirmDialog.tsx` (built on `Modal`) is the one confirm dialog: it names the exact item, states the effect in one sentence, requires a non-empty reason before Confirm when `requireReason` is set, and has a Cancel. Soft delete, restore and draft discard all use it; do not add per-screen confirmations.

### ADL-056: Imaging Lock Moves to Result Completion; IMAGING_PERFORMED Is a Status Label Only (Prompt 12)
- **Status:** **Implemented (Prompt 12); owner browser acceptance pending.** Behavior change, **no schema change** (`invoice_lines.is_locked/locked_at/locked_reason` already exist; head stays `a4d8c2e6f1b7`).
- **Old:** `POST /worklist/{id}/imaging-performed` set `is_locked = true` (reason "Imaging examination performed...") and moved the order to `AWAITING_DOCTOR`; `refund_service` and the invoice view additionally blocked cancellation for `COMPLETED`/`AWAITING_DOCTOR`/`PERFORMED` imaging orders. Sample tests lock at Sample Taken.
- **New:** a test that needs no sample (`not requires_sample()`: imaging, explicit no-sample markers) locks when its order becomes `COMPLETED` (result completion), via `line_lock_service.lock_line_at_result_completion`, called from the two completion paths (technician-final result save, and `POST /worklist/{id}/status` = `COMPLETED`). `IMAGING_PERFORMED` is **kept as a non-locking status label** (event, audit row, order to `AWAITING_DOCTOR`, "PERFORMED" badge) because the workflow still shows that the scan physically happened. Imaging-specific cancel branches were **removed**: before completion an imaging line is an ordinary unlocked line (ordinary cancel/refund path, no special approval or wastage step); after completion it is locked like any other line. Sample tests are unchanged (lock at Sample Taken / spoil).
- **Finding recorded:** the pre-Prompt-12 code had no result-completion lock for any no-sample test, and no line-level D14 unlock. Prompt 12 therefore added both as one uniform mechanism rather than an imaging-specific one.
- **D14 owner same-day unlock:** `POST /invoices/lines/{id}/unlock` (permission `invoice.line_unlock`, OWNER only by default), reason required, only on the business day the line was locked (`locked_at` not before the open day's `opened_at`), audit `INVOICE_LINE_UNLOCKED` in the same transaction; the order, result and sample are not changed. One path for every test type.
- **Stock:** `trigger_specimen_stock_deduction` is boundary-only and was never wired to imaging; nothing to move.

### ADL-057: Test Fixture Cleanup by End-of-Session Purge (Prompt 12)
- **Status:** **Implemented.** Tests create throwaway users through the API and commit, so a per-test rollback is impossible. `tests/fixture_cleanup.py` hard-deletes Staff rows with generated names (`_` + 6 to 8 hex characters) that are not named seed accounts, in an autouse session fixture teardown in `conftest.py`. It asserts `current_database() == 'medscope_test'` first (the existing hard guard is untouched). References are handled generically from `pg_constraint`: cascade tables deleted, nullable references set NULL, NOT NULL references re-pointed at `owner_tariq`, and audit rows about the purged user deleted (otherwise a reused staff id matches stale audit rows). `conftest.py` no longer lowers `staff_id_seq` (it uses `GREATEST(last_value, MAX(id))`) so ids are never reused. Never applied to `medscope_dcms`.

## 5. Schema Change Policy (Alembic Is the Single Source of Truth)

- Every schema/DDL change for the PostgreSQL stack (new columns, new tables, relations, indexes, constraints) is made **only** through an Alembic migration in `backend/alembic/versions/`.
- The Alembic head (currently the single head `a4d8c2e6f1b7`, Prompt 11 soft-delete columns; Prompt 10F reviewed with no schema change) is the single source of truth for the schema. `alembic check` must report no pending operations against the ORM models.
- Seeding and cleanup scripts (for example `backend/scripts/seed.py`; the former git-ignored `cleanup_test_data.sql` no longer exists) are development/testing utilities **outside** the Alembic chain. They must not create or alter schema, and they are not product features.

### ADL-058: One Cancellation Calculation, Server-Side and Read-Only
- **Status:** Implemented. No schema change.
- **Decision:** `refund_service.compute_cancellation_outcome` (the Prompt 10E rule, ADL-040) is the **only** place the cancellation arithmetic lives. It returns the read-only breakdown (`invoice_total`, `paid_total`, `line_price`, `retained_amount`, `refund_amount`, `due_after`, `net_after`). The line preview (`GET /refunds/preview/{line_id}`), the whole-invoice preview, the stored refund amount and the invoice net/due written at cancellation all use it; the whole-invoice preview runs the same function per line through a read-only stand-in invoice. There is no editable amount: a client `amount` or `request_type` is ignored.
- **Pending requests:** for a request that still waits for approval the amount stored at request time is a preview snapshot; the binding amount is recomputed at approval and the approval view (`GET /refunds/requests/{id}/breakdown`) shows the live figures beside the snapshot.
- **One invoice-status derivation:** `derive_invoice_refund_status` is used by every caller.
- **Rationale:** two code paths for one number is the root cause of a modal that disagrees with the grid.

### ADL-059: Explicit Line Cancellation State, Derived
- **Decision:** a line's state is derived from `invoice_lines.status` plus its **newest** refund request, with no column: `NONE`, `CANCELLATION_REQUESTED` (a request waiting for approval), `CANCELLED_REFUND_PENDING`, `CANCELLED`, `CANCELLED_REFUNDED` (a rejected request leaves `NONE`). Returned on the invoice detail as `cancellation_state`, `display_status`, `can_request_cancellation`.
- **Why no schema change:** `request_type` and `status` are free `String(50)` columns and the state is a pure function of existing rows, so nothing can drift out of sync.

### ADL-060: One Path Per Lock State
- **Decision:** exactly two cancellation paths with the lock event as the boundary: unlocked -> `PRE_SAMPLE_CANCELLATION` (Cancel Test / Cancel Whole Invoice), locked -> D15 `D15_NOT_PERFORMED` (Lab Tech). The generic cancellation endpoint never delegates to the D15 handler and never picks a line on its own.
- **Enforcement:** one lock check (`line_lock_blocker`: `is_locked`, or a COLLECTED/REJECTED/SPOILED sample) is used by eligibility, cancellation and approval. Cancellation takes a row lock on the line (on every line for a whole invoice). Conflicts return 409 with `{code, message}` (`SAMPLE_ALREADY_TAKEN`, `REQUEST_PENDING`, `ALREADY_CANCELLED`) so the UI can show the "Sample already taken" dialog.
- **Atomicity:** a cancellation (all lines, invoice figures, refund rows, audit rows) and a disbursement each commit in one transaction.

### ADL-061: Cancellation State Wins the Line Display
- **Decision:** the invoice line shows `display_status`: a cancellation/refund state, when present, takes precedence over the sample-status label. The raw `sample_status` is unchanged (clinical truth). Cancellation and disbursement fire the existing refresh event (`announceInvoiceChange`, an alias of the `medscope:sample-changed` mechanism).

### ADL-062: No Approval Step for Pre-Lock Cancellation
- **Status:** Implemented. No schema change.
- **Decision:** `refund_service.initiate_refund_request` (one line) and `cancel_invoice_now` (whole invoice) execute the cancellation immediately through one internal step, `_cancel_line_now`: line `CANCELLED`, test order cancelled with an event, invoice net/due/refund_due/payment status updated, the `RefundRequest` row stored as the record (`APPROVED` when a refund is due, `COMPLETED` when 0), and a `PRE_LOCK_CANCELLATION` audit row, all in the caller's single transaction. `reviewed_by_id` stays NULL and `review_notes` says no approval step applied.
- **Why:** owner decision of 2026-11-14 (SCOPE §8): no sample taken means no money or stock consumed.
- **Not covered:** D15, imaging-started cancellation and owner same-day unlock keep their approval. `admin_review_refund_request` remains for requests that wait for approval.
- **Permission:** no new key (`refund.request`).

### ADL-063: Whole-Invoice Cancellation Reuses the One Calculation
- **Decision:** `cancel_invoice_now` cancels every remaining line of a Confirmed invoice together, only when no line is locked or pending (409 otherwise, nothing changes; row locks on all lines). Money uses `compute_cancellation_outcome` once per line in id order, each line seeing the refunds already committed by the lines before it. Totals: refund = sum of the per-line refunds; retained, new due and new total = the final step's. For the owner case (9000, paid 3000) the whole invoice refunds 3000 (0 on the 5000 line, 3000 on the 4000 line), retained 0, due 0; the urgent-fee floor still applies.
- **API:** `GET /refunds/preview-invoice/{invoice_id}` (a blocked invoice answers `can_cancel=false` with `blocker`) and `POST /refunds/cancel-invoice`.

### ADL-064: Referrer Fixtures Purged by the Same Teardown
- **Decision:** `tests/fixture_cleanup.purge_fixture_referrers` extends the ADL-057 end-of-session purge: referrers whose names match the fixture patterns (`Partner Agent N`, `Dr. Prescriber N`, `Dr. E2E Test N`, `Dr Probe hex6`, `Probe Clinic hex6`, `Dr Audit hex6`) are hard-deleted in `medscope_test` only (database name asserted first); `invoices.referrer_id` / `prescribed_by_id` pointing at them are set to NULL and their audit rows go. Seed referrers (ids 1-10) never match.

### ADL-065: Cancelling and Paying Out Are Always Separate Actions
- **Status:** Implemented. No schema change.
- **Decision:** the cancellation schemas (`RefundRequestCreate`, `InvoiceCancellationCreate`) have no payout fields (a stray field is ignored) and the service has no combined payout path. A cancellation ends with the refund row `APPROVED` (refund due) or `COMPLETED` (0). `disburse_refund` is the only place money is paid out (original channel, reference rule, cash drawer, commission-reversal audit).
- **UI:** the cancel modal has no channel field and says that no money is paid by the click. A "Refund of ৳X is pending payout [Disburse now]" banner on the invoice opens the Disburse modal: a second deliberate click with its own amount and channel display; nothing is pre-submitted.
- **Why:** a combined one-click path makes a wrong amount or channel harder to catch or walk back.

### ADL-066: Business Day State Is a Money-Free Fact Readable by Every Role
- **Decision:** `GET /business-day/state` (`get_current_actor` only, no permission key) returns `{is_open, day_number, business_date}` from the same query as the full status. The auth context calls it for every role; closed maps to null, and the header shows "Business Day Closed" only when `is_open` is false. The full `/business-day/status` keeps `business_day.view` and its cash and channel figures, so Lab Tech (no `business_day.view`) never receives money (M11.3).
- **Why:** the header used to fetch the day only for users holding `business_day.view`; Lab Tech has no such key, so the header fell back to "Closed" while the day was open.

### ADL-067: Reference Ranges Are Versioned Bands (D24)
- **Status:** Implemented (Prompt 14). Schema change: migration `b7e3d91c5a24`.
- **Decision:** the table `reference_range_versions` holds one **band** per row: component, `sex` (`ANY`/`MALE`/`FEMALE`), `age_days_min`..`age_days_max` (inclusive; max NULL = no upper limit), `ref_min`/`ref_max`, `critical_min`/`critical_max`, optional report text, `version_no`, `is_current`, `effective_from`, `retired_at`, `created_by_id`, `retired_by_id`, `change_note`. A partial unique index allows one current row per (component, sex, band start). **Rows are never edited or deleted:** a new version inserts `version_no + 1` and marks the old row not current; retiring marks it not current. Same-sex current bands cannot overlap in age (409); an `ANY` band may sit beside sex bands.
- **Component columns:** the old single `ref_min`/`ref_max`/`critical_min`/`critical_max`/`reference_range_text` columns were **dropped** from `test_components` after being copied into version 1 (counts and every value verified inside the migration before the drop). `impossible_min`/`impossible_max` stay on the component: they are physiological limits, not an age/sex-dependent range.
- **Permission:** `test_catalog.manage` (Admin/Owner, not money); no new key.

### ADL-068: Band Selection and Snapshot at Result Entry (D24)
- **Decision:** `reference_range_service` converts entered age + visit date to total days (calendar-aware) and the visit gender to a sex key, then `pick_band`: (1) current band for that sex covering the age -> `MATCHED`; (2) current `ANY` band covering the age -> `MATCHED` when the component has no sex bands, `FALLBACK_ANY` when it has; (3) none -> `NO_BAND`. A gender of Other/Unknown can only match `ANY` bands. The server chooses the band (a client range for a known component is ignored) and snapshots `ref_min`, `ref_max`, `critical_min`, `critical_max`, `reference_range` text, `reference_range_version_id` and `range_match` onto the `result_items` row; the flag and the template shown to the technician use the same band.
- **No silent wrong band:** `NO_BAND` computes no flag (never "Normal") and the UI says the row needs manual review. The pre-D24 single range is not used as a guess.
- **History is safe by construction:** result items store values, not a live link; the band id is for traceability only, and bands are immutable.

### ADL-069: Doctor Sign-off Is a Separate Approval Record; Two Paths, One Permission (D22)
- **Status:** Implemented (Prompt 15). Schema change: migration `c9a4e7b2d815`.
- **Decision:** the doctor-side signature is a row in `doctor_approvals` (one per test order, append-only) holding who clicked (`approved_by_user_id`), which doctor it is attributed to (`doctor_id`, with name and registration-number snapshots), `is_attestation`, notes and time. It sits beside the technician's sign-off (`results.entered_by_id`), never over it. Approving reuses the existing completion step: `AWAITING_DOCTOR` / `IN_PROGRESS` -> `COMPLETED`; no new status and no `doctor_approved_at` column, because the existing status plus the approval row already say "approved".
- **Two paths in one service** (`doctor_approval_service`): Admin/Owner record it for a chosen doctor with a mandatory attestation; a DOCTOR login approves for its own linked doctor profile (`staff.doctor_profile_id`). Visibility of a DOCTOR is scoped by `test_orders.assigned_doctor_id` in the query, the same idea as the Lab Tech room scope; the assignment is set by Admin/Owner (or filled from the doctor chosen at approval).
- **Permission:** no new key. `result.complete_doctor_routed` already has exactly the needed holders (Admin, Owner, Doctor; not Receptionist, Cashier, Lab Tech) and is not a money key. The service additionally restricts Path A to ADMIN/OWNER, so granting the key to another role by override does not allow attesting for a doctor.
- **Why a table and not columns on the order:** the audit needs the actor, the attributed doctor, the attestation flag and snapshots for the printed report; finalization reads this row (ADL-070).
- **Deliberately not built:** reject / send back to the technician.

### ADL-070: Final Report = Immutable `report_versions` Row; Finalization Follows the Approval Rule (Module 14, D22)
- **Status:** Implemented (Prompt 16). Schema change: migration `d2b6f8a1c439`.
- **Investigated first:** `COMPLETED` on a test order was only ever an operational status (set by a technician-final result submit, the status action, or a doctor approval); nothing read it as "the report is Final" and no code created a report version from a result. The `report_versions` table already existed with seeded rows (status `FINAL_AUTHORIZED`) feeding delivery and the Issued Reports tab, so it was extended instead of adding a second table. A culture's stage `FINAL` is a lab lifecycle step that never created a report; it is now only one of the conditions for finalization.
- **Decision:** Draft = result `DRAFT` (no row). Final = one `report_versions` row holding a content snapshot (the result preview built from the items' own range snapshots) and text signatures. `COMPLETED` stays operational.
- **Who finalizes:** technician-final = explicit Finalize click (a distinct step from submitting the result). Doctor-required and both-signature = **automatically in the same transaction as the doctor approval**: approval is the scope's "approval-as-finalization", a second click would only add a half-approved state, and one transaction means either both the approval and the report exist or neither. Both-signature additionally needs the technician sign-off (an ENTERED result). Cultures also need stage FINAL: an approval given earlier finalizes when the stage reaches FINAL; a technician-final culture needs the click then. The same rule is implemented once (`report_finalization_service.finalize_blocker`).
- **Blocked states:** cancelled, rejected, spoiled, Not Performed, rejected sample, no submitted result, missing approval, culture not FINAL, already Final.
- **Immutability:** ORM `before_update` guard plus a database trigger over every content column; one Final per order by a partial unique index; result save is refused once a Final report or a doctor approval exists. Corrections (new version, Superseded) are Module 15; if the underlying data changes later the stored report does not.
- **Order status after finalizing:** `COMPLETED` (line locked) for orders that were still IN_PROGRESS / AWAITING_DOCTOR.
- **Permission:** no new key: Finalize uses `result.enter` plus the existing room / doctor-queue access check ("whoever can currently complete that order"); viewing uses `report.view`.
- **Cancellation after Final:** the existing flows are unchanged. A COMPLETED result locks its line, so ordinary cancellation is refused; the owner same-day unlock (D14, Prompt 12) can unlock a line but does not change the order, result or report; `list_deliverable_reports` already hides reports whose line is CANCELLED. No report cancellation mechanism was built (Module 15 / 29).

### ADL-071: Report-ready SMS Is a Placeholder Row; Edit Conflict Is an Optimistic Check (Module 14)
- **Decision:** finalization writes a `notification_log` row (`REPORT_READY_SMS`, `PENDING_INTEGRATION`, patient id only) and an audit row `REPORT_READY_NOTIFICATION_DUE`. No gateway call, no phone number, no message text: Module 25 will build real sending, like the stock-deduction boundary of Prompt 06.
- **Edit conflict:** `results.updated_by_id` plus an optional `expected_updated_at` on result save. A mismatch returns 409 naming who changed it and when. Not a lock or collaborative editing; a save without the field behaves as before. There was no such guard before. The result modal has no auto-save (Save Draft is a button), so none was disturbed.

### ADL-072: Owner-editable Center Settings Are a Key / Value Table (Prompt 17)
- **Status:** Implemented. Schema change: migration `e5d7a2c9b138`.
- **Investigated first:** no settings mechanism existed; role discount maximums and similar values are in code. The held-report switch and the write-off limit needed an Owner-editable place, so `tenant_settings` (tenant, key, value) was added with the known keys and defaults in `settings_service`. A missing row means the default, so behavior is unchanged until the Owner edits a value (`report_hold_when_due` default on, `writeoff_admin_limit` default 500).
- **Permission:** new key `settings.manage` (Owner only). Reading the settings needs only a signed-in session (no secrets).
- **Audit:** every change writes `SETTING_CHANGED` with the old and new value.

### ADL-073: Write-off Is a Separate Bad-debt Record That Lowers the Due, Never a Discount (D11)
- **Decision:** `due_writeoffs` holds each write-off (APPLIED, PENDING_OWNER, REJECTED) with who asked, who decided, the Admin limit at the time and the reason. Applying one does `invoices.due -= amount` and `invoices.written_off += amount`; `gross`, `discount`, `net` and `paid` are untouched, so discount reporting cannot be affected. The cancellation arithmetic subtracts `written_off`, so written-off money is not owed again.
- **Gate:** Admin may apply directly when `written_off + amount` stays within the limit (cumulative per bill, so splitting cannot dodge it); otherwise a PENDING_OWNER request is created and only the Owner can approve or reject. Owner writes off directly. One pending request per bill. Row locks (`FOR UPDATE`) protect the amount checks.
- **Not done on purpose:** no drawer effect (a write-off moves no cash); no write-off reversal. The journal posting (Dr Bad debt, Cr Patient receivable) was added in Prompt 18 (ADL-075).
- **Permission:** new key `due.writeoff` (Admin, Owner; money). The service also checks the role, so a granted key does not let another role write off.

### ADL-074: Doctor Balances Are Two Kinds in One Append-only Source Table (D43)
- **Decision:** `doctor_balance_entries` holds signed rows per doctor with a `kind` of `WHOLESALE_RECEIVABLE` or `PROFESSIONAL_FEE_PAYABLE`. The balance view sums each kind separately and never merges them (no total field exists in the response). Nothing writes the table yet: the writers (wholesale billing, held visit fees, payouts) are Modules 28 / 20. The view says so, instead of showing invented numbers.
- **Permission:** new key `doctor_balance.view` (Admin, Owner; money), because these figures sit next to commission data that the front desk must not see.
- **Handover findings (no decision needed):** `report_deliveries`, the due-hold rule and the reprint log already existed; the printable endpoint wrote its reprint log row without committing, so no reprint was ever persisted. It now commits and counts earlier prints (`reprint_count`, Duplicate from the second print or after a handover).

### ADL-075: The Journal Is Append-only and Balanced, Enforced by the Database (Module 21, Prompt 18)
- **Status:** Implemented. Schema change: migration `f9a2c4d6e8b1`.
- **Investigated first:** no journal or ledger existed in the API; the cash drawer is `business_day_channel_balances`, maintained by payments and cash refunds, and stays as it is. The legacy `accounting.py` is the old Streamlit module and was not touched.
- **Decision:** `accounts` (a small chart seeded per tenant on first use), `journal_entries` (event, source, date, business day, `reverses_entry_id`, `is_adjustment`) and `journal_lines` (one-sided positive debit or credit, reserved nullable `referrer_id` for a later commission module). Triggers refuse UPDATE / DELETE on lines and on entries (only `created_by_id` may be re-pointed, which the test-fixture staff purge needs) and a deferred constraint trigger refuses, at commit, an entry whose debits differ from its credits. The service also validates before insert.
- **Posting is a side effect only:** `accounting_service` is called from bill confirmation, payment, cancellation, refund disbursement and write-off, after their own logic; none of those flows was changed. Only real events are posted; commission, visit-fee handover, consultant fee and outside-lab cost are deferred (Modules 19 / 20 / 28 do not exist). Cancellation posts the cancelled line's revenue and the net reduction, so the Patient receivable account follows the sum of `invoices.due` for posted bills.
- **Not backfilled:** earlier bills and payments have no entries (inventing historical postings was ruled out). **Reports** read the journal (and the existing dues list) and never write; CSV export is a small new helper because no export mechanism existed.
- **Permission:** new key `accounting.view` (Admin, Owner; money): no existing Admin/Owner key describes the reports and the journal.

### ADL-076: Day Close Reuses the Business Day; Reopen Is a Status, Adjustments Are Journal Entries (Module 22, Prompt 18)
- **Decision:** expected cash is computed from source tables (payments of the day, disbursed refunds in the day's time window, `day_movements`), not from the journal, so it is correct for a day that started before the journal did. `POST /business-day/close` now requires `counted_cash` (the old call without a body is gone) and writes `closing_cash_counted`, `closing_expected_cash`, `closing_variance`, per-channel `closing_counted` / `variance` (columns that already existed and were unused) and `variance_reason`; the variance is journaled. The tolerance is a `tenant_settings` key (`cash_variance_tolerance`), not a second settings mechanism.
- **Closed-day protection:** the journal service refuses an ordinary entry on a CLOSED or REOPENED day (409); payments, refunds and movements only ever target the OPEN day. Reopen sets status `REOPENED` (Owner, reason, audited); a reopened day does not conflict with the one-open-day index. Adjustments are reversal entries or balanced manual entries posted with `is_adjustment`; re-closing keeps the original close time and posts only the change in variance. Close authority is unchanged (`business_day.close`, Admin / Owner).
- **Offline sync:** the "no unsynced items" condition always passes (reported as 0); it is not a real check.

### ADL-077: A Bank Deposit, Owner Withdrawal and Small Expense Are Cash Movements of the Open Day
- **Decision:** `day_movements` (kind, amount, note, journal entry, creator) is never edited or deleted. All three lower the drawer's expected cash; an owner withdrawal is Owner only; an expense needs a what-for; none may exceed the expected cash. Each posts Dr (Bank / Owner drawings / Operating expense), Cr Cash.

### ADL-078: Cash-affecting Actions Require an OPEN Day; One Active Day; Adjusting Entries Are an Expected-cash Term (Prompt 18B)
- **Root cause fixed:** payments and bill confirmation looked up the OPEN day and treated "none found" as "no day tracking", which skipped the closed-day check in the journal service, so money taken on a CLOSED or REOPENED day was recorded with `business_day_id = NULL` and reconciled nowhere. `accounting_service.require_open_day` is now the one lookup used by payment, bill confirmation and refund payout: 409 for a closed or reopened day, 400 when no day was ever opened. The journal service was not changed. The only remaining `business_day_id = NULL` postings are write-off and cancellation (no cash moves); that is deliberate.
- **One active day:** `open_business_day` refuses while a day is OPEN or REOPENED. No schema change.
- **Adjusting entries:** `compute_summary` adds, per channel, the net debit minus credit of adjusting entries on that channel's account for the day, excluding entries that also touch Cash variance (the count mechanism). The formula otherwise stays source-table based (days before the journal still compute correctly). No schema change.
- **Bank deposit:** Admin or Owner (owner decision); owner withdrawal stays Owner only.

### ADL-079: Doctor / 3rd-party Edit Is a PATCH on the Existing Row (Prompt 19)
- **Investigated first:** no edit existed anywhere (create inline in billing, soft delete / restore, nothing else), and there is no rate-card mechanism in the repository. **Decision:** `PATCH /referrers/{id}` with `referrer.manage`; only the sent fields change; commission fields are not accepted or returned; a deleted record is refused (409); each change is audited with old and new values. **Snapshot safety:** `doctor_approvals` copies the doctor's name and registration number at signing; invoices store only `referrer_id` and report lists read the live name (unchanged behavior, flagged, not reworked). No schema change.

## Audit Trail (Module 23, Prompt 19B)

- **One audit mechanism:** `audit_logs`, written only through `audit_service.log_audit_event` in the same transaction as the change. `reprint_logs` was folded into it (`log_reprint_event` is now a thin wrapper that writes `INVOICE_REPRINTED` / `REPORT_REPRINTED` rows with the acting role).
- **Append-only in the database,** not only in the code: triggers refuse UPDATE, DELETE and TRUNCATE for every writer. No purge, archival or retention logic exists; rows are kept forever. Only test fixtures in `medscope_test` switch the triggers off, inside their own transaction (`tests/fixture_cleanup.py`).
- **Viewer and export:** `backend/app/api/v1/endpoints/audit.py` (`audit.view`): filters, free-text search, CSV export that audits itself. The business-domain grouping of action names is in `backend/app/core/audit_domains.py` (action stays free text; no registry).
- **Report views** are logged by the three report GET endpoints through `report_service.log_report_view` / `log_ready_result_view`.
- **Vendor / session log:** deferred, no current subject (see `docs/SCOPE.md` section 15).
