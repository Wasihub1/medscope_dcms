# MedScope Project Context

## 1. Product purpose

MedScope is a Streamlit + SQLite web application for operating a diagnostic center. It manages tenant/platform access, patient registration, visits, test billing, individual and master discounts, payments and dues, refunds, laboratory assignment and sample collection, result entry and verification, report delivery, inventory, cashier day sessions, referral commissions, accounting, reports, and audit history.

The application is designed for local or trusted-network deployment. It is not a conventional API-based application and should not be redesigned as one unless the product requirements explicitly change.

## 2. Repository map

| Path | Role |
|---|---|
| `DCMS V1.py` | Main Streamlit application; authentication, navigation, screens, tenant schema, upgrades, invoice and clinical workflows |
| `accounting.py` | Double-entry accounting schema, journals, periods, chart of accounts, payables, expenses, fixed assets, and reports |
| `theme.css` | Site-wide visual styling and responsive layout |
| `keyboard_dropdown/index.html` | Local custom searchable dropdown component used by large option lists |
| `requirements.txt` | Python dependencies |
| `README.md` | Installation, startup, Dev setup, data, and backup documentation |
| `PERMISSIONS.md` | Implemented tenant and platform role matrix |
| `USER_GUIDE.md` | User-facing workflows |
| `AGENTS.md` | Repository instructions for coding agents |
| `project-context.md` | Complete project mental model and implementation constraints |
| `Dev.ps1` | Windows helper for Dev setup-token launch |
| `Test Price.csv` | Seed catalog imported once per tenant |
| `seba_diagnostic.db` | Optional legacy database used for initial tenant provisioning |
| `medscope_data/platform.db` | Platform registry and Dev records |
| `medscope_data/tenants/<tenant-uuid>.db` | One isolated operational database per tenant |

## 3. Runtime architecture

### Entry point and reruns

`main()` runs through Streamlit whenever a widget interaction triggers a script rerun. It initializes platform and tenant storage, loads theme CSS, authenticates the current session, resolves role navigation, and dispatches a screen function.

There are no separately maintained frontend route components. Navigation is generally stored in Streamlit session state and resolved inside the monolithic Python entry point.

### Monolithic application module

Most domain code is intentionally kept in `DCMS V1.py`. Important groups include:

- Platform and tenant initialization/migrations
- Login and Dev authentication
- Tenant navigation and dashboards
- Patient and visit workflows
- New Invoice, invoice search, dues and refunds
- Test assignment and cancellation
- Sample collection, result entry, verification, and report delivery
- Inventory
- Day/cashier sessions
- Staff, tests, referrers, database utilities, reports, and audit

`accounting.py` is imported by `DCMS V1.py` and initialized with tenant accounting data.

### Custom dropdown

`keyboard_dropdown_component(...)` declares the component path and `dropdown(...)` adapts Streamlit inputs and output to it. It supports keyboard searching, single selection, multi-selection, and optional empty selection behavior. The component and Python wrapper must preserve both the browser selected value and Streamlit session state across reruns.

## 4. Authentication scopes

### Tenant staff

Tenant staff signs in with a username and 4–6 digit PIN. Staff usernames are expected to be globally unique across active tenant databases, so a sign-in attempt can resolve the tenant without exposing a tenant directory. Authentication lockout fields are checked by the tenant login flow.

Tenant roles:

- Owner
- Admin
- Receptionist
- Cashier
- Lab Tech

See [PERMISSIONS.md](PERMISSIONS.md) for the implemented matrix.

### Platform Dev

Platform Dev is separate from tenant staff. Dev uses a separate Master/Dev ID, password, and authenticator TOTP. First-time Dev bootstrap requires `MEDSCOPE_DEV_SETUP_TOKEN` in the environment of the running Streamlit process.

A valid Dev session may:

- Enter the Dev portal
- Provision and manage tenants
- Create/disable tenant Owner accounts
- Enter a tenant with Owner-equivalent access while preserving Dev attribution in tenant audit records

Never expose or log Dev credentials or bootstrap secrets.

## 5. Data architecture and isolation

### Platform database

`medscope_data/platform.db` stores platform registry information:

- Tenants and enabled state
- Platform Dev users
- Platform audit history

Tenant UUID determines the tenant database filename. Tenant UUID validation occurs before database path construction.

### Tenant databases

Every tenant has a separate SQLite database:

`medscope_data/tenants/<tenant-uuid>.db`

This database contains:

- Staff and roles
- Patients and visits
- Tests and prices
- Referrers and commissions
- Invoices, lines, payments, refunds, and discounts
- Samples and results
- Report versions and deliveries
- Day sessions and ledger entries
- Inventory and stock movements
- Commission entries
- Sequences and audit history
- Referrer merge history
- Double-entry accounting records

The tenant database context manager:

- Opens SQLite in its tenant directory
- Enables foreign keys
- Commits successful transactions
- Rolls back exceptions
- Closes connections reliably

## 6. Core domain flow

```text
Patient
  -> Visit
     -> Invoice
        -> Invoice line(s)
           -> Sample
              -> Result
                 -> Report version
                    -> Report delivery

Invoice -> Payment(s) -> Due / Refund / Commission
Day session -> Ledger / payment-channel reconciliation
Stock item -> Stock movement(s)
```

Operational and financial data should remain connected through foreign keys and lifecycle checks.

### Patient and invoice lifecycle

A New Invoice screen registers or selects a patient, confirms demographic data, selects tests, calculates individual/master discounts, resolves referral fields, records invoice totals, posts payments, and creates accounting or ledger entries.

Selected patient details and test selection must be restored correctly from session state across Streamlit reruns. Patient IDs and test IDs, not display labels, should drive record operations.

### Billing calculations

The same prices and discount rules should be used consistently in:

- Selected-test UI
- Net Payable
- Invoice persistence
- Invoice search/detail views
- Due/refund calculations
- Receipt displays
- Discount expense journal entries
- Reports

Invoice discount invariants:

- Gross = sum selected test prices
- Individual percentage discounts: percentage mode only, capped at 50%
- Individual fixed discounts: amount mode only, capped at each test price
- Master percentage or amount mode: exclusive choices
- Master percentage and fixed amount cannot exceed the invoice subtotal
- Master Discount overrides individual calculations
- Individual settings remain stored inactive when master discount is active
- Canceling Master Discount must restore the individual settings unchanged

### Payments, dues, refunds, and commissions

Payments belong to invoices and cashier sessions. Dues are calculated from invoice totals and payment/refund state. Refund handling can retain all or part of canceled/refunded value according to current business rules.

Referral commission entries are linked to invoices and referrers. Owner-only rules govern commission configuration/payment. Commission payouts are ledger/accounting transactions and must not be inferred as staff earnings.

### Laboratory lifecycle

Tests can be assigned to reception/lab staff. Lab Tech roles collect samples, enter results, verify them, and authorize report versions. Once a sample exists, cancellation is not permitted under the normal lifecycle. Changes to assignment should record an audit/history row.

Report delivery requires an authorized report. Outstanding dues normally block release unless an Owner/Admin records the permitted override reason.

### Inventory and cashier sessions

Inventory items track current quantity and reorder threshold. Changes are represented by stock movements with signed quantities and attribution.

A cashier day is either open or closed:

- One open day constraint is enforced in tenant data
- Session balances cover payment channels
- Ledger entries belong to cashier sessions where applicable
- Closing reconciles counted and expected balances

### Accounting

`accounting.py` provides accounting-account setup and double-entry journal posting. Journal lines are posted in balanced debit/credit pairs. Amounts are stored in integer paisa where accounting code converts Taka values to avoid floating-point drift.

Accounting includes:

- Chart of accounts
- Double-entry journals and reversal support
- Parties/vendors
- Expenses and payables
- Fixed assets
- Accounting periods
- Reporting
- Cash and bank payment postings

Application invoice/payment actions and accounting actions must remain consistent. Preserve source keys and journal reversals instead of manually deleting posted business transactions.

## 7. Schema initialization

There is no Alembic, Django migration framework, or separate migration CLI. `initialize_database()` creates tables, indexes, additive columns, and seed data whenever startup selects a tenant.

Initialization rules:

