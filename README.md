# MedScope Diagnostic Center Management System (DCMS)

MedScope is a comprehensive multi-tenant Diagnostic Center Management System designed for clinical operations in Bangladesh. It manages the entire clinical and operational lifecycle: patient intake, bilingual registration, investigation pricing, individual and master discounts, payments and dues settlement, pre-sample refund requests, laboratory workstation routing, specimen collection, result entry and verification, report delivery with financial hold gating, inventory, cashier day sessions, referral commissions, accounting, and platform administration.

---

## 1. Modern Architecture (Receptionist Portal Vertical Slice)

In November 2026, the front-desk operational slice of MedScope was modernized into a decoupled, high-performance client-server stack while preserving legacy clinical and double-entry accounting routines:

- **Frontend Client:** React 19 + TypeScript + Vite 8 + Tailwind CSS v4 + Lucide Icons + React Router.
  - Implements the 60-30-10 palette (Platinum `#E8E7E3`, Dark Moss `#525333`, Persian Orange `#CF8852`, ink `#26270F`).
  - Features self-hosted typography via `@fontsource/manrope` and `@fontsource/noto-sans-bengali` (zero external CDN or Google Fonts runtime dependencies).
  - Public branded landing page (`/`) with two-column hero, animated medical scene (ECG loop, filling tube, travelling dot, sequential chips), and extensible endless marquee strip (Register, Sample, Result, Report).
  - Animated login page (`/login`) with Dark Moss brand panel (ECG loop with pulsing peak marker) and Platinum sign-in panel with visible labels, password Show/Hide toggle, and calm error feedback.
  - Every login lands on `/dashboard` (Prompt 10D). The Dashboard shows each role only what it may see (no money for Lab Tech) and links to its main work page.
  - One login = one fixed role; Owner/Admin **User Management** (`/users`) with a Create User tab and per-user permissions (Prompt 10D).
  - Invoice **Save Draft** / **Finalize** (Prompt 10D): drafts have no operational effect and get the real invoice number only at Finalize.
  - Prompt 10E: visit age/gender required to Finalize; urgent fee computed by the backend; payment channels Cash, bKash, Nagad, Rocket, Card, Bank Transfer, Other (+ typed name); **room-based lab routing** (every technician of a room sees its orders; Admin/Owner reassign rooms); worklist tiles act as filters; Ready Reports filter and Preview Report in My Work (Lab); DOCTOR role.
  - Prompt 10F (owner findings + decisions A5/A11): **Assigned Tests** tab on Assign Tests (view only for front desk, Reassign Room for Admin/Owner until COMPLETED); result **Preview** for DRAFT and ENTERED saves (DRAFT clearly marked); one shared **Ready** definition (submitted result; completion not required) feeding the Lab tile/tab and the sidebar **Ready Results** list; sample rule reversed (NULL `sample_type` on a non-imaging test = sample required); an emptied room demotes its assigned-only orders to UNASSIGNED. No schema change.
  - Simple branded 404 page for unknown routes.
  - Features Bento grid layout, live duplicate phone detector, instant test selector with line discounts up to 100%, cash drawer tender calculator, workstation bench router, dues collector, pre-sample refund state machine, report due-hold release, and A4 Landscape Dual-Copy (Patient Copy | Office Copy) print views.
  - Inline global search with anchored dropdown categories and `Ctrl+F` shortcut.
