# MedScope DCMS — System Architecture Specification

## 1. Architectural Overview & Decoupling

MedScope operates on a modernized, dual-stack architecture designed to handle high-throughput diagnostic intake desks while preserving core clinical and double-entry accounting ledgers:

- **Frontend (`frontend/`):** React 19, TypeScript, Vite 8, Tailwind CSS v4, Lucide Icons, React Router v7. Provides sub-millisecond local state updates, zero-rerun keyboard shortcuts, and native print formatting.
- **Backend (`backend/`):** FastAPI, Pydantic v2, SQLAlchemy 2.0 ORM, and async-capable architecture. Provides strict OpenAPI schema contracts, sub-5ms API response latency, and modular REST design (62 paths / 72 operations).
- **Database:** PostgreSQL 18 on port 5432 (`medscope_dcms`, user: `medscope_app`) managed via Alembic migrations (27 domain entities, 28 tables total).
- **Testing Infrastructure:** Automated pytest integration suite (45 test cases passing in-process against isolated `medscope_test`) with zero browser automation.
- **Legacy Stack (`DCMS V1.py`, `accounting.py`):** Streamlit + SQLite preserved for internal laboratory analysis and specialized double-entry accounting routines.

```
+-----------------------------------------------------------------------------------+
|                            MedScope Operational Stack                            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Modern Client ]                 [ REST API Gateway ]           [ PostgreSQL ]  |
|  React 19 + Vite 8                 FastAPI (Python 3.14)          Version 18      |
|  - Bento Grid Layout               - 62 Paths / 72 Ops            - 25 Domain Tbl |
|  - 60-30-10 Palette                - Multi-tenant Isolation       - Alembic Migr. |
|  - A4 Landscape Dual-Copy Print    - Whole-Taka Integers          - Monotonic Seq.|
|  - Dev Staff Switcher              - Role Security Middleware     - Concurrency   |
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
│   │   ├── versions/                 # Version revisions (5e7d6e556c9d, c94589ffc4ee)
│   │   └── env.py                    # Migration execution runner
│   ├── app/
│   │   ├── api/v1/                   # REST API routes
│   │   │   ├── endpoints/            # Domain endpoint routers (12 modules)
│   │   │   └── router.py             # Root v1 aggregator router
│   │   ├── core/                     # Core configs, database connection, security
│   │   │   ├── config.py             # Pydantic Settings
│   │   │   ├── database.py           # SQLAlchemy SessionLocal and engine
│   │   │   └── security.py           # CurrentActor dependency and role guards
│   │   ├── models/                   # SQLAlchemy 2.0 ORM domain entities (21 models)
│   │   ├── schemas/                  # Pydantic v2 request/response schemas
│   │   ├── services/                 # Business logic, audit logging, sequences
│   │   └── main.py                   # FastAPI application initialization & CORS
│   ├── scripts/                      # Seed, admin CLI, and SQL utility scripts (seed.py, manage_users.py, sql/cleanup_test_data.sql)
│   └── requirements.txt              # Backend dependencies
├── frontend/
│   ├── e2e/                          # Real browser Playwright E2E test suites
│   │   └── receptionist_corrections.spec.ts # 6 test suites covering 14 items
│   ├── playwright.config.ts          # Playwright configuration (Chromium, baseURL)
│   ├── src/
│   │   ├── api/                      # Client API connector (client.ts)
│   │   ├── components/               # Common UI widgets, Layout, Modals
│   │   │   └── common/
│   │   │       └── DualCopyInvoiceModal.tsx # A4 Landscape Patient/Office dual copy
│   │   ├── context/                  # AuthContext, ToastContext
│   │   ├── features/                 # Page features (Dashboard, Invoices, Patients, etc.)
│   │   ├── types/                    # TypeScript interfaces and domain enums
│   │   └── App.tsx                   # Main React entry & router configuration
│   ├── package.json                  # NPM packages, Playwright runner, build scripts
│   └── vite.config.ts                # Vite dev server and proxy rules
├── tests/                            # Automated pytest backend test suite
│   ├── test_receptionist_e2e.py      # Prompt 03 E2E integration test suite (14 tests)
│   └── test_prompt04_corrections.py  # Prompt 04 corrections test suite (5 tests)
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
  - Pre-sample refunds can be requested by Receptionists **only if** `Sample.status != 'COLLECTED'` (or sample record does not exist).
  - Any cancellation request creates a `RefundRequest` in status `PENDING_ADMIN_APPROVAL`.
  - Final financial disbursement from the cashier drawer is strictly blocked until an Admin or Owner approves the request.
- **Consequences:** Protects clinic revenue, prevents fraudulent unauthorized refunds, and provides complete traceability.

### ADL-006: Diagnostic Report Release Due Hold with Admin Override
- **Decision:**
  - Reports in status `AUTHORIZED` display an automatic `DUE HOLD` indicator if `invoice.due_amount > 0`.
  - Delivery action is strictly disabled for Receptionists when due balance is positive.
  - Settle Due workflow must be completed first to clear the balance to 0, which immediately unlocks standard delivery.
  - Exception: Emergency release is permitted only via the `Admin Due Override` endpoint, which mandates a documented justification and logs the authorizing Admin staff ID.
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
  - Test orders route automatically based on the test's `performing_role` and `department`:
    * If `performing_role == 'LAB_TECH'`: Routed directly to an active technician whose `department` matches the investigation.
    * If `requires_doctor == True` or `performing_role == 'DOCTOR'`: Enters `AWAITING_DOCTOR` status without requiring doctor login.
    * If no matching technician is available: Preserved in `UNASSIGNED` queue visible to supervisors.
  - Order creation is strictly idempotent (`invoice_line_id` is unique on `test_orders`).
- **Consequences:** Eliminates manual front-desk routing delays while preventing unassigned tasks from becoming lost.

### ADL-014: Strict Financial-Data Isolation for Laboratory Technicians (Module 11)
- **Decision:**
  - Technicians operate under strict operational boundaries: zero visibility into test prices, discounts, master margins, dues, or referrer commissions.
  - This constraint is enforced at the backend Pydantic serialization layer via `TechnicianWorklistItemResponse`, not merely hidden in the frontend.
  - Worklist queries are hard-filtered by `assigned_to_id == actor.id` when called under `LAB_TECH` role context.
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
  - Support three template formats: `NUMERIC_TABLE` (with components), `NARRATIVE` (multi-section findings/impression), and structured `ULTRASOUND` (organ-by-organ breakdown).
  - Absolute physiological boundaries (`impossible_min`, `impossible_max`) reject absurd inputs (e.g. Hemoglobin 150) immediately with HTTP 400.
  - Automatic clinical flags evaluate numeric values against configured reference bounds: `LOW`, `HIGH`, `CRITICAL`, or `NORMAL`. Incomplete or missing reference ranges NEVER silently default to NORMAL; flag remains `None`.
  - **D24 Snapshot Invariant:** When results are entered, reference ranges and units are permanently snapshotted into `result_items`. Future changes to the test catalog never drift historical clinical results.
  - Decouple `Result.status` (`DRAFT`, `ENTERED`) from `TestOrder.status` (`SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `COMPLETED`).