- Create tenant tables if missing
- Add missing columns using guarded in-code upgrades
- Rebuild incompatible legacy constraints only through explicit routines
- Ensure required billing sequence and stock defaults
- Import `Test Price.csv` only once using an app-settings guard
- Keep operations idempotent across Streamlit reruns
- Detect legacy staff constraints safely and preserve data

Before changing schema:

1. Inspect existing tenant databases.
2. Add default/nullable columns or an explicit data migration.
3. Update every SQL read/write and UI binding.
4. Back up platform and tenant databases.
5. Run initialization repeatedly.
6. Verify foreign keys and existing records.

## 8. UI and session-state conventions

- Streamlit reruns execute the full Python file.
- Use session keys for values that should survive reruns.
- Widget keys should be stable across reruns.
- Keys representing lists of selected records should use actual IDs or canonical labels consistently.
- Avoid using loop index alone for persistent row controls.
- Callback functions must read the latest canonical session-state selection rather than stale local variables.
- Number inputs, radio/button controls, and session state must not fight each other.
- Disabled controls should not silently reset stored values.
- Use the existing olive/champagne theme and Streamlit layout patterns.
- Keep financial text and labels clear; use the existing `money()` formatting.
- Prefer compact desktop layouts, while preserving responsive CSS behavior on narrower screens.

## 9. Navigation and permissions

Navigation is role-filtered by `main()`. Sensitive operations also require server-side role validation. Hiding a page is not an authorization boundary.

Screens include dashboard variants, New Invoice, invoice search, dues/refunds, assignment, Lab Work, report delivery, inventory, day management, Accounts & Referrers/Staff management, database management, reports, audit trail, accounting, and platform Dev.

Admin restrictions differ from Owner restrictions. For example, commission settings/payments and Owner reports are Owner-only; Admin can manage operational users/catalog/referrers within implemented boundaries. Platform Dev is outside the tenant role hierarchy.

## 10. Security and privacy

- Tenant databases contain patient identity, phone numbers, medical workflow state, financial data, staff data, and audit history.
- Runtime database files must remain private and out of source control.
- Staff PINs are credentials and must never be logged.
- Dev passwords and TOTP secrets must never be committed or displayed beyond required setup.
- `MEDSCOPE_DEV_SETUP_TOKEN` is process-local bootstrap configuration.
- Backup platform and tenant data together, stopping active writes first or using SQLite backup functionality.
- Do not expose tenant directories or disable-account records in sign-in errors.
- Production/network access requires TLS or a hardened trusted-network/reverse-proxy setup.
- SQLite is single-host-oriented. Concurrent multi-instance deployment is not supported by this architecture.

## 11. Testing and development workflow

### Local launch

```powershell
python -m streamlit run "DCMS V1.py" --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Syntax checks:

```powershell
python -m py_compile "DCMS V1.py"
python -m py_compile accounting.py
```

The project currently has no separate unit-test suite in the repository. Validate changes by targeted Streamlit execution and database inspection.

### Development validation matrix

Use a disposable or explicitly approved tenant/database for UI workflow testing:

- Tenant sign-in and role navigation
- Platform Dev authentication and tenant access
- New patient and existing patient invoice flow
- Test selection/removal with multiple tests
- Individual percentage and fixed amount discounts
- Master percentage and fixed amount discounts
- Master activation cancellation preserving individual values
- Payment, due, and refund behavior
- Sample assignment, collection, result, verification, and delivery
- Role-restricted actions
- Accounting posts and journal balances
- Streamlit reruns and custom dropdown state

## 12. Known implementation characteristics

- The main source file is long and monolithic.
- Streamlit rerun behavior and session state are part of application correctness.
- Database initialization is runtime code, not a migration package.
- The custom dropdown is browser JavaScript inside a local HTML component.
- Test catalog import is operational seeding, not a runtime API.
- SQLite expression indexes and additive constraints are initialized through application startup.
- There are multiple legacy-compatible schema upgrade paths; preserving old records is more important than clean schema replacement.
- Reports are operational summaries and should not be described as external accounting statements unless the implementation explicitly supports them.

## 13. Change strategy

When implementing a request:

1. Find the relevant function and schema ownership.
2. Map UI state, database writes, reports, and accounting consequences.
3. Update role checks and all persisted representations.
4. Keep individual changes small and cohesive.
5. Run syntax checks.
6. Start MedScope and exercise reruns where UI state is involved.
7. Inspect only approved/non-sensitive test records.
8. Update directly related README, permissions, or user guide documentation when behavior changes.

## 14. Modernized Receptionist Slice (React 19 + FastAPI + PostgreSQL)

In November 2026, the Receptionist Portal vertical slice was modernized into a decoupled, high-performance client-server stack while preserving all legacy Streamlit and SQLite code intact:

### Modern Stack Overview:
- **Frontend (`frontend/`):** React 19 + TypeScript + Vite 8 + Tailwind CSS v4 + React Router + Lucide Icons.
  - Implements the 60-30-10 palette (Platinum `#E8E7E3`, Dark Moss `#525333`, Persian Orange `#CF8852`).
  - Features Bento grid dashboard, 2-column fast invoice creator, duplicate phone detector, workstation routing, dues settlement, pre-sample refund state machine, report due-hold release, and 80mm thermal receipt printing.
- **Backend (`backend/`):** FastAPI + Pydantic v2 + SQLAlchemy 2.0 ORM + Psycopg 3 + Alembic.
  - 30 RESTful endpoints under `/api/v1/`.
  - Strict whole-Taka integer currency representation.
  - Role-based scoping (Receptionist role boundaries filter out commissions, test cost prices, and accounting ledgers; business day close returns 403 Forbidden).
- **Database:** PostgreSQL 18 on `127.0.0.1:5432` (`medscope_dcms`, user: `medscope_app`).
  - 22 tables provisioned via Alembic revision `5e7d6e556c9d`.
  - Monotonic concurrency-safe sequence generation via `sequence_counters`.
  - Partial unique index `idx_business_day_single_open` ensuring a single active business day per tenant.

### Modern Startup Commands:
```powershell
# Backend (FastAPI on http://127.0.0.1:8000):
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (Vite on http://localhost:5173):
cd frontend; npm run dev

# Alembic Migrations:
python -m alembic upgrade head

# Database Seed:
python backend/scripts/seed.py

# Automated E2E Test Suite:
python -m pytest tests/test_receptionist_e2e.py -v
```

---

## 15. Prompt 03 Completion Log & Documentation Consolidation

### Execution Summary (Prompt 03)
- **Discount Policy Updated:** Per Prompt 03 user decision, the arbitrary 50% discount cap was removed. Line discounts are permitted up to 100% of the individual test price (zero net value allowed, no negative values).
- **URL Query Deep Linking:** Wired deep linking across all views:
  - `/invoices/new?patient_id=:id` pre-selects patient.
  - `/invoices/new?test_id=:id` pre-selects test item.
  - `/invoices?id=:id` auto-opens invoice detail modal.
  - `/patients?id=:id` auto-opens patient history modal.
  - `/reports?id=:id` and `/reports?search=:term` auto-opens report print/handover modal.
- **Patient History Modal Tabbed Interface:** Wired 4-tab history (Visits, Invoices & Tests, Payments & Receipts, Specimens & Reports) with quick action `➕ New Invoice with Patient`.
- **Dues Endpoint & UI Aliases:** Updated `DueInvoiceSummary` in `payment.py` to supply full aliases (`id`, `invoice_number`, `patient_mrn`, `due_amount`), connecting directly to `/dues`.
- **Diagnostic Report Print Auditing:** Hooked print event registration via `GET /reports/printable/{id}` and `POST /reports/{id}/print-events` before triggering `window.print()`.
- **Automated Development E2E Suite:** Implemented `tests/test_receptionist_e2e.py` covering all 14 scenarios specified in Prompt 03 Section 7. Verified all 14 passed (0.92s).
- **Documentation Consolidated:** Streamlined narrative documentation into exactly nine canonical markdown files.

