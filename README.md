# MedScope Diagnostic Center Management System (DCMS)

MedScope is a comprehensive multi-tenant Diagnostic Center Management System designed for clinical operations in Bangladesh. It manages the entire clinical and operational lifecycle: patient intake, bilingual registration, investigation pricing, individual and master discounts, payments and dues settlement, pre-sample refund requests, laboratory workstation routing, specimen collection, result entry and verification, report delivery with financial hold gating, inventory, cashier day sessions, referral commissions, accounting, and platform administration.

---

## 1. Modern Architecture (Receptionist Portal Vertical Slice)

In November 2026, the front-desk operational slice of MedScope was modernized into a decoupled, high-performance client-server stack while preserving legacy clinical and double-entry accounting routines:

- **Frontend Client:** React 19 + TypeScript + Vite 8 + Tailwind CSS v4 + Lucide Icons + React Router.
  - Implements the 60-30-10 palette (Platinum `#E8E7E3`, Dark Moss `#525333`, Persian Orange `#CF8852`).
  - Features Bento grid layout, live duplicate phone detector, instant test selector with line discounts up to 100%, cash drawer tender calculator, workstation bench router, dues collector, pre-sample refund state machine, report due-hold release, and A4 Landscape Dual-Copy (Patient Copy | Office Copy) print views.
  - Inline global search with anchored dropdown categories and `Ctrl+F` shortcut.
- **Backend API:** FastAPI (Python 3.14) + Pydantic v2 + SQLAlchemy 2.0 ORM + Psycopg 3.
  - 46 RESTful endpoints under `/api/v1/` across 14 modules (including `/worklist` with Module 12 specimen lifecycle extensions and Module 13 clinical result entry).
  - Strict whole-Taka integer currency representation (zero floating-point drift).
  - Multi-tenant data scoping and role-based access control with write-only commission privacy and strict technician financial data isolation.
  - Test catalog scaling: 1,250 active clinical tests across 10 diagnostic departments delivered via high-capacity endpoint (`limit=2500`).
  - Specimen lifecycle & barcode printing: Code 128 thermal labels (50×30mm), line cancellation lock, D15 rejected specimen workflow, and department extensions.
  - Clinical result entry engine: Component numeric tables, narrative reporting, structured ultrasound templates, automatic flag calculations (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`, `None`), impossible-value limit protection, and D24 permanent reference range snapshotting.
- **Database:** PostgreSQL 18 (`medscope_dcms` on `127.0.0.1:5432`) managed via Alembic.
  - Exactly 26 tables (25 domain entities + `alembic_version`).
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

## 3. Seed Credentials & Development Staff Switcher

The modern front-desk interface includes an active **Development Staff Switcher** in the header to exercise role-based workflows:

| Identity | Staff ID | Role | Purpose |
| :--- | :---: | :--- | :--- |
| **Fatima Akter** | `1` | `RECEPTIONIST` | Daily front desk intake, billing, payments, unassigned routing, pre-sample refund requests, report delivery. |
| **Tariqul Islam** | `2` | `ADMIN` | Administrative supervision, refund approval/rejection, emergency due override delivery, business day closure. |
| **Kamal Hossain** | `3` | `LAB_TECH` | Hematology laboratory technician; workstation tasks, Quick Route sample taken, turnaround clocks. |
| **Nasrin Sultana** | `4` | `LAB_TECH` | Biochemistry laboratory technician; biochemical investigations, specimen collection tracking. |

---

## 4. Testing & Verification Status

### Test Catalog Scaling Verification:
- **Catalog Scale:** 1,250 active diagnostic tests under tenant `center-seba-01` verified in PostgreSQL.
- **API Tests:** `GET /api/v1/tests` returns HTTP 200 with all 1,250 tests; verified search (`q=Glucose` -> 31 tests) and department filters (`Clinical Pathology` -> 471 tests).
- **Backend Pytest Suite:** All 28 tests in `tests/test_receptionist_e2e.py`, `tests/test_prompt04_corrections.py`, and `tests/test_prompt07_module13_and_fixes.py` passed in 2.45s.
- **Frontend Build & Types:** `tsc -b` compiled cleanly with 0 errors; `oxlint` passed with 0 errors.

### Prompt 07 Testing Status: Zero Browser Testing & Non-Browser Validation
Pursuant to the mandatory testing constraint in Prompt 07 Section 3:
- **Browser Automation (Playwright, Puppeteer, Selenium):** STRICTLY PROHIBITED and NOT PERFORMED.
- **Manual Browser Testing:** STRICTLY PROHIBITED and NOT PERFORMED.
- **Non-Browser Automated Validation Executed:**
  - `python -m py_compile`: 100% of modified backend, service, and Streamlit scripts compiled cleanly with exit code 0.
  - `tsc -b`: Clean TypeScript typecheck across all React 19 components and API client bindings with 0 errors.
  - `oxlint`: Clean linter run across 33 files with 0 errors.
  - `pytest tests`: 28 automated integration and unit tests passed in 2.45s.
  - `alembic upgrade head`: Applied migration `a7d834bc912e` cleanly.
  - Test Catalog Seed: 26 clinical test components seeded with physiological limits and reference ranges.

---

## 5. Canonical Documentation Architecture

All project documentation is consolidated into nine canonical markdown documents:

1. [`README.md`](README.md) - Quick start, system requirements, launch commands, environment variables, seed credentials.
2. [`project-context.md`](project-context.md) - Master state, tenant structure, data invariants, session logs, disposition table, and mandatory future prompt clause.
3. [`docs/SCOPE.md`](docs/SCOPE.md) - Functional scope, user roles, operational boundaries, and permissions matrix.
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Dual-stack architecture, directory layout, multi-tenancy, security headers, integer currency, ADL.
5. [`docs/DESIGN.md`](docs/DESIGN.md) - Visual tokens (60-30-10 palette: Platinum `#E8E7E3`, Moss `#525333`, Persian Orange `#CF8852`), typography, Bento layout, thermal printing.
6. [`docs/API.md`](docs/API.md) - Complete REST contract for all 12 modules, request/response models, query parameters, error responses.
7. [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) - Operational workflows (Intake -> Billing -> Assignment -> Sample -> Result -> Delivery -> Due Settlement -> Reprint) and UI/API Wiring Matrix.
8. [`docs/DATABASE.md`](docs/DATABASE.md) - Schema specification of 22 PostgreSQL tables (21 domain + alembic_version), relationships, indices, sequences.
9. [`docs/TESTING.md`](docs/TESTING.md) - Test strategy, automated E2E test suite setup, executed test scenarios, results, and reproduction commands.