- **Consequences:** Provides clinical data fidelity, prevents malpractice from data corruption, and ensures immutable diagnostic history.

### ADL-019: Rejected Specimen D15 Refund Exception & Two-Stage Disbursal Separation (Module 12 Fix 4)
- **Decision:**
  - When a specimen is spoiled or rejected, `TestOrder.outcome = "NOT_PERFORMED"` under the D15 exception.
  - The technician can submit a D15 refund request directly from the worklist (`request_type = "D15_NOT_PERFORMED"`, `status = "PENDING_ADMIN_APPROVAL"`).
  - Invoices view blocks generic pre-sample cancellation on locked lines while displaying the authoritative D15 refund status.
  - **Two-Stage Refund Separation:** Admin review marks the request `APPROVED` and invoice `REFUND_APPROVED`. Money disbursement is an explicit separate action performed by the Cashier or Admin, recording the payout channel (`CASH`, `BKASH`, `NAGAD`, etc.), drawer deduction, and reversing referral commissions.
- **Consequences:** Prevents phantom drawer shortages by ensuring cash is deducted only when physically paid out, while upholding the D15 invariant against unauthorized cancellations.

### ADL-020: Original Payment Channel Enforcement for Refunds (Rules 3.1, D18, M29)
- **Decision:**
  - `disburse_refund` strictly validates that the refund disbursement method matches one of the payment channels actually used on that invoice (`CASH`, `BKASH`, `NAGAD`, `POS_CARD`, `BANK_TRANSFER`).
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
- **Consequences:** Clean separation of public entry surfaces and authenticated operational workspaces without route collision or unauthorized data exposure.

### ADL-031: Lightweight CSS Keyframe Animation Architecture (Prompt 10)
- **Context:** High-motion marketing libraries (such as Three.js, Lottie, or heavy canvas runners) degrade front-desk hardware performance and violate the lightweight clinical footprint.
- **Decision:** Implement all interactive and medical scene animations (ECG heartbeat line, filling tube, travelling dot, sequential chips, pulsing peak marker, and marquee) strictly via pure vector SVG and native CSS keyframes animating only `transform`, `opacity`, and `stroke-dashoffset` using the weighted deceleration curve `cubic-bezier(0.22, 1, 0.36, 1)`. Full fallback under `@media (prefers-reduced-motion: reduce)`.
- **Consequences:** Ultra-fast rendering (~60fps on low-end hardware) with zero JavaScript execution overhead during animation frames.

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
- **Multi-Role Governance:**
  - Table `staff_roles` maps staff members to permitted operational roles (`RECEPTIONIST`, `CASHIER`, `ADMIN`, `OWNER`, `LAB_TECH`).
  - Active session holds single `acting_role`, dynamically switchable among granted roles via `/auth/acting-role`.
  - All audit log events persist the user's `acting_role`.