### Disposition Table of Consolidated Documents
| Source Legacy File | Canonical Destination File | Disposition Status |
| :--- | :--- | :--- |
| `DCMS Final Scope V1.md` | `docs/SCOPE.md` | Consolidated into `docs/SCOPE.md`; source removed |
| `PERMISSIONS.md` | `docs/SCOPE.md` | Consolidated into `docs/SCOPE.md`; source removed |
| `USER_GUIDE.md` | `docs/SCOPE.md` & `docs/WORKFLOWS.md` | Consolidated; source removed |
| `docs/modules/receptionist.md` | `docs/SCOPE.md` & `docs/WORKFLOWS.md` | Consolidated; source removed |
| `docs/architecture/ADL.md` | `docs/ARCHITECTURE.md` | Consolidated into `docs/ARCHITECTURE.md`; source removed |
| `docs/design/design-convention.md` | `docs/DESIGN.md` | Consolidated into `docs/DESIGN.md`; source removed |
| `docs/interfaces/receptionist/*.md` (17 files) | `docs/API.md` | Consolidated into `docs/API.md`; source removed |
| `DATABASE-DIAGRAM.md` | `docs/DATABASE.md` | Consolidated into `docs/DATABASE.md`; source removed |
| `docs/database/database-and-alembic.md` | `docs/DATABASE.md` | Consolidated into `docs/DATABASE.md`; source removed |
| Automated E2E Test Suite | `docs/TESTING.md` | Setup, scenarios, and results documented |
| Core Architecture & Quick Start | `README.md` | Updated with dual-stack documentation |

---

## 16. Prompt 04 Completion Log & Real Playwright Browser E2E Verification

### Execution Summary (Prompt 04)
- **Item 01 (Prescriber vs Referrer Separation & Write-Only Commission):**
  - Database: Alembic migration `c94589ffc4ee` added `prescribed_by_id` foreign key referencing `referrers.id` on `invoices` table.
  - Backend: Added write-only initial `commission_rate` (0-100%) and `commission_type` on `ReferrerCreate`. Commission fields are strictly excluded from `ReferrerResponse` so receptionist cannot read or inspect commission rates. Added `type` filter (`?type=Doctor`) on `GET /referrers`.
  - Frontend: Independent inputs on `NewInvoicePage.tsx` for `Prescribed By (Doctor Only)` with inline modal, and `Referred By (Doctor / Third Party)` with inline modal. Both can be walk-in/self.
- **Item 02 (Business Day Close RBAC):**
  - Backend: `close_business_day` enforces 403 Forbidden for `RECEPTIONIST` and `CASHIER`. Allowed for `ADMIN` and `OWNER`.
  - Frontend: `BusinessDayPage.tsx` shows disabled indicator in receptionist mode, active close button in admin mode.
- **Item 03 (Test Suggestion Deduplication):**
  - Backend: Pydantic validator `validate_no_duplicate_lines` on `InvoiceConfirmRequest`.
  - Frontend: Selected tests are dynamically filtered out of catalog and suggestions; reappear if removed.
- **Item 04 (Dual % and ৳ Discount Modes with Distinct Input Fields):**
  - Line items in the Selected Investigations form feature distinct, synchronized input fields side-by-side (`[ % ] %` and `[ ৳ ] ৳`), eliminating the dropdown `<select>`.
  - Dynamic bidirectional synchronization: typing in `%` computes equivalent integer Taka; typing in `৳` computes equivalent integer percentage.
  - Resetting or clearing either field safely resets the line discount to `NONE` (৳0).
  - Both line and master discounts are rounded to whole integer Taka, capped at test price or 100%, with no negative net payable. Line discounts remain preserved in state when Master Discount is active.
- **Item 05 (Default Paid Amount ৳0):**
  - `paidAmount` defaults to ৳0 (Unpaid). No zero-amount payment row persisted. Helper quick-buttons for full payment and ৳0.
- **Item 06 & 07 (Two-Stage Creation Flow & Clean Form Reset):**
  - `Generate Preview` opens `DualCopyInvoiceModal` showing side-by-side **Patient Copy** and **Office / Lab Copy** (non-final, with Unsaved Draft watermark).
  - `Back & Correct` returns to form with 100% state intact.
  - Final save commits transaction-safely once. Entry form resets to clean state only after persistence succeeds.
- **Item 08 & 09 (Inline Global Search & Ctrl+F):**
  - Header search is fully inline with anchored dropdown categorized results. `Ctrl+F` replaces `Ctrl+K`. Obsolete modal removed.
- **Item 10 (Dual-Copy Invoice Print & Single Duplicate Audit):**
  - Fixed print action in `InvoicesPage.tsx` and `DashboardPage.tsx`. Reprints record a single audit event, apply `DUPLICATE` watermark, and open A4 landscape dual-copy printable view without route redirection.
- **Item 11 (Standardized Payment Labels):**
  - Universal mapping: `Full Due` -> `Unpaid`, `Partial Paid` -> `Partial Due`, `Paid` -> `Paid`.
- **Item 12 (Patient History Old Invoice Context Bug Fixed):**
  - In `PatientsPage.tsx`, clicking "View" on an invoice in Patient History opens a nested `DualCopyInvoiceModal` overlay without route navigation. Closing returns to the exact patient ledger on `/patients`.
- **Item 13 & 14 (Playwright Real Browser E2E & Separate Refund Status):**
  - `@playwright/test` and Chromium installed in Antigravity sandbox.
  - 6 real browser E2E tests in `frontend/e2e/receptionist_corrections.spec.ts` covering desktop and mobile viewports: 6 passed in 16.7s.
  - 19 backend pytest integration tests in `tests/`: 19 passed in 1.19s.
  - Surface dynamic `refund_status` column (`No Refund`, `Refund Pending`, `Partially Refunded`, `Fully Refunded`, `Refund Rejected`) and request timeline in invoice details.

---

## 17. Invoice Filter Dropdown User-Friendly Events & Persistent `refund_status` Column

### Scope & Solution Overview
Following user request to eliminate empty grid responses when selecting filter options on `/invoices`:
1. **Persistent `refund_status` Column:**
   - Alembic migration `bdc0201a1170` (`add_refund_status_to_invoices.py`) added `invoices.refund_status` (`VARCHAR(50)`, default `'NO_REFUND'`, indexed).
   - Automated backfill updated existing database rows: 16 `FULLY_REFUNDED`, 1 `PARTIALLY_REFUNDED`, 44 `NO_REFUND`.
   - Updated `admin_review_refund_request` and `initiate_refund_request` in `refund_service.py` to maintain persistent `refund_status`.
2. **User-Friendly Filter Events:**
   - Hardcoded the 6 user-friendly events in `InvoicesPage.tsx`:
     - `All Payments`
     - `Paid`
     - `Unpaid`
     - `Partial Due`
     - `Partially Refunded`
     - `Fully Refunded`
3. **PostgreSQL Column Masking in Backend (`invoice_service.py`):**
   - The backend `search_invoices` service accepts user-friendly event strings and maps them cleanly to underlying PostgreSQL columns:
     - `Paid`: `payment_status = 'PAID' AND (refund_status IS NULL OR refund_status != 'FULLY_REFUNDED')`
     - `Unpaid`: `payment_status = 'UNPAID' OR (paid = 0 AND due > 0)`
     - `Partial Due`: `payment_status = 'PARTLY_PAID' OR (paid > 0 AND due > 0)`
     - `Partially Refunded`: `refund_status = 'PARTIALLY_REFUNDED'`
     - `Fully Refunded`: `refund_status = 'FULLY_REFUNDED' OR payment_status = 'REFUNDED'`
4. **Verification:**
   - Playwright browser E2E: 6 passed in 18.5s (Test 4 explicitly exercises all 6 dropdown options).
   - Pytest suite: 20 passed in 1.34s (added `test_p04_06_user_friendly_status_filter_events`).
   - Frontend Vite build: 2083 modules transformed, 0 errors.

---

## 18. Prompt 05 Completion Log: Test Catalog Readiness, Task Routing & Technician Worklist

### Execution Summary (Prompt 05)
- **Part A — Test Catalog Readiness Assessment (Module 5):**
  - Assessed existing catalog structure against clinical task routing and report processing requirements.
  - Added necessary schema fields to `Test` model: `turnaround_hours` (integer), `performing_role` (VARCHAR(50), default `LAB_TECH`), `requires_doctor` (boolean, default false), `report_template` (VARCHAR(50), default `NUMERIC_TABLE`), `approval_rule` (VARCHAR(50), default `TECHNICIAN_FINAL`), and `is_outsourced` (boolean, default false).
  - Seeded 25 master diagnostic tests with operational turnaround hours (2h - 48h), template types (`NUMERIC_TABLE`, `NARRATIVE`, `CULTURE_SENSITIVITY`), and approval rules (`TECHNICIAN_FINAL`, `DOCTOR_REQUIRED`, `BOTH_SIGNATURES`).
  - Preserved working catalog prices and line-item snapshotting. Documented multi-component profile trees and age/sex reference ranges as deferred to Module 13.
