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
  - Automatic role-based home route redirection for authenticated staff (`/invoices` for Receptionist/Cashier, `/worklist` for Lab Tech, `/dashboard` for Admin/Owner).
  - Simple branded 404 page for unknown routes.
  - Features Bento grid layout, live duplicate phone detector, instant test selector with line discounts up to 100%, cash drawer tender calculator, workstation bench router, dues collector, pre-sample refund state machine, report due-hold release, and A4 Landscape Dual-Copy (Patient Copy | Office Copy) print views.
  - Inline global search with anchored dropdown categories and `Ctrl+F` shortcut.
- **Backend API:** FastAPI (Python 3.14) + Pydantic v2 + SQLAlchemy 2.0 ORM + Psycopg 3.
  - 69 RESTful endpoint paths (79 operations across 15 modules, including convenience alias routes).
  - Strict whole-Taka integer currency representation (zero floating-point drift).
  - Multi-tenant data scoping and role-based access control with write-only commission privacy and strict technician financial data isolation.
  - Test catalog scaling: 1,250 active clinical tests across 10 diagnostic departments delivered via high-capacity endpoint (`limit=2500`).
  - Specimen lifecycle & barcode printing: Code 128 thermal labels (50×30mm), line cancellation lock, D15 rejected specimen workflow, and department extensions.
  - Clinical result entry engine: Component numeric tables, narrative reporting, structured ultrasound templates, automatic flag calculations (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`, `None`), impossible-value limit protection, and D24 permanent reference range snapshotting.
- **Database:** PostgreSQL 18 (`medscope_dcms` on `127.0.0.1:5432`) managed via Alembic.
  - Exactly 28 tables (27 domain entities + `alembic_version`).
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
| `reception_fatima` | Fatima Akter | `RECEPTIONIST`, `CASHIER` | `/invoices` (Intake, Billing & Counter Receipts) |
| `admin_tariq` | Tariqul Islam | `ADMIN`, `OWNER` | `/` (Executive Dashboard & Center Governance) |
| `tech_kamal` | Kamal Hossain | `LAB_TECH` | `/worklist` (Hematology Workstation) |
| `tech_nasrin` | Nasrin Sultana | `LAB_TECH` | `/worklist` (Biochemistry Workstation) |

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

# Assign an additional role to an existing user (enables role switching in UI)
python backend/scripts/manage_users.py assign-role --username reception_fatima --role CASHIER

# Provision a brand new staff user
python backend/scripts/manage_users.py create-user --username tech_subrata --display-name "Subrata Roy" --roles "LAB_TECH" --department "Microbiology"
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

---

## 5. Canonical Documentation Architecture

All project documentation is consolidated into nine canonical markdown documents:

1. [`README.md`](README.md) - Quick start, system requirements, launch commands, environment variables, seed credentials.
2. [`project-context.md`](project-context.md) - Master state, tenant structure, data invariants, session logs, disposition table, and mandatory future prompt clause.
3. [`docs/SCOPE.md`](docs/SCOPE.md) - Functional scope, user roles, operational boundaries, and permissions matrix.
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Dual-stack architecture, directory layout, multi-tenancy, security headers, integer currency, ADL.
5. [`docs/DESIGN.md`](docs/DESIGN.md) - Visual tokens (60-30-10 palette: Platinum `#E8E7E3`, Moss `#525333`, Persian Orange `#CF8852`), typography, Bento layout, thermal printing.
6. [`docs/API.md`](docs/API.md) - Complete REST contract for all 14 modules, request/response models, query parameters, error responses (62 paths / 72 operations).
7. [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) - Operational workflows (Intake -> Billing -> Assignment -> Sample -> Result -> Delivery -> Due Settlement -> Reprint) and UI/API Wiring Matrix.
8. [`docs/DATABASE.md`](docs/DATABASE.md) - Schema specification of 28 PostgreSQL tables (27 domain entities + alembic_version), relationships, indices, sequences, and test data cleanup script.
9. [`docs/TESTING.md`](docs/TESTING.md) - Test strategy, automated dual-mode test suite setup, executed test scenarios, results, and reproduction commands.