- **Backend API:** FastAPI (Python 3.14) + Pydantic v2 + SQLAlchemy 2.0 ORM + Psycopg 3.
  - 129 RESTful endpoint paths (144 operations) across 17 modules, including convenience alias routes.
  - Central permission layer (`backend/app/core/permissions.py`): every route requires a named permission; role defaults + per-user overrides.
  - Strict whole-Taka integer currency representation (zero floating-point drift).
  - Multi-tenant data scoping and role-based access control with write-only commission privacy and strict technician financial data isolation.
  - Test catalog scaling: 1,250 active clinical tests across 10 diagnostic departments delivered via high-capacity endpoint (`limit=2500`).
  - Specimen lifecycle & barcode printing: Code 128 thermal labels (50×30mm), line cancellation lock, D15 rejected specimen workflow, and department extensions.
  - Clinical result entry engine: Component numeric tables, narrative reporting, structured ultrasound templates, automatic flag calculations (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`, `None`), impossible-value limit protection, and D24 permanent reference range snapshotting.
- **Database:** PostgreSQL 18 (`medscope_dcms` on `127.0.0.1:5432`) managed via Alembic.
  - Exactly 38 tables (37 domain entities + `alembic_version`; `reprint_logs` was folded into `audit_logs` in Prompt 19B); single Alembic head `a19b5c7d9e31` (Prompt 19B append-only audit log; before it `f9a2c4d6e8b1`, Prompt 18 accounting journal and day close).
  - Revision `f3c9a1d7e5b2` (Prompt 10E): `tests.lab_section` (backfilled), `test_orders.lab_section`, CHECK "a LAB_TECH has a room" (where all rows comply).
  - Revision `e8b2f4a6c1d3` (Prompt 10E): `sample_type` "None" → NULL, `payments.channel_detail`, `invoices.urgent_fee`, `invoice_lines.urgent_fee`, new channel rows on the open business day.
  - Revision `d7e5a91c4f02` (Prompt 10D): one role per user (`uq_staff_roles_staff_id`, dual-role accounts split), `staff.lab_section`, table `staff_permission_overrides`.
  - Revision `c3d10a7f2b61` (Prompt 10D): invoice drafts (`visit_id` nullable, `draft_payload`, `finalized_at`).
  - Revision `b9e41d82f05a`: Added `staff_roles` (multi-role mapping) and `auth_sessions` (server-side session storage); added security columns to `staff` (`password_hash`, `failed_attempts`, `locked_at`, `last_login_at`, `password_changed_at`).
  - Revision `a7d834bc912e`: Added `test_components`, `results`, `result_items` tables; added `outcome` to `test_orders`; added `request_type`, `disbursed_at`, `disbursed_by_id`, `disbursement_method`, `disbursement_reference` to `refund_requests`.
  - Revision `f16c024d3e4a`: Added line locks (`is_locked`, `locked_at`, `locked_reason`) to `invoice_lines`, specimen audit fields to `samples`, department extensions to `test_orders`, and created append-only `test_order_events` table.
  - Revision `e05b9b1a2c3d`: Added Test Catalog readiness columns, staff department, default sample route, and test order operational routing & clock tracking.
  - Revision `bdc0201a1170`: Added persistent `refund_status` column (`NO_REFUND`, `PARTIALLY_REFUNDED`, `FULLY_REFUNDED`) on `invoices` with automated backfill.
  - Revision `c94589ffc4ee`: Added `prescribed_by_id` with foreign key referencing `referrers.id` on `invoices`.
  - Partial unique index `idx_business_day_single_open` ensuring a single active business day per tenant.
  - Concurrency-safe monotonic sequence generator (`sequence_counters`).
- **Legacy Monolith:** Streamlit (`DCMS V1.py`) + SQLite + `accounting.py` preserved in parallel for laboratory analysis and double-entry accounting.

---

## 2. Quick Start & Local Development

### Prerequisites
- Python 3.10+ (Python 3.14 recommended)
- Node.js 20+ and npm
- PostgreSQL 18 running on `127.0.0.1:5432` with user `medscope_app` (or configured via environment)

### Environment Configuration
Configure `.env` in the project root:
```env
DATABASE_URL=postgresql+psycopg://medscope_app:medscope_secure_pass_2026@127.0.0.1:5432/medscope_dcms
TEST_DATABASE_URL=postgresql+psycopg://medscope_app:medscope_secure_pass_2026@127.0.0.1:5432/medscope_test
DEFAULT_TENANT_ID=center-seba-01
PORT=8000
```

### Launch Commands

#### 1. Start the FastAPI Backend
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

#### 2. Start the Modern React Frontend
```powershell
cd frontend
npm install
npm run dev
```
Front Desk Portal: [http://127.0.0.1:5173](http://127.0.0.1:5173)

#### 3. Database Migrations & Seeding
```powershell
# Run Alembic migrations to head
python -m alembic upgrade head

# Seed initial tenant, staff, test catalog, and patients
python backend/scripts/seed.py
```

#### 4. Run Legacy Streamlit Monolith (Optional / Lab & Accounting)
```powershell
python -m streamlit run "DCMS V1.py" --server.port 8501
```

---

## 3. Real Role-Based Authentication & User Administration CLI

In Prompt 09, the insecure development role switcher was **permanently removed**. All requests now require cryptographically validated, server-side sessions transportable via `HttpOnly` cookies (`medscope_session`) or `Authorization: Bearer <token>` headers, reinforced with `X-Requested-With` CSRF verification.

### Staff Identity & Operational Roles
| Staff Username | Display Name | Assigned Roles | Primary Workstation Landing |
| :--- | :--- | :--- | :--- |
| `reception_fatima` | Fatima Akter | `RECEPTIONIST` | `/dashboard` → Invoices |
| `cashier_fatima` | Fatima Akter — Cashier | `CASHIER` | `/dashboard` → Invoices |
| `admin_tariq` | Tariqul Islam | `ADMIN` | `/dashboard` |
| `owner_tariq` | Tariqul Islam — Owner | `OWNER` | `/dashboard` |
| `tech_kamal` | Kamal Hossain | `LAB_TECH` (Hematology, Room 101) | `/dashboard` → My Worklist |
| `tech_nasrin` | Nasrin Sultana | `LAB_TECH` (Biochemistry, Room 102) | `/dashboard` → My Worklist |
| `tech_micro` | Microbiology Technician | `LAB_TECH` (Microbiology, Room 105) | `/dashboard` → My Worklist |
| `tech_usg` | Ultrasonography Technician | `LAB_TECH` (Ultrasonography, Room 204) | `/dashboard` → My Worklist |

Prompt 10E: technicians see **all orders of their room** (not only their own). Roles: OWNER, ADMIN, RECEPTIONIST, CASHIER, LAB_TECH, DOCTOR (DOCTOR is creatable in User Management). A LAB_TECH must have a lab room; Prompt 10F: a room losing its last active technician turns its assigned-only orders back to UNASSIGNED.

Prompt 10D: **one login = one fixed role** (no role switching). The former dual-role accounts were split; the new accounts reuse the existing development password.

> **Implemented in Prompt 10D:** one login = one fixed role, Dashboard landing for every role, more users (one default LAB_TECH per lab section), and the User Management page with a Create User tab and per-user permissions. See `docs/SCOPE.md` §5 and `docs/ARCHITECTURE.md` ADL-032 to ADL-039. **Prompt 10E** decisions are ADL-040 to ADL-047; **Prompt 10F** decisions are ADL-048 to ADL-051. The CLI below is single-role too.

### User Management CLI (`backend/scripts/manage_users.py`)
User passwords and roles are managed securely through the CLI without committing secrets:
```powershell
# List all registered staff, active roles, and account lock status
python backend/scripts/manage_users.py list-users

# Set a staff password securely (prompts interactively via hidden getpass)
python backend/scripts/manage_users.py set-password --username reception_fatima

# Set password from an environment variable (for headless automation)
$env:NEW_PASSWORD = "..."
python backend/scripts/manage_users.py set-password --username admin_tariq --password-env NEW_PASSWORD

# Unlock an account locked after 5 failed password attempts
python backend/scripts/manage_users.py unlock --username tech_kamal

# Set a user's single role (one login = one role)
python backend/scripts/manage_users.py assign-role --username tech_usg --role LAB_TECH --lab-section ULTRASONOGRAPHY

# Provision a brand new staff user (a LAB_TECH needs --lab-section)
python backend/scripts/manage_users.py create-user --username tech_subrata --display-name "Subrata Roy" --roles "LAB_TECH" --lab-section MICROBIOLOGY

# One-off re-route of existing open orders to rooms (Prompt 10E; dry run unless --apply)
python -m backend.scripts.reroute_orders_to_rooms"
```

---

## 4. Testing & Verification Status

### Backend Pytest Suite:
- **Test Database Isolation:** Pytest executes strictly against the isolated test database `medscope_test` via `TEST_DATABASE_URL`. The primary development/QA database `medscope_dcms` is never touched by tests.
- **Hard Safety Guard:** Implemented in `tests/conftest.py` (`enforce_safety_guard`). If `TEST_DATABASE_URL` resolves to `medscope_dcms` (even under `localhost` or `127.0.0.1`), pytest immediately aborts with `pytest.UsageError` (Exit code 4).
- **Test Suite Results:** All 45 automated integration and unit tests in `tests/test_receptionist_e2e.py`, `tests/test_prompt04_corrections.py`, `tests/test_prompt07_module13_and_fixes.py`, `tests/test_prompt07c_fixes.py`, and `tests/test_prompt09_auth.py` pass 100% in-process via FastAPI `TestClient` in ~4.2s.
- **Authentication & Security Verified:** Argon2id password hashing, 5-attempt brute-force account lockout, admin unlock, session revocation on logout, multi-role switching, and strict rejection of unauthenticated requests.
- **Frontend Build & Types:** `tsc -b` compiled cleanly with 0 errors; `oxlint` passed with 0 errors across 36 files; Vite production build succeeds.

### Testing Policy & Verification Constraints:
Pursuant to the mandatory testing constraints:
- **Browser Automation (Playwright, Puppeteer, Selenium):** STRICTLY PROHIBITED and NOT PERFORMED in Prompt 09.
- **Manual Browser Testing:** STRICTLY PROHIBITED and NOT PERFORMED.
- **Non-Browser Automated Validation Executed:**
  - `python -m py_compile`: 100% of modified backend, service, schema, endpoint, and CLI scripts compiled cleanly with exit code 0.
  - `tsc -b`: Clean TypeScript typecheck across all React 19 components, auth context, login feature, and API client bindings with 0 errors.
  - `oxlint`: Clean linter run across 36 files with 0 errors.
  - `pytest`: 45 automated tests passed cleanly against `medscope_test`.
  - `alembic check`: Confirmed schema in sync with ORM models under single head `b9e41d82f05a` (0 new operations).

### Current status (Prompt 10F done — reported, 2026-11-13)
- Phase: **Prompt 18 implemented (reported)** — Module 21 accounting and Module 22 day open / close. A balanced, append-only double-entry journal (`accounts`, `journal_entries`, `journal_lines`; the database refuses UPDATE / DELETE and any unbalanced entry) is posted by the real events: bill confirmed, payment received, line cancelled / refund owed, refund paid, due written off, cash variance, bank deposit, owner withdrawal, small expense. Commission, visit-fee handover, consultant fee and outside-lab cost are **not** posted (Modules 19 / 20 / 28 are not built). Four V1 reports (cash book, daily income and expense, dues, cost by referrer; the last is 0 until commission exists) with a date range and CSV export for Excel. Day screen for Admin / Owner: expected cash by the D45 formula, counted cash, variance with a reason above an Owner-set tolerance (`cash_variance_tolerance`, default 0), wallet / bank channels on their own lines, bank deposit / owner withdrawal / expense entry, and Owner-only reopen with adjusting entries only. Migration `f9a2c4d6e8b1`. One new permission key, `accounting.view`. Module 17 handover and Module 18 dues (Prompt 17) are in place as before. See `report/PROMPT_18_IMPLEMENTATION_REPORT.md`. **Next step: the separate verification prompt, then owner browser acceptance** (`docs/TESTING.md` §21.2).
- `pytest`: 297 passed, 0 failed against `medscope_test` (Prompt 19B: Module 23 audit trail; Prompt 19 doctor / 3rd-party edit before it). `alembic heads`: single head `a19b5c7d9e31`. `alembic check`: no new operations. `tsc -b`, `oxlint` (0 errors) and `vite build` pass.
- Playwright specs were updated (login helper, Dashboard landing, Draft/Finalize; 10E: age/gender, channels, worklist tiles and room label). They were **not run** in Prompt 10E or 10F: `MEDSCOPE_E2E_PASSWORD` is not set in the agent environment, the receptionist spec creates records, and browser testing is the owner's acceptance step. 10F updated spec A5 for the new `/reports` tabs. See `docs/TESTING.md` §7.1, §11 and §13.
- Schema changes go through Alembic migrations only. Seed/cleanup scripts are dev/testing utilities outside the Alembic chain (`docs/DATABASE.md`).
- **Pre-go-live cleanup list** (hard-coded credentials, password rotation, test-DB fallback removal): `docs/TESTING.md` §12. It is for later and has not been acted on.

---

## 5. Canonical Documentation Architecture

All project documentation is consolidated into nine canonical markdown documents:

1. [`README.md`](README.md) - Quick start, system requirements, launch commands, environment variables, seed credentials.
2. [`project-context.md`](project-context.md) - Master state, tenant structure, data invariants, session logs, disposition table, and mandatory future prompt clause.
3. [`docs/SCOPE.md`](docs/SCOPE.md) - Functional scope, user roles, operational boundaries, and permissions matrix.
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Dual-stack architecture, directory layout, multi-tenancy, security headers, integer currency, ADL.
5. [`docs/DESIGN.md`](docs/DESIGN.md) - Visual tokens (60-30-10 palette: Platinum `#E8E7E3`, Moss `#525333`, Persian Orange `#CF8852`), typography, Bento layout, thermal printing.
6. [`docs/API.md`](docs/API.md) - Complete REST contract for all 16 modules, request/response models, query parameters, error responses (85 paths / 98 operations), and the permission keys.
7. [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) - Operational workflows (Intake -> Billing -> Assignment -> Sample -> Result -> Delivery -> Due Settlement -> Reprint) and UI/API Wiring Matrix.
8. [`docs/DATABASE.md`](docs/DATABASE.md) - Schema specification of 35 PostgreSQL tables (34 domain entities + alembic_version), relationships, indices, sequences, and test data cleanup script.
9. [`docs/TESTING.md`](docs/TESTING.md) - Test strategy, automated dual-mode test suite setup, executed test scenarios, results, and reproduction commands.