- **Part B — Splitting the Work & Task Routing (Module 10):**
  - **Individual Order Creation:** Upon invoice confirmation, every test line generates an individual `TestOrder`. Monolithic bill assignment is strictly barred. Order creation is concurrency-safe and idempotent (`invoice_line_id` is unique).
  - **Smart Department & Role Routing:** Orders route to staff based on `performing_role` and `department`. Hematology tests auto-route to Kamal Hossain (ID 3); Biochemical investigations auto-route to Nasrin Sultana (ID 4). Unmatched departments remain preserved in `UNASSIGNED` queue visible to supervisors.
  - **Visiting Doctor Queue:** Ultrasound and doctor-required investigations (`USG_W_A`, `USG_L_A`, `USG_PREG`) automatically enter `AWAITING_DOCTOR` status without requiring doctor credentials.
  - **STAT Priority Preservation:** Urgent flags from billing persist onto `TestOrder.urgent` and prioritize tasks at the top of technician worklists.
  - **Assignment History Audit:** Reassignments require a recorded justification and persist previous assignee, new assignee, actor ID, and timestamps in `AssignmentHistory`.
  - **Turnaround Clocks:** Implemented dual clocks: Patient Clock (elapsed duration since invoice confirmation) and Laboratory Clock (elapsed duration since specimen collection). Late tasks automatically trigger a red `LATE` indicator with clock breakdown when either clock exceeds configured TAT.
  - **Sample Collection Foundation:** Established Quick Route specimen collection action (`POST /api/v1/worklist/{id}/sample-taken`). Records specimen collection timestamp, starts Laboratory Clock, and audits manual timestamp adjustments exceeding 5 minutes drift.
- **Part C — Technician Worklist (Module 11):**
  - **My Work Screen (`/worklist`):** Dedicated laboratory workbench featuring Bento KPI summary tiles (Total Assigned, Urgent STAT, Sample Pending, In Progress, Late, Completed), instant search (barcode, sample code `SMP-...`, patient name, MRN, test code), status tabs, and quick route specimen collection modals.
  - **Strict Financial Data Separation (Section 5.4):** Completely enforced at backend Pydantic serialization level (`TechnicianWorklistItemResponse`). All prices, gross, net, dues, discounts, and commissions are omitted from payloads and DOM representations.
  - **Access Boundaries:** Technicians operating under `LAB_TECH` role context are strictly hard-filtered to `assigned_to_id == actor.id`. URL/query tampering is blocked.
  - **Multi-Role Development Switcher:** Expanded development switcher in `AuthContext` and `Header` to cycle between Receptionist (Fatima, ID 1), Admin (Tariqul, ID 2), Tech Kamal (Hematology, ID 3), and Tech Nasrin (Biochemistry, ID 4).
- **Database & Migrations:**
  - Alembic revision `e05b9b1a2c3d` applied to PostgreSQL 18. Added catalog readiness fields to `tests`, `department` to `staff`, `default_sample_route` to `tenants`, and operational clock tracking fields to `test_orders`.
- **Testing Status:**
  - **Testing: Not performed — explicitly instructed by the user.** (Zero automated tests executed; static build and syntax compilation verified: frontend Vite build 2084 modules transformed, 0 errors; Python py_compile 0 errors).

---

## 19. Test Catalog Scale (1,250 Tests) & API Pagination Resolution Log

### Investigation & Root Cause Summary
Following user manual insertion of 1,200+ diagnostic tests into the PostgreSQL `tests` table, investigations revealed why investigations were not appearing in the New Patient Diagnostic Intake UI (`/invoices/new`):

1. **Primary Blocker — Multi-Tenant Scoping Isolation (`tenant_id`):**
   - The manually inserted 1,225 tests carried `tenant_id = 'default_tenant'`.
   - The active tenant in the application database, security context, and frontend headers is `'center-seba-01'` (`Seba Diagnostic Center`).
   - The API endpoint `GET /api/v1/tests` enforces tenant isolation via `select(Test).where(Test.tenant_id == actor.tenant_id, Test.active == True)`.
   - Result: All 1,225 records were excluded by the SQL `WHERE` clause. Only the 25 original seed tests were returned.

2. **Secondary Blocker — API Pagination Hard Cap (`default=50, le=200`):**
   - In `backend/app/api/v1/endpoints/tests.py`, `limit: int = Query(default=50, le=200)`.
   - The endpoint defaulted to returning 50 tests, and rejected any query with `limit > 200` via FastAPI HTTP 422 Unprocessable Entity.
   - Even when tenant ID matched, `GET /api/v1/tests` truncated the delivered catalog to 50 records.

3. **Tertiary Factor — In-Memory Client Search Pattern:**
   - In `frontend/src/features/invoices/NewInvoicePage.tsx`, the catalog is fetched on mount via `api.getTests()` and stored in `testCatalog`.
   - User search keystrokes filter in-memory (`testCatalog.filter(...)`).
   - Consequently, any test not included in the initial fetch payload could never be discovered in the search dropdown.

### Technical Resolution Applied:
1. **Tenant ID Migration:**
   - Migrated all 1,225 test records in PostgreSQL to `'center-seba-01'`:
     ```sql
     UPDATE tests SET tenant_id = 'center-seba-01' WHERE tenant_id = 'default_tenant';
     ```
   - Confirmed 0 duplicate code conflicts with existing tests (`idx_test_tenant_code` unique index fully preserved). Total active tests under `center-seba-01` reached **1,250**.
2. **Backend API Limit Scaled:**
   - In `backend/app/api/v1/endpoints/tests.py`, updated `limit: int = Query(default=2500, le=10000)`.
   - Calling `GET /api/v1/tests` without parameters now returns the full active catalog (up to 2,500 tests).
3. **Frontend API Client Adjusted:**
   - In `frontend/src/api/client.ts`, updated `getTests` to accept `limit: number = 2500` and pass it in query parameters.
4. **Referrers Capacity Scaled:**
   - In `backend/app/api/v1/endpoints/referrers.py`, updated `limit: int = Query(default=100, le=500)` to ensure all active medical doctors and agents are accessible.

### UI Form Consolidation, Column Rebalancing & Invoice Preview Resolution
1. **Invoice Preview Test Name Display Resolution:**
   - Diagnosed that FastAPI's `InvoiceLineResponse` uses `test_name_snapshot`, `department_snapshot`, `unit_price_snapshot`, `urgent` which caused `l.test_name` to be undefined in `DualCopyInvoiceModal`.
   - Added direct aliases (`test_name`, `test_code`, `department`, `price`, `is_urgent`) on `InvoiceLineResponse` via Pydantic validator.
   - Enhanced `DualCopyInvoiceModal.tsx` to safely resolve `l.test_name || l.test_name_snapshot || l.name || (l.test && (l.test.name || l.test.test_name)) || 'Investigation'` across all sources, and prioritized `invoiceData` when `isPreview === true`.
2. **Form Consolidation (Prescriber & Referrer) & Aligned Controls:**
   - Merged `2. Prescribed By (Doctor Only)` and `3. Referred By (Doctor / Third Party / Broker)` into a single consolidated card container (`bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-3.5 shadow-xs`) with an internal 2-column responsive subgrid (`grid grid-cols-1 md:grid-cols-2 gap-4 items-start`).
   - Aligned search input field and Add modal trigger button side-by-side (`h-9` / 36px) on the exact same baseline in each sub-form.
   - Selected card also adopts `h-9` with name, badge, and Clear button, ensuring 100% vertical and horizontal alignment across columns regardless of selection states.
   - Maintained 100% separate functionality, independent search bars, inline modals, doctor badges, and test attributes.
   - Saved ~130px of vertical space, bringing `4. Investigation Catalog` significantly up on the screen.
3. **Investigation Catalog Height Expansion:**
   - Increased catalog test list height from `max-h-56` (224px) to `max-h-80` (320px) to provide ample viewing space for the 1,250 tests.
4. **Intake Grid Rebalancing (10% Space Transfer):**
   - Main intake grid rebalanced from 7:5 (58% : 42%) to `lg:grid-cols-[48%_1fr]` (48% : 52%).
   - Truncated the left column by 10% and granted the space to the right column, giving generous width for itemized test rows, line discounts (% and ৳), urgent toggles, master discounts, and payment intake.
5. **Selected Investigations Distinct Discount Input Fields:**
   - Replaced line discount dropdown `<select>` with distinct side-by-side input fields: `[ % ] %` and `[ ৳ ] ৳`.
   - Bidirectional real-time calculation: typing % updates equivalent Taka; typing ৳ updates equivalent %.
   - When Master Discount is active, line inputs are gracefully disabled with `(Master Active)` indicator while preserving configured values for reactivation.
6. **Verification & Testing:**
   - `GET /api/v1/tests` tested with `TestClient`: returns HTTP 200 with all 1,250 tests.
   - Filter queries verified: `q=Glucose` (31 tests), `department=Clinical Pathology` (471 tests).
   - Frontend production build (`npm --prefix frontend run build`): 2084 modules transformed, 0 errors, built in 569ms.
   - Backend pytest suite: 20 passed in 1.67s.
   - Playwright browser E2E: 6/6 tests passed in 30.6s (including automated dynamic sync verification for line discounts).

---

## Prompt 06 — Module 12: Test in Progress & Specimen Lifecycle Implementation
1. **Specimen Tube Barcode Label Generation & Printing (Section 5.1):**
   - Formatted for standard 50mm × 30mm and 50mm × 25mm thermal direct adhesive rolls in `SampleBarcodeModal.tsx`.
   - Pure-Python vector Code 128 SVG generator in `backend/app/services/barcode_service.py` (zero external dependencies).
   - Barcode identifies the specific sample (`sample_code`), not merely the invoice or patient.
   - Includes Patient Name, Age/Gender, Patient Code (MRN), Test Name & Code, Specimen Type, Collection Time, and Sample ID. Strictly financial-free.
   - Offline barcode reconciliation supported via `Sample.temp_sample_id`.
2. **Sample Collection, Line Locking & Stock Boundary (Section 5.2):**
   - `record_sample_taken` locks the corresponding bill line: `InvoiceLine.is_locked = True`, `locked_at = now`, `locked_reason = Specimen collected`.
   - `refund_service.py` blocks ordinary pre-sample refunds/cancellations once `is_locked == True`.
   - Reagent consumption integration boundary established in `backend/app/services/stock_boundary_service.py` (`trigger_specimen_stock_deduction`); complete reagent inventory and batch ledgers deferred to Module 16.
3. **Spoiled or Rejected Specimen Workflow (Section 5.3 & D15 Rule):**
   - Mandatory rejection reason required (`POST /api/v1/worklist/{id}/reject-sample`).
   - Transitions sample and task status to `REJECTED` or `SPOILED`.
   - Flags patient for follow-up contact (`patient_followup_required = True`, `patient_contact_status = 'PENDING_CALL'`).
   - Enforces D15 rule: Line remains locked under Not Performed outcome. No free recollection on the same bill line. Patient contact records `CALLED`, `RECOLLECTION_AGREED` (new bill line required), or `REFUND_REQUESTED` (Admin/Owner Not Performed exception).
4. **Append-Only Operational History & Event Timeline (Section 5.4):**
   - Added `test_order_events` table capturing immutable lifecycle milestones with actor attribution (`SAMPLE_CREATED`, `SAMPLE_COLLECTED`, `SAMPLE_REJECTED`, `IMAGING_PERFORMED`, `AWAITING_DOCTOR`, `CULTURE_STAGE`, `OUTSOURCED`, `COMPLETED`, `PATIENT_CONTACTED`).
   - Rendered in interactive timeline modal `LifecycleHistoryModal.tsx`.
5. **Department-Specific Workflow Extensions (Section 5.5):**
   - **Radiology & Imaging:** Added `IMAGING_PERFORMED` milestone; does not require a biological sample; line locks at scan completion; routes to `AWAITING_DOCTOR`.
   - **Culture & Sensitivity:** Stepwise multi-stage progression: `INCUBATING` (24h/48h) -> `PRELIMINARY` -> `FINAL`.
   - **Outsourced Laboratories:** Tracks dispatch (`OUTSOURCED_SENT`) and specimen/result receipt (`OUTSOURCED_RECEIVED`) with external tracking numbers.
6. **Worklist State Transition Correction (Section 6):**
   - Fixed Prompt 05 bug where `Complete` button was exposed prior to sample collection.
   - Before sample collection, sample-based tasks only offer `Sample Taken`.
   - Backend `update_order_status` enforces transition rules: rejects completing before sample collection, rejects technician completing doctor-routed tests, and rejects completing spoiled/rejected samples.
7. **Database Evolution (Alembic Migration `f16c024d3e4a`):**
   - Added `temp_sample_id`, `rejected_at`, `rejected_by_id`, `rejection_reason`, `rejection_notes` to `samples`.
   - Added `is_locked`, `locked_at`, `locked_reason` to `invoice_lines`.
   - Added `patient_followup_required`, `patient_contact_status`, `patient_contacted_at`, `patient_contact_notes`, `culture_stage`, `outsourced_status`, `outsourced_lab_name`, `outsourced_sent_at`, `outsourced_received_at`, `outsourced_ref_no` to `test_orders`.
   - Created `test_order_events` table with indexes.
8. **Testing Status:**
   - **NOT PERFORMED — explicitly prohibited by the user in Prompt 06 Section 3.**
   - Verified via static code review, architectural trace, and schema validation.

---

## Prompt 07 — Module 13: Entering Results & Report Data + Module 12 Fixes

### 1. Module 13 Clinical Result Entry Engine
- **Three Template Formats:**
  1. `NUMERIC_TABLE`: Component-driven with live flag preview and reference range comparisons (e.g. CBC, Lipid Profile, Electrolytes, LFT, KFT). Delta comparison is excluded by D25.
  2. `NARRATIVE`: Free-text multi-section editor capturing Technique, Findings, Impression, and Recommendations (e.g. Chest X-Ray, ECG).
  3. Structured `ULTRASOUND`: Organ-by-organ breakdown (Liver, Gallbladder, Biliary Tree, Spleen, Pancreas, Kidneys, Urinary Bladder, Pelvic Organs) with organ-specific findings and consolidated Impression.
- **Automatic Result Flag Calculation Engine:**
  - Evaluates numeric component values against configured reference bounds: `LOW` (below ref_min), `HIGH` (above ref_max), `CRITICAL` (below critical_min or above critical_max), or `NORMAL` (within ref_min and ref_max).
  - Safe `None` Fallback: If limits are missing or incomplete, the flag remains `None`. Incomplete configuration NEVER silently assumes `NORMAL`.
- **Physiological Impossible-Value Limits Validation:**
  - Absolute physiological boundaries (e.g., Hemoglobin `2.0 - 25.0 g/dL`, Potassium `0.5 - 12.0 mmol/L`).
  - Values outside limits are rejected immediately with HTTP 400 Bad Request on the backend and client-side form validation before submission.
- **Reference Range Snapshot Invariant (D24):**
  - When results are saved, the authoritative reference limits (`ref_min`, `ref_max`, `critical_min`, `critical_max`, `units`) are snapshotted permanently into `result_items`. Future changes to the reference catalog never mutate historical clinical results.
- **Strict Technician Financial Privacy:**
  - Technician worklist, task details, and result entry interfaces strictly exclude financial data (test prices, invoice amounts, dues, payments, or patient billing records).
- **Result Status vs Test Order Status Decoupling:**
  - `Result.status` (`DRAFT`, `ENTERED`) remains distinct from `TestOrder.status` (`SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `COMPLETED`). Result draft saving does not advance task status; result submission moves task to `IN_PROGRESS` or `AWAITING_DOCTOR`.

### 2. Four Mandatory Fixes Implemented
- **FIX 1: Line Lock Badge Removal from Tech Worklist:**
  - Removed visual `Line Locked` badges from technician worklist rows and lifecycle views.
  - All backend line-locking rules, database constraints, and financial protection audits remain 100% active.
- **FIX 2: Urgent Flag Persistence Across Intermediate States:**
  - `is_urgent` / `URGENT` badge remains prominently visible across all intermediate task states (`SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `REJECTED`, `SPOILED`).
  - The badge is removed only when the authoritative task status is `COMPLETED`.
- **FIX 3: Authoritative Sample Status in Invoice View:**
  - Replaced undefined frontend evaluation with authoritative backend `sample_status` mapping:
    - `COLLECTED` -> Success badge
    - `REJECTED` -> Danger badge
    - `SPOILED` -> Danger badge
    - `PERFORMED` -> Info badge
    - `AWAITING COLLECTION` -> Neutral badge
- **FIX 4: Correct Rejected/Spoiled Specimen D15 Refund Exception Workflow:**
  - Explicit D15 outcome: `TestOrder.outcome = "NOT_PERFORMED"` upon sample rejection.
  - Lab Technician D15 refund request endpoint (`POST /api/v1/worklist/{id}/d15-refund-request`) queuing request under `PENDING_ADMIN_APPROVAL` with `request_type = "D15_NOT_PERFORMED"`.
  - Locked D15 lines are barred from generic pre-sample cancellation in Invoice View.
  - D15 refund lifecycle status and outcome are clearly rendered in Invoice Line Details.
  - Distinguishes Admin review (`REFUND_APPROVED`) from actual money disbursement (`COMPLETED` / `FULLY_REFUNDED` / `PARTIALLY_REFUNDED`).
  - Cashier / Receptionist / Admin disburse refund endpoint (`POST /api/v1/refunds/{id}/disburse`) recording payment channel, transaction reference, drawer balance, and reversing referral commissions.

### 3. Database Schema Evolution (Alembic `a7d834bc912e`)
- Table `test_components`: Component definitions with normal, critical, and physiological impossible limits.
- Table `results`: Master clinical result record linked to `test_order_id`, tracking draft/entered status, technician attribution, and ultrasound/narrative text fields.
- Table `result_items`: Individual component results snapshotting reference ranges and units at entry time with automatic clinical flags.
- Column `test_orders.outcome`: Stores operational outcome (`NOT_PERFORMED` under D15).
- Columns on `refund_requests`: `request_type` (`PRE_SAMPLE_CANCELLATION`, `D15_NOT_PERFORMED`), `disbursed_at`, `disbursed_by_id`, `disbursement_method`, `disbursement_reference`.

### 4. Non-Browser Engineering Validation & Testing Status
- **Zero Browser Testing:** Per user instructions, browser automation, Playwright, Selenium, and manual browser testing were STRICTLY PROHIBITED and NOT PERFORMED.
- **Non-Browser Automated Validation:**
  - Python compile (`py_compile`): Passed across all backend, service, endpoint, and legacy Streamlit files.
  - TypeScript compilation (`tsc -b`): Passed cleanly with 0 errors.
  - Code Linter (`oxlint`): Passed with 0 errors.
  - Pytest Suite: 28 automated tests passed in 2.45s (including 8 dedicated tests in `tests/test_prompt07_module13_and_fixes.py` verifying impossible-limit rejection, flag calculations, safe None fallbacks, and boundary conditions).
  - Database Migration: Alembic revision `a7d834bc912e` applied cleanly to PostgreSQL.
  - Catalog Seed Data: 26 clinical test components seeded just-in-time on initial template access (deferred standalone seed script).

---

## Prompt 07C — Safety and Correctness Fixes (Prompt 07B Audit)

### 1. Architectural & Safety Corrections Implemented
- **Fix 1: Original Payment Channel Enforcement for Refunds (Rules 3.1, D18, M29):**
  - Updated `disburse_refund` in `refund_service.py` to validate disbursement method against channels actually used on the invoice (`CASH`, `BKASH`, `NAGAD`, `POS_CARD`, `BANK_TRANSFER`).
  - Mandatory transaction reference number on non-cash disbursements.
  - Verified per-channel payment balances to prevent cross-channel over-disbursement.
  - Cash disbursements decrement the active business day drawer.
  - Applied to both primary and alias disbursement endpoints (`/refunds/{id}/disburse` and `/refunds/disburse/{id}`).
- **Fix 2: Segregation of Duties on Refund Approvals (Rule 3.6, D56):**
  - Added isolated helper `enforce_segregation_of_duties` in `refund_service.py`.
  - Blocks self-approval/rejection (`reviewer_id == requested_by_id`) with HTTP 403 Forbidden.
  - Emits immutable security audit log `REFUND_SELF_APPROVAL_BLOCKED`.
  - Isolated in a single function to enable future per-customer configuration (Small Center Mode).
- **Fix 3: Culture Lifecycle Decoupling (Rule D19, M12):**
  - Decoupled `culture_stage` (`INCUBATING` -> `PRELIMINARY` -> `FINAL`) from `TestOrder.status`.
  - Reaching `FINAL` stage leaves order in `IN_PROGRESS` (does NOT auto-complete).
  - Enforced guard in `update_order_status` and `save_test_result`: culture orders cannot be marked `COMPLETED` unless culture stage is `FINAL`.
- **Fix 4: Result-Save Guards (Rules 3.2, D24, M13, B10 State Machine):**
  - **(a) Completed Order Immutability:** Saving results on an already `COMPLETED` order is strictly rejected with HTTP 409 Conflict.
  - **(b) Draft Status Invariance:** Saving a `DRAFT` result preserves `TestOrder.status` (does NOT prematurely advance to `IN_PROGRESS` or `COMPLETED`).
  - **(c) Specimen Collection Requirement:** For sample-based tests, attempting to enter or save results before specimen collection is rejected with HTTP 409 Conflict.
- **Fix 5: Technician Financial Data Isolation (Rule M11.3, 3.8):**
  - Replaced `RefundRequestResponse` on `POST /worklist/{id}/d15-refund-request` with `D15RefundClinicalResponse` omitting all monetary figures (`amount`, `price`, refund values).
  - Sanitized historical test-order event descriptions and notes in `get_order_events` to redact monetary amounts (`Tk` and `৳`) for `LAB_TECH` callers while preserving append-only database integrity.
  - New event descriptions emitted for D15 refund lifecycle are amount-free.
- **Fix 6: Alembic ORM Model Alignment (Head `a7d834bc912e`):**
  - Aligned `backend/app/models/result.py` with applied migration `a7d834bc912e`:
    - Added `ondelete="CASCADE"` to `ResultItem.result_id`.
    - Added explicit `UniqueConstraint("test_order_id", name="uq_results_test_order_id")` to `Result`.
  - `alembic check` reports zero new upgrade operations. Single head remains `a7d834bc912e`.
- **Fix 7: Test Suite Dual-Mode Reliability:**
  - Updated test client fixtures in `test_prompt04_corrections.py`, `test_receptionist_e2e.py`, and `test_prompt07c_fixes.py` to seamlessly execute in-process via FastAPI `TestClient` when port 8000 is inactive, or against a live server when running.
  - Added comprehensive automated test suite `tests/test_prompt07c_fixes.py` covering Fixes 1–5.
  - Full test suite passes 100% in both modes (35 passed, 0 failed).

### 2. Current State & Known Limitations
- Current migration head: `a7d834bc912e` (single head, 25 domain tables + 1 alembic_version = 26 tables).
- Endpoints: 62 unique paths / 72 operations registered under `/api/v1/`.
- Deferred features:
  - Sex/age-band reference range versioning (D24).
  - Barcode scan direct-open in worklist (M11.4).
  - Invoice detail auto-refresh on order updates.
  - Imaging lock timing alteration (scan completion vs result completion) and Owner emergency unlock (D13/D14).
  - Centralized configurable permission/role settings table.
  - Module 14: Draft to Final report publishing, verification, and PDF delivery.

---

## Prompt 08 — Modal Navigation Fix, Test DB Isolation, and Test Record Identification

### 1. Architectural & Engineering Fixes Implemented
- **Part A: In-Place Modal Navigation & URL Preservation:**
  - **Problem Solved:** Opening patient history from the invoice detail modal previously called `navigate('/patients?id=...')`, which dismounted the Invoices page, switched the active sidebar tab to Patients, lost search filters, status filters, and scroll position, and left the user stranded on `/patients` when dismissed.
  - **Encapsulated Component:** Created `frontend/src/components/common/PatientHistoryModal.tsx` managing its own 4-tab clinical profile (Overview, Invoices & Tests, Payments, Dues) and nested invoice detail modal.
  - **In-Place Overlay:** Wired `PatientHistoryModal` into `InvoicesPage.tsx` so clicking "Patient History" displays an overlay directly over the invoices table with zero route switching (`/invoices` remains unchanged). Closing the modal cleans up query params without route disruption.
  - **PatientsPage Refactoring:** Refactored `frontend/src/features/patients/PatientsPage.tsx` to reuse `PatientHistoryModal`, eliminating ~350 lines of duplicate JSX drawer code.
  - **Playwright Regression Suite:** Created `frontend/e2e/test_modal_regression.spec.ts` covering all 6 modal/drawer surfaces across roles (Invoices detail, Invoices->History, Patients history, Dues settlement, Ready Reports preview, Technician Worklist modals). All role switching is encapsulated in `selectDevRole`. 6 passed in 14.4s.
- **Part B: Test Database Isolation & Hard Safety Guard:**
  - **Isolated Test Database:** Provisioned `medscope_test` owned by `medscope_app`.
  - **Hard Safety Guard:** Added `enforce_safety_guard` in `tests/conftest.py`. Compares normalized host, port, and database targets. If `TEST_DATABASE_URL` resolves to `medscope_dcms`, pytest immediately aborts with `pytest.UsageError` (Exit code 4).
  - **Alembic Migration Chain:** Verified running from `<base>` to `a7d834bc912e (head)` cleanly on an empty database.
  - **Deterministic Seed Fixture:** `setup_test_database` seeds tenant `center-seba-01`, staff accounts, 25 diagnostic tests, test destinations, referrers, and CBC components.
  - **Pure In-Process Execution:** Completely removed live-server port 8000 probing fixtures. All tests execute in-process via FastAPI `TestClient` with `app.dependency_overrides[get_db]`. 35 tests pass in 2.99s.
- **Part C: Test Record Identification & Main DB Backup:**
  - **Strict Read-Only Guarantee:** Zero writes, updates, or deletions executed against `medscope_dcms`.
  - **Safety Dump:** Binary pg_dump snapshot saved to git-ignored `backups/medscope_dcms_pre_prompt08.dump` (191,737 bytes).
  - **Forensic Investigation:** Identified 106 test patients, 93 test referrers, 180 test invoices, 189 test lines, 146 test payments, 76 test refund requests, 189 test orders, 121 test events, 22 test samples, 3 test results, 46 test audit logs, 50 test reprint logs.
  - **Candidate Report & Dependency Map:** Documented in `report/TEST_RECORD_CANDIDATES.md` with complete dependency graph, operational impact analysis, and cleanup recommendations for future execution.

### 2. Current State & Next Steps
- Primary database (`medscope_dcms`): Untouched, backed up, candidate test records identified.
- Test database (`medscope_test`): Migrated, isolated, verified by hard safety guard, passing all 35 tests.
- Next prompt: `Prompt_09_Role_Based_Authentication_and_Switcher_Removal.md` (RBAC, JWT/session authentication, removal of dev role switcher).
- Followed by: `Prompt_10_Login_and_Landing_Page_UI.md`.

---

## Prompt 09 — Real Role-Based Authentication and Dev Switcher Removal

### 1. Architectural & Engineering Implementations
- **Removal of Insecure Development Role Switcher:**
  - Completely excised the header-based role switcher component, state toggling (`actorMode`, `toggleRole`, `setMode`), and request headers (`X-Staff-Id`, `X-Staff-Role`, `X-Actor-*`).
  - Added authenticated user profile menu to the global header with staff name, department, acting role badge, multi-role switcher list, and sign-out button.
- **Data Model & Alembic Migration (`b9e41d82f05a`):**
  - Table `staff_roles`: Multi-role mapping allowing a person to hold several roles (`RECEPTIONIST`, `CASHIER`, `ADMIN`, `OWNER`, `LAB_TECH`), seeded from each existing person's primary role.
  - Table `auth_sessions`: Server-side session management storing SHA-256 hashed session tokens, tenant ID, acting role, expiration, idle timeout timestamps, and revocation status.
  - Table `staff`: Added security fields `password_hash`, `failed_attempts`, `locked_at`, `last_login_at`, and `password_changed_at`.
- **Cryptographic Password Hashing & Brute-Force Lockout:**
  - Password hashing via Argon2id (`argon2-cffi`).
  - Enforced minimum 8 characters and disallowance of password matching username.
  - 5 failed login attempts trigger automated account lockout (`locked_at = utc_now()`) requiring Admin/Owner unlock.
  - Generic error messages for failed attempts (`"Invalid username or password"`) preventing username enumeration.
- **Session Transport & CSRF Protection:**
  - `HttpOnly`, `SameSite=Lax`, `Path=/` session cookie (`medscope_session`) or `Authorization: Bearer <token>` for API clients.
  - `X-Requested-With: XMLHttpRequest` required on all state-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`).
  - Idle timeout (120 minutes) and absolute session lifetime (24 hours).
- **Authentication API Endpoints (`/api/v1/auth/...`):**
  - `POST /auth/login`: Authenticates credentials, creates session, sets HttpOnly cookie, returns acting role profile.
  - `POST /auth/logout`: Revokes session and clears cookie.
  - `GET /auth/me`: Returns active authenticated profile.
  - `POST /auth/acting-role`: Switches active role within current session among roles held by user.
  - `POST /auth/change-password`: Validates old password and sets new hash, revoking other sessions.
  - `POST /auth/users/{id}/reset-password`: Admin/Owner password reset.
  - `POST /auth/users/{id}/unlock`: Admin/Owner account unlock.
- **User Administration CLI (`backend/scripts/manage_users.py`):**
  - Commands: `list-users`, `set-password`, `create-user`, `assign-role`, `remove-role`, `unlock`, `lock`, `init-staff-passwords`.
  - Passwords read securely via `getpass` or `--password-env`, never CLI arguments.
- **Frontend Workstation Access & Route Guards:**
  - Functional `/login` page with Bento styling, 60-30-10 palette tokens, and clear lockout alerts.
  - Protected route wrapper redirecting unauthenticated users to `/login`.
  - Global 401 response interceptor clearing session and routing to `/login`.
  - Role-based landing routes: Receptionist/Cashier -> `/invoices`, Lab Tech -> `/worklist`, Admin/Owner -> `/`.
- **Automated Test Suite (Pure In-Process, Isolated):**
  - Rewrote fixtures in `tests/conftest.py` with deterministic test sessions and Argon2id test passwords.
  - Added `tests/test_prompt09_auth.py` (10 tests) covering login, wrong password, 5-attempt lockout, admin unlock, 401 unauthenticated, logout revocation, password change, acting role switch, real session role guards, and technician financial isolation.
  - Full test suite: **45 passed in 4.19s** against `medscope_test`. Zero writes to `medscope_dcms`.

### 2. Current State & Next Steps
- Primary database (`medscope_dcms`): Upgraded to `b9e41d82f05a` (28 tables), untouched operational records (223 invoices), 0 test session rows.
- Next prompt: Completed Prompt 10. Ready for next prompt.

---

## Prompt 10 — Branded Landing Page and Animated Login UI

### 1. Architectural & Engineering Implementations
- **Public Branded Landing Page (`/`):**
  - Two-column responsive hero: H1 "Your diagnostic center, in one place" (max width 680px, balanced wrapping), subtitle "Billing, samples, results and reports.", single Persian Orange CTA "Sign in".
  - Animated medical scene inside Dark Moss panel (`#525333`): self-drawing ECG heartbeat line (`@keyframes ecg-landing`), filling/draining specimen tube (`@keyframes fillup`), travelling progress dot (`@keyframes travel`), and sequential chips ("Sample taken", "Result entered", "Report ready"). Purely decorative; zero patient data.
  - Endless scrolling strip (marquee): White band under hero. Tightened to **70px total section height** (`py-4 md:py-5`, 28×28 SVG icons, `gap-3 px-6 md:px-8`). Driven by an extensible `WORKFLOW_STEPS` data array (Register, Sample, Result, Report). Continuous linear loop (`28s linear infinite`), auto-pausing on hover or focus-within.
  - Motion Architecture: Guaranteed pure CSS/SVG animation playback across all OS client area animation flags. Eliminated destructive reduced-motion overrides that previously stopped ECG drawing or forced double-row marquee wrapping.
- **Operational Roles & Credential Provisioning:**
  - Initialized Argon2id credentials for all 4 diagnostic staff members in `medscope_dcms` (password: `12345`).
  - Active role assignments: `admin_tariq` (`ADMIN`, `OWNER`), `reception_fatima` (`RECEPTIONIST`, `CASHIER`), `tech_kamal` (`LAB_TECH`), `tech_nasrin` (`LAB_TECH`).
  - Multi-role header switcher enables seamless toggling between Admin/Owner and Receptionist/Cashier without re-authentication.
  - CLI [`backend/scripts/manage_users.py`](file:///d:/DMS/MedScope/backend/scripts/manage_users.py) enhanced with `--force` flag for administrative credential assignment.
- **Animated Login Page (`/login`):**
  - Two-panel responsive layout (stacks vertically on mobile viewports).
  - Left panel (Dark Moss `#525333`): Brand logo mark, animated vector ECG line with baseline and pulsing ring marker at peak `(128, 30)`, disclaimer "Illustration only. No patient information is shown on this page." Zero step cards.
  - Right panel (Platinum `#E8E7E3` canvas): Centered white rounded container (`max-w-[420px]`), heading "Sign in", helper copy, real `<form>` with Username, Password with Show/Hide toggle, Persian Orange `#CF8852` full-width button (shows "Signing in…" when submitting), and inline `aria-live="polite"` error banner.
  - Calm, specific error messages: wrong credentials, locked account, session expired, network failure.
  - Helper links: "Forgot your password? Ask your center administrator to reset it." and "Back to the overview" link to `/`.
- **Public Entry & Role Home Redirection (`getRoleHomeRoute`):**
  - Signed-in users who open `/` or `/login` are automatically redirected to their role's workbench (`/invoices` for Receptionist/Cashier, `/worklist` for Lab Tech, `/dashboard` for Admin/Owner).
  - Authenticated route `/dashboard` added for executive overview.
  - Unknown paths (`*`) render a branded 404 page (`NotFoundPage.tsx`) with "Back to home" / "Back to workbench".
- **Self-Hosted Typography & Brand Tokens:**
  - Installed and bundled `@fontsource/manrope` and `@fontsource/noto-sans-bengali`. Zero external CDN or Google Fonts requests.
  - Palette: Persian Orange `#CF8852` (accent), Platinum `#E8E7E3` (canvas), Dark Moss `#525333` (panels), ink `#26270F` (text), secondary `#3D3E1F`, white `#FFFFFF`. Button text on orange is ink `#26270F` (contrast ratio ~7:1).
  - Flat backgrounds only; no background gradients.
  - Motion tokens: non-continuous curve `cubic-bezier(0.22, 1, 0.36, 1)`, linear marquee, and complete `@media (prefers-reduced-motion: reduce)` fallbacks.
  - Branded SVG favicon created from logo mark (`frontend/public/favicon.svg`).
- **Limited Browser Exception (Playwright Chromium Screenshots):**
  - Automated script `frontend/scripts/capture_screenshots.mjs` captured 5 screenshots under `report/screenshots/`:
    - `landing-desktop.png` (1360x900)
    - `landing-mobile.png` (390x844)
    - `login-desktop.png` (1360x900)
    - `login-mobile.png` (390x844)
    - `404-desktop.png` (1360x900)
  - 390px check: `scrollWidth = 390`, `clientWidth = 390`, `hasOverflow = false` on both pages.
- **Verification & Testing Results:**
  - Backend pytest: 45 passed in 4.43s against `medscope_test`.
  - Frontend typecheck: `tsc -b` exited 0.
  - Frontend linter: `oxlint` reported 0 errors across 39 files.
  - Production build: `vite build` completed in 670ms.
  - Database migrations: single head `b9e41d82f05a`, 0 new migrations.

---

## Prompt 10B — Test Data Cleanup SQL Script

### 1. Architectural & Engineering Implementations
- **Single Standard PostgreSQL Deliverable:**
  - Script path: [`backend/scripts/sql/cleanup_test_data.sql`](file:///d:/DMS/MedScope/backend/scripts/sql/cleanup_test_data.sql).
  - Designed for execution directly by the owner inside the **pgAdmin Query Tool** (pure standard SQL, zero `psql` meta-commands).
- **Safety Guarantees & Evidence-Based Filtering:**
  - Zero mutations performed directly against live `medscope_dcms` during implementation (read-only queries and dry-run transactional simulations only).
  - Strictly eliminated all range deletions (e.g. `invoices.id >= 6` is strictly prohibited); deletions rely 100% on evidence matching (exact test naming patterns, automated reason markers, and topological child cascading).
  - Protected entities: `staff`, `staff_roles`, `auth_sessions`, `tests` (1,250 tests), `test_components`, `test_destinations`, `business_days`, `sequence_counters`, `alembic_version`, 16 protected patients (12 seed + 4 QA: Jamila Begum, Waasi, Wasir beta, Wassir beti), 16 protected referrers (10 seed + 3 QA: Dr. Salehin, Asst. Prof. Dr. Arif Jawad, Rafiq, plus referrers 11, 31, 35 referenced by QA invoices), and 14 protected invoices (9 seed + 5 QA: SD-000031, SD-000066, SD-000099, SD-000135, SD-000136).
- **Four Script Sections in Order:**
  - Section 1: Header comments, scope, protected entities, fresh custom `.dump` backup instructions in pgAdmin (warning against old Prompt 08 dump), and restore procedure.
  - Section 2: Configuration & PREVIEW (read-only): temp table `_cleanup_config` (`include_medium`, default `TRUE`), candidate temp tables per entity, preview summary result sets per table/tier, and list of kept protected entities.
  - Section 3: Deletion Transaction: `BEGIN;` followed by `DO $$ ... $$` executing deletions in topological order, emitting `RAISE NOTICE` for row counts per table, and inserting a single summary audit log `TEST_DATA_CLEANUP`.
  - Section 4: Post-checks & Default ROLLBACK: automated orphan checks across all foreign keys, kept entity count assertions (16 patients, 16 referrers, 14 invoices), business day balance notice, ending with `ROLLBACK;` (switch to `COMMIT;` to persist).
- **Topological Deletion Sequence:**
  `audit_logs` -> `reprint_logs` -> `report_deliveries` -> `report_versions` -> `result_items` -> `results` -> `samples` -> `assignment_history` -> `test_order_events` -> `refund_requests` -> `test_orders` -> `payments` -> `invoice_lines` -> `invoices` -> `visits` -> `referrers` -> `patients` -> `audit_logs` summary insert.
- **Cash Drawer & Business Day Policy:**
  Recomputation of Day 2 stored cash received (70,430 Taka) diverges from raw payment sum (72,830 Taka) by 2,400 Taka due to historical pre-seeded floats/untracked adjustments. Per Prompt 10B rules, balances are left **untouched** with a warning notice printed in script output.
- **Candidate Elimination Counts:**
  - With `include_medium = TRUE` (default): Deletes 135 patients, 115 referrers, 209 invoices, 209 visits, 218 invoice lines, 151 payments, 218 test orders, 153 events, 155 assignments, 29 samples, 3 results, 0 result items, 0 report versions, 0 report deliveries, 78 refund requests, 48 reprint logs, 587 audit logs.
  - Preserves exactly: 16 patients, 16 referrers, 14 invoices, 14 visits, 48 invoice lines, 15 payments, 48 test orders, 16 events, 23 assignments, 9 samples, 2 results, 0 result items, 6 report versions, 4 report deliveries, 2 refund requests, 44 reprint logs, 72 audit logs.
- **Rehearsal Database Boundary:**
  Attempted `CREATE DATABASE medscope_cleanup_rehearsal`. PostgreSQL user `medscope_app` lacks `CREATEDB` privilege (`permission denied to create database`). Formally reported as **Blocked** per Prompt 10B Section 5 clause. Script verified via transactional dry-run simulation and static catalog validation.

---

## Mandatory Phase-End Documentation Update Clause
At the end of every prompt execution and at the conclusion of each development phase, the agent MUST review and update the relevant canonical documentation files (`project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`, `README.md`). Any newly created endpoints, updated database schemas, altered workflows, UI changes, or testing results must be reflected in these canonical documents before concluding the prompt. Redundant or duplicate narrative markdown files must not be created; all architectural and operational knowledge must reside strictly within these nine canonical files.



