# MedScope DCMS — Testing & Verification Specification

## 1. Test Strategy & Philosophy

MedScope enforces zero-regression quality assurance across both backend services and frontend browser interfaces. In accordance with Prompt 04 directives, real automated browser verification using **Playwright in Chromium** is deployed directly in the sandbox, complementing the backend **pytest** integration suite.

Testing verifies all clinical and financial invariants under real runtime conditions (FastAPI on `127.0.0.1:8000`, Vite on `127.0.0.1:5173`, PostgreSQL 18 on `127.0.0.1:5432`).

---

## 2. Real-Browser Playwright E2E Suite (`frontend/e2e/receptionist_corrections.spec.ts`)

### Configuration & Runner
- **Runner:** `@playwright/test` v1.58.2
- **Config File:** `frontend/playwright.config.ts`
- **Target Browser:** Chromium (Installed to `C:\Users\zituser\AppData\Local\ms-playwright`)
- **Base URL:** `http://127.0.0.1:5173`
- **Execution Command:**
  ```powershell
  npm --prefix frontend run test:e2e
  ```

> **Status note (Prompt 10D):** the spec was updated in Prompt 10D (shared login helper, Dashboard landing, admin checked by signing in as admin, Save Draft → Finalize flow, the stale "role switcher" comment removed). It **creates records** (patients, doctors, referrers, invoices), so it was **not run** in Prompt 10D and must only be run against a disposable database.
>
> **Earlier status note (Prompt 10C):** the results below are the **historical Prompt 04 run**. This spec predates the Prompt 09 session login and was not updated afterwards. The 2026-11-12 audit reports it broken against the current UI. It also still has a stale comment at `frontend/e2e/receptionist_corrections.spec.ts:43` ("Toggle role to Admin via header role switcher"), although that dev switcher was removed in Prompt 09. The spec has not been changed or re-run in Prompt 10C. Treat it as **not currently passing**.

### Test Scenarios & Execution Outcomes (historical Prompt 04 run — 6 Test Suites covering all 14 items)

| # | Test Scenario Title | Items Covered | Verifications Performed | Duration | Result |
| :-: | :--- | :--- | :--- | :---: | :---: |
| **01** | `08 & 09: Inline global search and Ctrl+F keyboard shortcut` | **08, 09** | Exercises inline `#medscope-global-search`; verifies typing directly into header without modal; verifies anchored category dropdown; executes `Ctrl+F` shortcut and confirms focus. | 1.6s | **PASSED** |
| **02** | `02: Business Day close action permissions` | **02** | Confirms Receptionist role has no close action and displays disabled/restricted notice; switches to Admin role and verifies active `Close Business Day (Admin)` button. | 2.1s | **PASSED** |
| **03** | `01, 03, 04, 05, 06, 07: Complete Intake Workflow with Preview, Discounts, and Dual-Copy Print` | **01, 03, 04, 05, 06, 07** | Inline registers Doctor Tariqul as Prescriber and Referrer with write-only commission (no commission leakage); selects CBC & Lipid Profile (verifies added tests disappear from suggestions); enters 10% line discount and ৳100 master discount (verifies non-negative payable); confirms default ৳0 paid amount; clicks `Generate Preview` (verifies dual-copy modal opens in non-final mode); clicks `Back & Correct` (verifies all inputs retained 100%); re-opens preview and clicks `Save Invoice`; verifies permanent invoice assigned; verifies intake form resets to clean state with ৳0 paid. | 4.7s | **PASSED** |
| **04** | `10, 11, 14: Invoices list, reprint action, standard labels, and refund status` | **10, 11, 14** | Verifies standardized payment status labels (`Unpaid`, `Partial Due`, `Paid`); exercises status filter dropdown across all 6 user-friendly events (`All Payments`, `Paid`, `Unpaid`, `Partial Due`, `Partially Refunded`, `Fully Refunded`) masking PostgreSQL columns; verifies separate dynamic `Refund Status` column; clicks `Reprint` action and confirms `DualCopyInvoiceModal` opens with `DUPLICATE` watermark without page redirect. | 4.9s | **PASSED** |
| **05** | `12: Patient History nested invoice view preserves Patients route and context` | **12** | Navigates to `/patients`; searches "Fatima"; opens 4-tab history drawer; clicks "Invoices & Tests" tab; clicks "View" on invoice; verifies `DualCopyInvoiceModal` opens as nested overlay while route remains `/patients`; closes overlay and confirms user is back on `/patients` with history drawer and tab active. | 2.3s | **PASSED** |
| **06** | `Responsive Viewport: Mobile rendering and accessible layout` | **UI/UX** | Exercises 375x667 mobile viewport; verifies inline search, responsive header layout, mobile menu toggles, and accessible touch targets without horizontal layout breaking. | 2.4s | **PASSED** |

---

## 3. Backend Integration Test Suite (`tests/`)

### Test Modules (current):
1. `tests/test_receptionist_e2e.py` (Prompt 03 Core Scenarios)
2. `tests/test_prompt04_corrections.py` (Prompt 04 Specific Corrections)
3. `tests/test_prompt07_module13_and_fixes.py` (Module 13 flags and impossible limits)
4. `tests/test_prompt07c_fixes.py` (Prompt 07C safety fixes)
5. `tests/test_prompt09_auth.py` (Prompt 09 authentication and sessions; test 08 rewritten in 10D for one fixed role)
6. `tests/test_prompt10d_refunds.py` (**rewritten in Prompt 10E** for the new refund rule: the four worked cases A 600 + B 400 with paid 500/800/1000/0, repeated cancellations on one invoice, cancellation after an earlier disbursed refund, due turning into a refund, client amount ignored, urgent fee not refunded, technician visibility — 10 tests)
7. `tests/test_prompt10d_drafts.py` (draft has no side effects, finalize creates them, finalize not repeatable, edits after finalize blocked)
8. `tests/test_prompt10d_roles_permissions.py` (single-role login, no acting-role endpoint, dual role rejected by DB, LAB_TECH dashboard without money, defaults/access matrix (updated for the three Prompt 10E default changes), overrides enforced, escalation and self-change rules, last-admin protection, no money for LAB_TECH)
9. `tests/test_prompt10e_invoice_payment_samples.py` (Prompt 10E, 16 tests: `requires_sample` rules and the "None" normalization; USG/X-ray proceed without a sample; CBC still blocked before Sample Taken; age/gender round trip incl. months, Finalize requires both, draft allows them empty, invalid values 422; a payment on every channel and drawer totals per channel incl. ROCKET/OTHER; OTHER without a name rejected; CARD alias; refund channel rule with OTHER; urgent fee formula, with/without, minimum 100, preview (draft) = saved (finalized), client fee ignored)
10. `tests/test_prompt10e_rooms_roles_worklist.py` (Prompt 10E, 10 tests: catalog → room mapping and backfill; order routed to the room; two technicians of one room both see and work it, another room does not; empty room → UNASSIGNED visible to Admin/Owner, released when a technician joins; reassign before COMPLETED, refused after, not allowed for technician/front desk; Assign Tests stores room names not ids; LAB_TECH needs a room, DOCTOR has none; LAB_TECH own profile; CASHIER/RECEPTIONIST blocked from release with due, Admin needs a reason; DOCTOR defaults, queue, completion and money restriction incl. overrides; saved result returns the preview data and appears under READY)
11. `tests/test_prompt10f_owner_findings.py` (**Prompt 10F, 12 tests**: F1 — Assigned Tests payload is money-free with rooms/technicians/UNASSIGNED, RECEPTIONIST view only + reassign 403, LAB_TECH/DOCTOR 403 on the view, ADMIN and OWNER reassign before COMPLETED with audit + history, 409 after COMPLETED and for Not Performed, status/room filters, 400 on an unknown status; F2 — a saved DRAFT is previewable at once, marked draft, not Ready, room access enforced, 404 without a result; F3 — ENTERED is Ready without operational Complete (BOTH_SIGNATURES stays IN_PROGRESS), DRAFT/cancelled/rejected/AWAITING_DOCTOR are not Ready, tile count = Ready list = sidebar list (one shared definition), room filter and search, no `report_versions` row, preview money-free; money fields only for money roles (a receptionist without `payment.view` gets no due; technicians/doctors get 403 on `/reports/ready`); F4 — helper rules (NULL/empty = required, markers = not, imaging via room/department/template, doctor-read tissue test NOT imaging), exactly one definition in the backend, every gate blocked before Sample Taken (result template 400, save DRAFT/ENTERED 409, Complete 400, culture stage 400, outsourced SENT 400) then allowed after with the line locking at collection, explicit markers and imaging proceed, a legacy completed-without-sample order is untouched and labelled; F5 — full cycle: empty room → deactivate demotes only the assigned-only order (audit `ORDER_UNASSIGNED_ROOM_EMPTY` + history, same transaction, verified by rollback), progress states (draft result, IN_PROGRESS, AWAITING_DOCTOR, COMPLETED) untouched, Admin/Owner see it, a joining technician releases exactly it; room change and role change demote too)
- Existing tests updated for Prompt 10E: invoice payloads send `age_value`/`gender` (Finalize requires them); `test_04` in `test_receptionist_e2e.py` expects the urgent fee on a 100%-discounted urgent line; a 10D test creating a LAB_TECH now gives it a room.
- Fixtures and the main-DB safety guard live in `tests/conftest.py` (guard unchanged). Prompt 10D: fixtures use single-role users (`cashier_fatima`, `owner_tariq` added) and clear per-user overrides left by earlier runs. The latest real run (Prompt 10F, 2026-11-13) is **122 passed** against `medscope_test` (110 from 10E + 12 new).
- **Prompt 10F updates to existing tests:** `test_prompt10e_invoice_payment_samples.py::test_requires_sample_helper_rules` now encodes the 10F rule (NULL/empty = sample required; only explicit markers mean no sample) and `test_none_strings_were_normalized_by_the_migration` ignores the `P10F_*` probe tests that carry explicit markers on purpose. The old sample-gate messages are kept as a substring of the new plain messages, so `test_prompt07c_fixes.py` still passes.
- **Test DB note (Prompt 10E):** `medscope_test` kept LAB_TECH users without a room (created by earlier test runs; soft-deleted in Prompt 11, see §14.2), so migration `f3c9a1d7e5b2` did not add the CHECK `chk_staff_lab_tech_has_section` there; the user service enforces the rule. Room tests make the Ultrasonography room empty in the test DB only.
- **Frontend tile mapping:** the frontend has no unit-test runner. `frontend/src/features/worklist/worklistTiles.ts` is pure; its tile → filter mapping was checked with a Node 24 script (type stripping) outside the repo: every status tile applies its filter, highlights itself and clears on a second click; Urgent toggles independently; counts use money-free summary keys — all assertions passed.

### Baseline Execution Command:
```powershell
python -m pytest tests/
```

---

## 4. Prompt 06 Testing Restriction & Static Regression Review

### Mandatory Testing Restriction: NOT PERFORMED
In strict adherence to the explicit instruction in Prompt 06 Section 3:
- **Pytest or automated backend tests:** NOT executed.
- **Playwright, Cypress, Selenium, or browser automation:** NOT executed.
- **Unit, integration, API, E2E, regression, or manual tests:** NOT executed.
- **Starting a testing server or browser session:** NOT initiated.
- **Creating test data or altering operational records for testing:** NOT performed.
- **Running test suites, build commands, typechecks, or migrations:** NOT executed.
- **No claim is made that any test has passed.**

### Static Regression Review Conducted:
A strict static code and architecture review was conducted across all modified files without executing test runners:
1. **Invoice Intake & Line Locks:** Verified that `InvoiceLine.is_locked` is set upon specimen collection, or (Prompt 12) at result completion for no-sample/imaging tests, and checked that `refund_service.py` prevents ordinary pre-sample cancellation when locked.
2. **Worklist State Transitions:** Verified that `TechnicianWorklistPage.tsx` and `worklist_service.py` require specimen collection prior to offering completion for sample-based tests, resolving the Prompt 05 worklist bug.
3. **Financial Isolation:** Confirmed that `TechnicianWorklistItemResponse`, `BarcodeLabelResponse`, and worklist endpoints omit all financial fields (gross, net, paid, due, discounts, commissions, reagent costs).
4. **Append-Only History:** Verified that `TestOrderEvent` maintains an immutable audit log across sample collection, rejection, patient follow-up, culture stages, and referral lab dispatch.
5. **Department-Specific Extensions:** Confirmed dedicated branches for Imaging (`PERFORMED`), Culture (`INCUBATING`, `PRELIMINARY`, `FINAL`), and Outside Labs (`OUTSOURCED_SENT`, `OUTSOURCED_RECEIVED`).

---

## 5. Prompt 07 Testing Policy & Non-Browser Engineering Validation

### Zero Browser Testing Declaration
In strict adherence to Prompt 07 Section 3:
- **Browser Automation (Playwright, Selenium, Puppeteer, Cypress):** STRICTLY PROHIBITED and NOT PERFORMED.
- **Manual Browser Verification:** STRICTLY PROHIBITED and NOT PERFORMED.
- **Starting a Browser Session or Headless Browser:** NOT PERFORMED.
- **Declaration:** No browser-based automated or manual testing was executed. All assertions of system stability are derived exclusively from non-browser automated engineering checks.

### Executed Non-Browser Engineering Validation Suite
1. **Python Syntax & Bytecode Compilation:**
   ```powershell
   python -m py_compile "DCMS V1.py" accounting.py backend/app/main.py backend/app/services/result_service.py backend/app/services/refund_service.py backend/app/services/worklist_service.py backend/app/api/v1/endpoints/results.py backend/app/api/v1/endpoints/refunds.py backend/app/api/v1/endpoints/invoices.py
   ```
   *Outcome:* **PASSED** (exit code 0; zero compilation errors across monolith and modular backend).

2. **TypeScript Strict Typecheck:**
   ```powershell
   cd frontend; .\node_modules\.bin\tsc.cmd -b
   ```
   *Outcome:* **PASSED** (exit code 0; zero type errors across all React 19 components, API clients, and schemas).

3. **Frontend Code Quality & Linter (`oxlint`):**
   ```powershell
   cd frontend; npm run lint
   ```
   *Outcome:* **PASSED** (exit code 0; 0 errors across 33 files with 116 rules).

4. **Automated Backend Pytest Suite:**
   ```powershell
   python -m pytest tests
   ```
   *Outcome:* **28 PASSED in 2.45s**
   - `tests/test_prompt04_corrections.py`: 6 tests passed.
   - `tests/test_receptionist_e2e.py`: 14 tests passed.
   - `tests/test_prompt07_module13_and_fixes.py`: 8 tests passed:
     - `test_compute_flag_normal_range` (NORMAL calculation within normal reference interval)
     - `test_compute_flag_low_and_high` (LOW and HIGH flag detection)
     - `test_compute_flag_critical_bounds` (CRITICAL flag detection on severe low/high values)
     - `test_compute_flag_safe_none_fallback` (Safe None fallback when limits are missing or incomplete; never silently classifies as NORMAL)
     - `test_validate_impossible_limits_valid` (Physiologically viable numeric values pass cleanly)
     - `test_validate_impossible_limits_high_rejection` (Absurd high value e.g. Hemoglobin 150 rejected with HTTP 400)
     - `test_validate_impossible_limits_low_rejection` (Absurd low value rejected with HTTP 400)
     - `test_non_numeric_text` (Text-based qualitative results e.g. "Trace" handled without numeric conversion errors)

5. **PostgreSQL Database Schema & Migration (`a7d834bc912e`):**
   ```powershell
   python -m alembic -c backend/alembic.ini upgrade head
   ```
   *Outcome:* **PASSED** (Alembic revision `a7d834bc912e` verified in PostgreSQL 18; tables `test_components`, `results`, `result_items` and D15 columns active).

---

## 6. Prompt 07C Testing & Verification (Safety and Correctness Fixes)

### Mandatory Testing Policy: Zero Browser Testing
In strict adherence to Prompt 07C Section 2:
- **Browser Automation (Playwright, Puppeteer, Cypress, Selenium):** STRICTLY PROHIBITED and NOT PERFORMED.
- **Manual Browser Testing:** STRICTLY PROHIBITED and NOT PERFORMED.
- All verification was conducted through automated backend test suites, compiler checks, schema synchronization verifications, and frontend build validations.

### Dual-Mode Test Suite Reliability (Fix 7)
The test suite now natively supports dual-mode execution:
1. **In-Process Mode (No Live Server):** The `client` fixture automatically falls back to Starlette/FastAPI's in-process `TestClient` against `backend.app.main:app`. No background server process is required.
2. **Live-Server Mode (Background Server Active):** When a live uvicorn server is running on `http://127.0.0.1:8000`, the fixture connects via HTTP client.

### Automated Test Suite Execution Results (35 Tests Total)

#### 1. In-Process Execution (No Live Server Running):
```powershell
python -m pytest tests -v
```
- **Outcome:** **35 PASSED** in 5.65s (0 failures, 8 warnings).
  - `tests/test_prompt04_corrections.py`: 6 passed
  - `tests/test_prompt07_module13_and_fixes.py`: 8 passed
  - `tests/test_receptionist_e2e.py`: 14 passed
  - `tests/test_prompt07c_fixes.py`: 7 passed:
    - `test_fix1_original_payment_channel_enforcement` (disbursing refund through unrecorded payment channel rejected with 400; non-cash reference enforced; per-channel balance limit checked)
    - `test_fix2_segregation_of_duties_self_approval_blocked` (self-approval rejected with 403; audit row `REFUND_SELF_APPROVAL_BLOCKED` written)
    - `test_fix3_culture_stage_final_does_not_autocomplete` (moving culture stage to `FINAL` leaves order in `IN_PROGRESS`; completing order requires `FINAL` stage)
    - `test_fix4_draft_does_not_advance_status` (saving result `DRAFT` does not advance order status)
    - `test_fix4_sample_uncollected_result_save_rejected` (sample-based test rejects result saving before specimen collection with 409)
    - `test_fix4_completed_order_resave_rejected` (modifying results on an already `COMPLETED` order rejected with 409)
    - `test_fix5_technician_financial_isolation` (D15 refund endpoint returns `D15RefundClinicalResponse` omitting amount; event timeline redacts monetary amounts for `LAB_TECH`)

#### 2. Live Server Execution (`uvicorn backend.app.main:app --port 8000`):
```powershell
python -m pytest tests -v
```
- **Outcome:** **35 PASSED** in 3.49s (0 failures, 5 warnings).

### Non-Browser Verification Commands & Observed Results
1. **Python Bytecode Compilation:**
   ```powershell
   python -m py_compile backend/app/models/result.py backend/app/services/refund_service.py backend/app/services/worklist_service.py backend/app/services/result_service.py backend/app/schemas/refund.py backend/app/api/v1/endpoints/results.py tests/test_prompt07c_fixes.py
   ```
   *Result:* Code 0, clean compilation.
2. **Alembic ORM Model Synchronization (Fix 6):**
   ```powershell
   python -m alembic -c backend/alembic.ini check
   python -m alembic -c backend/alembic.ini heads
   python -m alembic -c backend/alembic.ini current
   ```
   *Result:* Code 0, `No new upgrade operations detected`. Single head `a7d834bc912e (head)`.
3. **Frontend TypeScript Strict Typecheck:**
   ```powershell
   cd frontend; .\node_modules\.bin\tsc.cmd -b
   ```
   *Result:* Code 0, zero type errors.
4. **Frontend Code Linter (`oxlint`):**
   ```powershell
   cd frontend; npm run lint
   ```
   *Result:* Code 0, zero errors across 33 files.
5. **Frontend Production Build:**
   ```powershell
   cd frontend; npm run build
   ```
   *Result:* Code 0, Vite production bundle built cleanly (`dist/index.html`, `dist/assets/`).

---

## 7. Prompt 08 Testing & Verification (Modal Fix, Test DB Isolation & Record Identification)

### 7.1 Part A: Limited Browser Testing Exception & Modal Navigation Fix
- **Scope & Directive:** In strict accordance with Prompt 08 Section A3, a narrow exception was authorized to use Playwright (Chromium) exclusively for reproducing and verifying the modal/tab navigation bug.
- **Rules Enforced:**
  1. **Strictly Read-Only:** Tests only open tabs and modals; zero creation, modification, or deletion of data.
  2. **Login helper:** Prompt 10D replaced the stale `selectDevRole` with the shared helper `frontend/e2e/support/auth.ts` (`loginAs` / `openAs`). It signs in through the real form (`login-username` / `login-password` test ids), waits for `/dashboard`, then opens the page under test. The password comes from the environment variable `MEDSCOPE_E2E_PASSWORD`; it is never stored in code.
  3. **No Claim of Product Acceptance:** Automated browser specs do not claim manual acceptance; personal acceptance is reserved for the product owner.
- **Prompt 10D:** selectors fixed and helper replaced (see item 2). Run on 2026-11-13 without `MEDSCOPE_E2E_PASSWORD`: **0 passed, 6 failed**, each failing immediately with "MEDSCOPE_E2E_PASSWORD is not set" before any login attempt. A real pass/fail run needs the owner to set that variable (see §11).
- **Earlier status (Prompt 10C): FAILING — selector update pending.** In the 2026-11-12 audit run, **0 passed, 6 failed**. The login helper fills `#username` / `#password`, but the current login page (`frontend/src/features/auth/LoginPage.tsx`) uses `#user` / `#pass` (`data-testid` `login-username` / `login-password`). Fixing the spec is a separate coding task, not done in Prompt 10C. The per-spec PASSED results below are the **historical Prompt 08 run** only.
- **Regression Suite:** `frontend/e2e/test_modal_regression.spec.ts` (6 specs; historical Prompt 08 results):
  - `A1: Invoices detail modal preserves /invoices URL and active tab` (PASSED, 2.3s)
  - `A2: Invoices -> Patient History opens in-place without switching background to Patients` (PASSED, 3.5s)
  - `A3: Patients page history drawer preserves /patients URL and tab state` (PASSED, 2.3s)
  - `A4: Dues settlement modal preserves /dues URL and tab state` (PASSED, 2.2s)
  - `A5: Ready Reports printable preview modal preserves /reports URL and tab state` (PASSED, 2.0s)
  - `A6: Technician Worklist modals preserve /worklist URL and tab state` (PASSED, 1.2s)
- **Execution Command:**
  ```powershell
  cd frontend; npx playwright test e2e/test_modal_regression.spec.ts
  ```
  *Outcome (historical, Prompt 08):* 6 passed in 14.4s. *Outcome (audit 2026-11-12):* **0 passed, 6 failed** (stale login selectors, see above).

### 7.2 Part B: Test Database Isolation & Hard Safety Guard
- **Test Database URL:** Selected via `TEST_DATABASE_URL` (defaults to `postgresql+psycopg://medscope_app:1234@127.0.0.1:5432/medscope_test`).
- **Hard Safety Guard:** Implemented in `tests/conftest.py` (`enforce_safety_guard`). If `TEST_DATABASE_URL` equals or resolves to the main/production database (`medscope_dcms`), pytest immediately aborts with `pytest.UsageError` (Exit code 4).
- **Alembic Migration Chain:** Verified running from `<base>` to `a7d834bc912e (head)` on empty test database before tests execute.
- **Deterministic Seed Fixture:** `setup_test_database` seeds tenant `center-seba-01`, staff, 25 diagnostic tests, test destinations, referrers, and CBC components.
- **In-Process Execution:** Completely removed live-server port 8000 probing. All tests execute strictly in-process using FastAPI `TestClient` with `app.dependency_overrides[get_db]`. Pytest cannot write to the main database.
- **Execution Command:**
  ```powershell
  python -m pytest
  ```
  *Outcome:* **35 PASSED** in 2.99s against `medscope_test`.

### 7.3 Part C: Read-Only Test Record Identification
- **Safety Backup:** `backups/medscope_dcms_pre_prompt08.dump` (191,737 bytes, git-ignored).
- **Inspection Report:** `report/TEST_RECORD_CANDIDATES.md`.
- **Integrity Guarantee:** Zero writes to `medscope_dcms`. Exact breakdown: 106 test patients, 93 test referrers, 180 test invoices, 189 test lines, 146 test payments, 76 test refund requests, 189 test orders, 121 test events, 22 test samples, 3 test results, 46 test audit logs, 50 test reprint logs.

---

## 8. Prompt 09 Testing & Verification (Role-Based Authentication & Session Transport)

### 8.1 Mandatory Testing Policy & Zero Browser Testing Directive
In strict adherence to the explicit constraints of Prompt 09:
- **Zero Browser Testing:** Browser testing is strictly prohibited. No Playwright, Cypress, Puppeteer, Selenium, or manual browser testing was initiated. The limited browser testing exception authorized in Prompt 08 expired upon completion of Prompt 08.
- **Main Database Invariant:** Automated test runs executed strictly against `medscope_test`. The hard safety guard in `tests/conftest.py` prevented test runs against `medscope_dcms`. Main database records remained untouched by the Prompt 09 test runs (invoice count unchanged during that session; dev/QA data, counts vary).

### 8.2 Test Infrastructure Upgrades (`tests/conftest.py`)
- **Seeded Passwords & Roles:** Pre-computed Argon2id password hash (`$argon2id$v=19$m=65536,t=3,p=4$6vA...`) for test password `Password123!`. Seeded `staff_roles` table for all staff (including multi-role mapping for Admin/Owner).
- **Session Fixtures:** Deterministic server-side test sessions created in `auth_sessions` during database fixture setup, yielding verified session tokens for all roles (`receptionist_headers`, `admin_headers`, `cashier_headers`, `lab_tech_headers`, `owner_headers`).
- **PostgreSQL Sequence Synchronization:** Added automated sequence synchronization (`staff_id_seq`, `staff_roles_id_seq`) preventing primary key collision errors during dynamic user creation tests.
- **Existing Test Suite Modernization:** Updated `test_receptionist_e2e.py`, `test_prompt04_corrections.py`, and `test_prompt07c_fixes.py` to use real session headers instead of spoofed headers.

### 8.3 Dedicated Authentication Test Suite (`tests/test_prompt09_auth.py` — 10 Scenarios)

| # | Test Function | Scenario Tested | Outcome |
| :-: | :--- | :--- | :---: |
| **01** | `test_login_successful_and_cookie_issuance` | Valid credentials issue `medscope_session` HttpOnly cookie, return user profile, and seed active business day. | **PASSED** |
| **02** | `test_login_invalid_password_and_generic_error` | Bad password returns HTTP 401 with generic error message (`"Invalid username or password"`). | **PASSED** |
| **03** | `test_account_lockout_after_five_failed_attempts` | 5 consecutive bad passwords lock account (`locked_at` set); subsequent attempts return HTTP 423 Locked. | **PASSED** |
| **04** | `test_authenticated_get_me_and_session_resolution` | `GET /auth/me` resolves session actor and updates idle sliding window. | **PASSED** |
| **05** | `test_role_based_route_protection` | Role-based RBAC: Receptionist rejected from closing day (HTTP 403), Admin permitted (HTTP 200). | **PASSED** |
| **06** | `test_multi_role_switching` | Staff switches acting role; invalid role assignment is rejected with HTTP 403. | **PASSED** |
| **07** | `test_session_revocation_on_logout` | `POST /auth/logout` marks session revoked on server; subsequent calls return HTTP 401. | **PASSED** |
| **08** | `test_csrf_header_protection_on_mutating_requests` | Mutating POST request using cookie without `X-Requested-With: XMLHttpRequest` is rejected with HTTP 403 CSRF error. | **PASSED** |
| **09** | `test_self_service_password_change` | User changes password; old sessions revoked; validates login with new password. | **PASSED** |
| **10** | `test_admin_password_reset_and_unlock` | Admin unlocks locked account and resets user password; verifies immediate unlocking. | **PASSED** |

### 8.4 Full Test Suite Execution Summary
- **Execution Command:**
  ```powershell
  python -m pytest
  ```
- **Results:**
  - `tests/test_prompt09_auth.py`: 10 passed
  - `tests/test_prompt07c_fixes.py`: 15 passed
  - `tests/test_prompt04_corrections.py`: 6 passed
  - `tests/test_receptionist_e2e.py`: 14 passed
  - **Total:** **45 passed in 4.19s** (100% pass rate).

### 8.5 Static Verification & Compilation
- **Frontend Typecheck (`npx tsc -b`):** 0 errors.
- **Frontend Linter (`npx oxlint`):** 0 errors across 36 files.
- **Frontend Production Build (`npm run build`):** Vite bundle completed in 581ms (`dist/index.html`, `dist/assets/`).
- **Python Bytecode Compilation (`py_compile`):** Clean exit code 0 across all backend and test files.

---

## 9. Prompt 10 Testing & Verification (Branded Landing Page & Animated Login UI)

### 9.1 Narrow Browser Exception (Prompt 10 Screenshot & 390px Overflow Verification)
- **Scope & Directive:** In accordance with Prompt 10 Section 4, a narrow exception was authorized to use Playwright (Chromium) **only to take screenshots** of `/` and `/login` (desktop 1360x900 and mobile 390x844) and to verify horizontal overflow at 390px.
- **Rules Enforced:**
  - Strictly read-only; no sign-in actions, no session tampering, and zero data creation/mutation.
  - No automated browser acceptance tests claimed; product owner reviews the design personally.
- **Automated Runner:** `frontend/scripts/capture_screenshots.mjs` executing Chromium in headless mode.
- **Screenshots Stored:**
  1. `report/screenshots/landing-desktop.png`: 1360x900 viewport of public landing page (`/`).
  2. `report/screenshots/landing-mobile.png`: 390x844 viewport of landing page (`/`).
  3. `report/screenshots/login-desktop.png`: 1360x900 viewport of animated login page (`/login`).
  4. `report/screenshots/login-mobile.png`: 390x844 viewport of login page (`/login`).
  5. `report/screenshots/404-desktop.png`: 1360x900 viewport of branded 404 page (`/unknown-path-404`).
- **390px Viewport Horizontal Overflow Check:**
  - `Landing Page Mobile (390px)`: `scrollWidth = 390`, `clientWidth = 390`, `hasOverflow = false`.
  - `Login Page Mobile (390px)`: `scrollWidth = 390`, `clientWidth = 390`, `hasOverflow = false`.
  - Both viewports confirm that primary actions ("Sign in") are visible above the fold without horizontal clipping or scrollbar generation.

### 9.2 Non-Browser Verification & Code Quality
- **Backend Pytest Suite:**
  - Execution Command: `python -m pytest`
  - Result: **45 passed in 4.43s** (100% pass rate).
  - Target Database: Isolated `medscope_test`. Main database `medscope_dcms` untouched.
- **Frontend TypeScript Compilation:**
  - Execution Command: `npm --prefix frontend run build` (`tsc -b && vite build`)
  - Result: Code 0, Vite production bundle generated cleanly in 670ms.
- **Frontend Linter:**
  - Execution Command: `npm --prefix frontend run lint` (`oxlint`)
  - Result: **0 errors** across 39 files.
- **Alembic Schema Status:**
  - Single head confirmed: `b9e41d82f05a (head)`.
  - `alembic check` reports `No new upgrade operations detected.` Zero database migrations introduced.

### 9.3 Motion Verification, Marquee Strip Height, and Account Credential Verification
- **Continuous Motion Sampling:** Verified ECG heartbeat stroke-dashoffset transitions (`720px` down to `9px` on Landing, `900px` down to `26px` on Login) and marquee linear translation (`matrix(1, 0, 0, 1, -20px, 0)` down to `-78px`) across both standard and forced `reducedMotion: 'reduce'` operating contexts.
- **Marquee Height Metric:** Measured rendered section height at **70px** (`containerHeight = 68px`, `sectionHeight = 70px`) with zero horizontal overflow at 390px.
- **Role Credentials Verification:** Tested all four staff accounts via HTTP API `POST /api/v1/auth/login` with password `12345`:
  - `reception_fatima`: HTTP 200 OK, default workbench `/invoices`, acting role `RECEPTIONIST`, multi-role switchable to `CASHIER`.
  - `admin_tariq`: HTTP 200 OK, default workbench `/dashboard`, acting role `ADMIN`, multi-role switchable to `OWNER`.
  - `tech_kamal`: HTTP 200 OK, default workbench `/worklist`, acting role `LAB_TECH`.
  - `tech_nasrin`: HTTP 200 OK, default workbench `/worklist`, acting role `LAB_TECH`.

---

## 10. Test Record Elimination & Database Integrity Verification (Prompt 10B)

### 10.1 Status (corrected in Prompt 10C)
- **What Prompt 10B did:** delivered the standalone SQL script `backend/scripts/sql/cleanup_test_data.sql` for the owner to run in the **pgAdmin Query Tool**. During the Prompt 10B session itself, no `DELETE`/`UPDATE`/`INSERT` was committed against `medscope_dcms` (read-only queries and in-transaction dry runs only).
- **What happened afterwards:** the owner **executed and committed** the cleanup on the main dev DB `medscope_dcms` on **2026-11-11**. The `audit_logs` row with action `TEST_DATA_CLEANUP` (id 826) records it. The docs no longer describe the script as "dry-run only" or "zero mutations".
- **Nature:** development/testing utility only. It is not part of the schema, not part of the Alembic chain, and not a product feature. The file is git-ignored (`*.sql`) and exists only locally.
- **On-disk vs executed:** the on-disk file currently ends with `ROLLBACK;` (with `-- COMMIT;` commented out), so it cannot be shown to be byte-for-byte what was executed.

### 10.2 Dry-Run Validation (historical, Prompt 10B session)
The delivered SQL script was validated by executing an in-transaction dry run with explicit notice handling. The dry run verified:
- Clean compilation and execution across PostgreSQL 18.
- Exactly 17 target tables processed in topological dependency order without a single foreign key violation.
- All 13 post-check integrity assertions passed with 0 orphaned foreign keys.
- Kept-entity assertions matched the protected seed + manual-QA set at that time (dev/QA data; counts vary).
- Reversion verified via default trailing `ROLLBACK;`.

### 10.3 Verification Database Creation Boundary
Section 5 specifies: *"Create a scratch database from a fresh pg_dump of the main database... If the database user cannot create databases, report Blocked for this verification and still deliver the script, saying clearly that it was not rehearsed."*
- **Attempted Operation:** `CREATE DATABASE medscope_cleanup_rehearsal` on `127.0.0.1:5432` under user `medscope_app`.
- **Database System Response:** `psycopg.errors.InsufficientPrivilege: permission denied to create database`.
- **Status:** **Blocked** (The configured PostgreSQL application user lacks `CREATEDB` privileges on the server).
- **Deliverable Status:** The script was delivered verified only via transactional dry-run simulation and static catalog validation. It was not rehearsed on a scratch copy.

---

## 11. Verification Status after Prompt 10E (2026-11-13; superseded by §13, Prompt 10F)

| Check | Result | Source |
| :--- | :--- | :--- |
| `python -m pytest` (against `medscope_test`) | **110 passed**, 0 failed | Prompt 10E run |
| `tsc -b` | exit 0 | Prompt 10E run |
| `oxlint` (`npm run lint`) | exit 0, 0 errors, 120 warning lines (unchanged baseline) | Prompt 10E run |
| `vite build` | built (one >500 kB chunk warning, as before) | Prompt 10E run |
| `alembic heads` / `current` | single head `f3c9a1d7e5b2` (dev DB at head) | Prompt 10E run |
| `alembic check` | `No new upgrade operations detected.` | Prompt 10E run |
| OpenAPI | 81 paths / 94 operations | Prompt 10E run |
| `frontend/e2e/test_modal_regression.spec.ts` | Updated in 10E (room label + tile filter checks in A6, OTHER channel field in A4; all read-only); **not run**: `MEDSCOPE_E2E_PASSWORD` is not set in the agent environment | Prompt 10E |
| `frontend/e2e/receptionist_corrections.spec.ts` | Updated in 10E (visit age/gender before Finalize, channel list incl. OTHER name field); **not run** (it creates records) | Prompt 10E |
| `npx playwright test --list` | 12 tests in 2 files (specs parse) | Prompt 10E |

To run the read-only modal spec (PowerShell, servers on 5173/8000): `$env:MEDSCOPE_E2E_PASSWORD = '<dev password>'; cd frontend; npx playwright test e2e/test_modal_regression.spec.ts`.

---

## 12. Pre-Go-Live Cleanup List (for later — not to be acted on now)

The owner recorded these as required **before go-live**. None of them has been done yet. Only file paths are listed here, never values.

1. **Remove hard-coded credentials and connection strings** from code, tests, docs, reports and env templates. Known locations (from the 2026-11-12 audit and the Prompt 10C sweep):
   - `tests/conftest.py`: hard-coded fallback connection string to the main DB, plus a hard-coded test password constant.
   - `tests/test_prompt09_auth.py`: hard-coded test passwords.
   - `frontend/e2e/test_modal_regression.spec.ts`: **done in Prompt 10D** (password removed; now read from `MEDSCOPE_E2E_PASSWORD`).
   - `README.md` (Environment Configuration block): concrete DB password in example URLs.
   - `docs/TESTING.md` §7.2 (default `TEST_DATABASE_URL`) and §8.2/§9.3: concrete passwords.
   - `project-context.md` (Prompt 10 section): a concrete staff password.
   - `.env.example` and `backend/.env.example`: concrete-looking values instead of placeholders.
   - Historical reports under `report/` (e.g. Prompt 08 and Prompt 10B reports) that contain connection strings.
2. **Rotate all development passwords** (DB user and staff accounts), since current values are in git history.
3. **Remove the main-DB fallback** in `tests/conftest.py`. Tests must require an explicit `TEST_DATABASE_URL` and never derive a main-DB URL.
4. **Replace hard-coded test passwords** with values from environment variables or fixtures generated at runtime.

---

## 13. Prompt 10F Verification & Owner Acceptance (2026-11-13)

### 13.1 Non-browser evidence (real results)

| Check | Result |
| :--- | :--- |
| `python -m pytest` (against `medscope_test` only; guard unchanged) | **122 passed**, 0 failed (baseline before 10F: 110 passed) |
| `tsc -b` | exit 0 |
| `oxlint` (`npm run lint`) | exit 0, **0 errors**, 120 warning lines (unchanged baseline) |
| `vite build` (output to a scratch folder) | built (the usual >500 kB chunk warning) |
| `alembic heads` | `f3c9a1d7e5b2 (head)` — single head, **no schema change in 10F** |
| `alembic current` (dev DB) | `f3c9a1d7e5b2 (head)` |
| `alembic check` | `No new upgrade operations detected.` |
| OpenAPI | **85 paths / 98 operations** (4 new read-only GETs) |
| `npx playwright test --list` | 12 tests in 2 files (specs parse) |
| Playwright run | **Not run** (browser testing is banned for the agent and `MEDSCOPE_E2E_PASSWORD` is not set); spec A5 updated for the new `/reports` tabs |
| Dev DB | read-only inspection only (`SET TRANSACTION READ ONLY`); nothing written, no backup needed |

### 13.2 Data-readiness note (owner decision A5)

Until the owner fills `tests.sample_type` in the catalog, **every non-imaging test with a NULL or empty `sample_type` requires a Sample Taken** before results, completion, culture stages or outsourced dispatch. This is the safe direction: nothing can skip the sample lock, but technicians must record Sample Taken for 1,199 catalog tests (dev DB count) even where no specimen is really drawn. Entering an explicit `None` / `N/A` / `NA` / `No sample` in `sample_type` lifts the requirement per test; any other value names the specimen. 51 tests count as imaging (Ultrasonography room, USG/X-ray/radiology/imaging departments, narrative template) and never need a sample. **Read-only dev-DB effect check:** 29 of 38 open orders now wait for Sample Taken; 1 completed order (id 269, Ascitic Fluid for Cytology, completed without a sample under the 10E rule) is left untouched and shows "Completed without sample".

### 13.3 Manual acceptance checklist for the owner (one click path, one expected result each)

| # | Item | Click path | Expected result |
| :-: | :--- | :--- | :--- |
| F1a | Assigned view, view only | Log in as **Receptionist** → Assign Tests → tab **Assigned Tests** | Every order with invoice, patient, test, room, technician name(s) or UNASSIGNED, status, urgent, created time; filters and search work; **no Reassign button, no money anywhere** |
| F1b | Reassign | Log in as **Admin** or **Owner** → Assign Tests → Assigned Tests → **Reassign Room** on a non-completed row → pick a room → Move Order | The row shows the new room without a page reload; the receiving room's My Work shows the order |
| F1c | Completed locked | Same list, a COMPLETED row | No Reassign button; a grey "Completed" lock is shown instead |
| F2a | Preview after save | Log in as a **technician** → My Work → Enter Results → **Save Draft** | A "Result saved as DRAFT…" strip with **Preview Report** appears at once; the row shows Preview Report; the preview opens with a dashed amber **"DRAFT, not a final report"** banner |
| F2b | Preview after submit | Same, but **Submit Results** | Preview still available (strip + row); banner replaced by a "Result submitted and Ready" note; no print button |
| F3a | Lab Ready tile | My Work → click the **Ready Reports** tile right after Submit | The grid filters to exactly the Ready orders; the tile count equals the rows; clicking the tile again clears the filter |
| F3b | Sidebar Ready Reports | Log in as **Receptionist/Admin/Owner** → sidebar **Ready Reports** | The **Ready Results** tab lists the just-submitted result (all rooms) with room, entered time, a due badge (money roles) and **Preview Report**; the empty text no longer claims nothing is issued |
| F4a | Sample required | As a technician, pick a lab test whose catalog `sample_type` is empty (e.g. most Biochemistry tests) → try **Enter Results** or **Complete** before Sample Taken | Refused with "Take the sample before entering results…"; after **Sample Taken** both work and the invoice line locks |
| F4b | No-sample marker | Pick a test whose `sample_type` you set to `None` (or an USG/X-ray) | Results and Complete work without a sample; the invoice line shows "No sample needed" (or the imaging states) |
| F5 | Empty room | As Admin: User Management → deactivate a room's only technician → Assign Tests | That room's not-yet-started orders show **UNASSIGNED** (orders already in progress keep their state); re-activating or adding a technician puts them back to ASSIGNED |

### 13.4 Known not done (unchanged by 10F)

- Module 15 (corrections), signature image upload, PDF / print, QR and real SMS are not built (Module 14 itself is built, Prompt 16).
- A reject / send-back path for the doctor sign-off; `performing_role` normalization; rooms for the 671 unmapped tests; the urgent-fee floor/cap question (A1); master-discount behaviour (A3); the reduced-motion "Pause animations" control; the pre-go-live credential cleanup (§12).
- Playwright specs were not run (no password in the agent environment; browser testing banned for the agent).

---

## 14. Prompt 11 Verification & Owner Acceptance (2026-11-13)

### 14.1 Non-browser evidence (real results)

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only; guard unchanged) | **135 passed**, 0 failed (122 before Prompt 11; +13 in `tests/test_prompt11_soft_delete.py`) |
| `alembic heads` / `alembic current` (dev DB) | `a4d8c2e6f1b7 (head)` single head |
| `alembic check` | "No new upgrade operations detected." |
| `tsc -b` | 0 errors |
| `oxlint` | 0 errors (warnings only, baseline style) |
| `vite build` | succeeds |
| OpenAPI | 96 paths / 110 operations; 38 permission keys (21 money) |
| Confirm dialog | No frontend unit-test framework in the project; the reason-gating rule (`isConfirmReady`) was verified by code review only (non-browser). |
| Browser / Playwright | **Not run** (agent may not test in a browser). Owner does acceptance below. |

### 14.2 Test DB cleanup
The leftover `LAB_TECH` test users in `medscope_test` (98 accumulated by earlier test runs, not 5) were soft-deleted with the new `delete_user` service (audited, `medscope_test` only, database-name asserted); two seeded technicians remain. New pytest runs add fresh test users again; `medscope_dcms` was not touched.

### 14.3 Manual acceptance checklist for the owner (one click path, one expected result each)

| # | Click path | Expected result |
|---|---|---|
| P11-1 | Catalog & Deleted → Tests → Delete a test (empty reason, then a real reason) | Confirm stays disabled until a reason is typed; then the test disappears from New Invoice search |
| P11-2 | Open an old invoice that used that test | The line, name and price are unchanged |
| P11-3 | Deleted tab → Restore the test | It is searchable on New Invoice again |
| P11-4 | Same for a Doctor, then a 3rd party | Hidden from "Tests ordered by / referred by" and from new bills; old bills still show the name |
| P11-5 | User Management → Delete a technician with a reason | User signed out and cannot sign in; their room is emptied like Deactivate; Deleted tab → Restore → user is inactive until Reactivate |
| P11-6 | Try Delete on your own user row | Button disabled / API refuses |
| P11-7 | Try deleting the last active Owner/Admin (use a second account) | Refused with a message |
| P11-8 | Invoices → open a Confirmed/Finalized invoice | No Discard button; a direct API call returns 409 |
| P11-9 | Receptionist: Invoices → Drafts → Discard own draft | Draft permanently removed |
| P11-10 | Admin: Discard another staff member's draft | Draft permanently removed |
| P11-11 | Audit Log (Owner) → filter by each action | Rows for every action above (SOFT_DELETED, RESTORED, INVOICE_DRAFT_DISCARDED) with reason and before/after. **PASS condition: an Admin does not see Audit Log by default — this is correct; the Owner can grant `audit.view` to an Admin.** |
| P11-12 | Receptionist/Cashier/Lab Tech: open `/audit-log`, `/catalog-admin` | "You do not have access" |
| P11-13 | Test DB cleanup | `medscope_test` has no stray LAB_TECH fixtures; `medscope_dcms` unchanged |

The pre-go-live list (§12) and known-not-done list (§13.4) are unchanged.

## 15. Prompt 12 Verification & Owner Acceptance (2026-11-13)

### 15.1 Non-browser evidence (real results)

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only; guard unchanged) | **141 passed**, 0 failed, **twice in a row** (135 before + 6 in `tests/test_prompt12_imaging_lock.py`) |
| Fixture-created staff in `medscope_test` | Start of Prompt 12: **408** (366 with 8-hex names + 42 older auth-test users; 98 of the 108 LAB_TECH were already soft-deleted by Prompt 11). After the one-time hard delete: **0** (8 seed accounts remain). After run 1: **0** (total staff 8). After run 2: **0** (total staff 8). |
| `alembic heads` / `current` / `check` | `a4d8c2e6f1b7` single head / at head / clean (no schema change) |
| `tsc -b`, `oxlint`, `vite build` | 0 errors; warnings only; build succeeds |
| OpenAPI / permissions | 97 paths / 111 operations; 39 permission keys (21 money) |
| Invoice auto-refresh test | The project has **no frontend test runner**; verified by code review only (non-browser): `recordSampleTaken` and `rejectSample` announce a `medscope:sample-changed` event and the Invoices page refetches list and open detail on it, on focus and every 30 s while a detail is open. |
| Browser / Playwright | **Not run.** Owner does acceptance below. |

Other test tables (patients, invoices, tests, audit rows) still grow with each run; only Staff fixtures were in scope.

### 15.2 Manual acceptance checklist for the owner (one click path, one expected result each)

| # | Click path | Expected result |
|---|---|---|
| P12-1 | Open an invoice (detail), in another tab/user take its sample in My Work, return to the invoice tab | Sample status shows COLLECTED without a manual reload (immediately in the same window; on focus or within 30 s from another window) |
| P12-2 | Invoice with an imaging test, record "Imaging performed" in My Work, open the invoice | The line shows PERFORMED but is **not** locked |
| P12-3 | Cancel that imaging line before its result is completed | The ordinary cancel/refund flow is offered (no special approval step) |
| P12-4 | Complete the imaging result | The line is now shown locked; ordinary cancel is refused |
| P12-5 | As Owner, same day: **Unlock (same day)** on that line with a reason | The line is unlocked; as Admin the link is absent and the API returns 403 |
| P12-6 | Log in as Admin | **Audit Log is not in the sidebar. This is correct** (default OWNER only; the Owner can grant `audit.view`) |

### 15.3 Known not done (additions)
- **M11.4 barcode scan-to-task-open: deferred to the product-finishing phase by explicit owner decision** (not forgotten).
- Everything in §13.4 is unchanged.

## 16. Pre-Lock Cancellation, Separate Disbursement and Business Day Status: Verification and Owner Acceptance

### 16.1 Non-browser evidence

| Area | Evidence (all against `medscope_test`; guard unchanged) |
|---|---|
| Cancellation (`tests/test_prompt13_prelock_cancellation.py`, 11) | immediate effect, client amount/type ignored; owner case 9000/3000/5000 (preview = single function = grid: retained 3000, refund 0, new due 1000); locked line 409; rejected specimen refused (not delegated to D15); second cancellation 409; full lifecycle display (`CANCELLED - REFUND PENDING PAYOUT` then `CANCELLED - REFUNDED`) with audit rows and no approval entry; zero refund reads `CANCELLED`; a forced audit failure rolls the cancellation back (atomic); pending-approval review rules (Admin/Owner only, reason required, 409 after the sample is taken). |
| Roles and whole invoice (`tests/test_prompt13a_whole_invoice_no_approval.py`, 12) | Receptionist, Cashier, Admin and Owner each cancel a line without approval; Lab Tech 403; whole-invoice preview equals the single function summed; all lines cancelled together then a separate disburse; a channel sent in a cancel body is ignored and nothing is paid; blocked when any line is locked (409, nothing changed); forced failure on a later line rolls everything back; D15 still needs approval and cancels nothing until approved. |
| Business Day (`tests/test_prompt13b_business_day_state.py`, 4) | all five roles read identical open state and identical closed state; Lab Tech body is exactly `{is_open, day_number, business_date}`, `/business-day/status` and `/current` stay 403; unauthenticated 401. |
| Referrer fixtures | `purge_fixture_referrers` in `tests/fixture_cleanup.py` runs at session teardown; `medscope_test` holds only the 10 seed referrers after a run; `test_p04_01` filters by a unique term. |

### 16.2 Manual acceptance checklist for the owner

| # | Click path | Expected result |
|---|---|---|
| C-1 | Receptionist: Invoices → open a Confirmed invoice with an unlocked line → **Cancel Test** | Read-only breakdown, no amount box, no channel field, a note that nothing is paid by this click; confirming cancels at once; the line reads CANCELLED or CANCELLED - REFUND PENDING PAYOUT without a reload |
| C-2 | Same as Admin, Cashier and Owner | Same result; no Approve step anywhere |
| C-3 | Invoice 9000 with 3000 paid, cancel the 5000 line | Refund 0, retained 3000, new due 1000 |
| C-4 | A paid invoice with a refund due, after cancelling | Banner "Refund of ৳X is pending payout [Disburse now]"; **Disburse now** opens the Disburse modal; nothing is paid until you confirm there |
| C-5 | Same invoice, **Cancel Whole Invoice** | Per-line rows, total refund, retained, new due; both lines CANCELLED together; refunds paid one at a time through Disburse |
| C-6 | Take a sample on one line, reopen the invoice | **Cancel Whole Invoice** is gone; on a stale page the click shows "Sample already taken" and nothing changes; the other line can still be cancelled alone |
| C-7 | Lab Tech rejects a specimen, Submit D15 request | Still waits for Admin/Owner approval; line not cancelled until approved |
| C-8 | Receptionist: look for any edit-price / discount / payment / add-line action | Only Cancel Test / Cancel Whole Invoice |
| C-9 | While the business day is open, log in as Lab Tech | Header shows "Day #N Open (date)", like every other role |
| C-10 | Close the day (Admin/Owner), reload as Lab Tech and another role | Both show "Business Day Closed"; Lab Tech sees no business-day money and cannot open the Business Day screen |

### 16.3 Known not done
- Frontend behaviour is checked by `tsc`/`vite build` and code review only (no frontend test runner, no browser run).

## 17. Reference Range Versioning (D24, Prompt 14): Verification and Owner Acceptance

### 17.1 Non-browser evidence

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only), run twice | **180 passed, 0 failed** both runs (168 + 12 new in `tests/test_prompt14_reference_ranges.py`); referrer rows stay at 10 |
| Age conversion | days as entered; calendar-aware years/months from the visit date (30 years = 10957 days with 7 leap days; 2 years back from 29 Feb 2024 = 731; 3 months back from 31 Jan 2026 = 92); 365/30 approximations only without a visit date |
| Band selection | male adult gets the male band (12.5 g/dL -> LOW) and female adult the female band (-> NORMAL); a child falls to the any-sex band and is labelled `FALLBACK_ANY`; no matching band -> `NO_BAND`, no flag, no range, never a wrong band; gender Other only matches any-sex bands |
| Impossible values | a value above the component's impossible maximum is still rejected (400) |
| **Non-destructiveness** | a result is saved; then a new version of its band, a new band and a retirement are made; the saved item (range, critical limits, text, version id, match type, flag) is byte-for-byte unchanged in the database and when re-read through the API; the next result uses the new version (or `NO_BAND` after retirement) |
| Management | new version keeps the old row's values, marks it not current with `retired_at`; history lists both; superseding an old version 409; validation 400/422; overlap 409; only Admin/Owner can manage (Receptionist, Cashier, Lab Tech 403); audit rows written |
| Migration carry-forward | every component in the test DB has a version 1 band; demo CBC hemoglobin 12-16 survived as version 1; downgrade restored all 27 component ranges and upgrade re-created 27 versions; dev DB 26 -> 26 with identical values |
| `alembic heads` / `check` | before `a4d8c2e6f1b7`, after `b7e3d91c5a24` (single); "No new upgrade operations detected" |
| `tsc -b` / `vite build` | 0 errors / succeeds |
| `oxlint src` | 0 errors; 122 warning lines (unchanged baseline) |
| OpenAPI / permissions | 106 paths / 120 operations; 39 permission keys (21 money); no new key |
| Browser / Playwright | **Not run.** Owner does acceptance below. |

### 17.2 Manual acceptance checklist for the owner

| # | Click path | Expected result |
|---|---|---|
| R-1 | Admin/Owner: Catalog & Deleted → Reference ranges → search a test → open it | Components listed with their version-1 band (Sex Any, age 0 - no limit) carried from before |
| R-2 | **Add band** for a component: Female, 6570 days to no limit, reference 12-15.5 | Band appears; an overlapping Female band is refused with a clear message |
| R-3 | **New version** on a band with a different range | `v2` current, `v1` kept as history (tick "Show old versions") |
| R-4 | Enter a result for an adult female and an adult male on the same test | Each sees their own range and flag; the report text shows the band's range |
| R-5 | Enter a result for a patient with no matching band | "No range for this age/sex: review manually", no Normal/Low/High flag |
| R-6 | Save a result, then change that band (new version), reopen the saved result | The saved result still shows the range it was entered with |
| R-7 | **Retire** a band (reason required) | It disappears from current bands; saved results keep their range |
| R-8 | Receptionist / Cashier / Lab Tech open Catalog | No Reference ranges tab / 403 on the endpoints |

### 17.3 Known not done
- No clinical range values were invented: the 26 seeded demo components carry their demo range as version 1 for every age and sex. The owner enters real age/sex bands.
- Bands are keyed on total days at the visit; a date of birth is not recorded, so age comes from the age entered at the visit.

## 18. Doctor Sign-off (D22, Prompt 15): Verification and Owner Acceptance

### 18.1 Non-browser evidence

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only) | **202 passed, 0 failed** (180 + 22 new in `tests/test_prompt15_doctor_signoff.py`) |
| Queue | only DOCTOR_REQUIRED / BOTH_SIGNATURES orders with an ENTERED result and no approval; DRAFT, no result and technician-final excluded; money-free; Admin filter by doctor; DOCTOR sees only own assigned orders and cannot widen the scope |
| Role gating | Receptionist, Cashier, Lab Tech get 403 on all four endpoints; a Lab Tech granted the key by override is still refused (guard verified by weakening it once: the test fails) |
| Path A | attestation and doctor required (400), doctor without registration number (409), clinic type (400), unknown doctor (404), nothing written by refused calls; success writes the row, moves the order to COMPLETED, locks the line, writes `DOCTOR_APPROVAL_RECORDED_BY_STAFF`; second approval 409; Owner works too |
| Path B | assigned order approved with `is_attestation = false`, `DOCTOR_APPROVED_OWN_RESULT`; another doctor's or unassigned order 403 (detail and approve); login with no linked profile sees an empty queue and cannot approve; body `doctor_id` / `attestation` ignored |
| Both paths | same doctor id, name and registration number on the approval whichever path wrote it; the audit rows differ |
| Both-signature | technician `entered_by_id` / `entered_at` unchanged; doctor approval reachable from the same order (detail shows both) |
| Snapshot | renaming the doctor afterwards does not change the approval's name or registration number |
| Audit viewer | the Prompt 11 viewer (`GET /audit-logs`) lists and filters both approval actions |
| User link | `doctor_profile_id` accepted only for a DOCTOR user, cleared with null |
| `alembic heads` / `check` | before `b7e3d91c5a24`, after `c9a4e7b2d815` (single); "No new upgrade operations detected"; downgrade/upgrade round trip on `medscope_test` |
| `tsc -b` / `vite build` / `oxlint` | 0 errors / succeeds / 0 errors, no warning in the new files |
| OpenAPI / permissions | 110 paths / 124 operations; 39 permission keys (21 money); no new key |
| Browser / Playwright | **Not run.** Owner does acceptance below. |

### 18.2 Manual acceptance checklist for the owner

| # | Click path | Expected result |
|---|---|---|
| D-1 | User Management: link the dev DOCTOR user `doc` to a doctor profile that has a registration number | Saved; shown on the user |
| D-2 | Enter and submit a result for a doctor-required test (for example a USG) as Admin/Lab | Order shows Awaiting Doctor |
| D-3 | Admin: Doctor Sign-off | The result is listed with rule "Doctor required" |
| D-4 | Admin: Review, pick a visiting doctor, leave the tick off | Confirm stays disabled |
| D-5 | Tick the attestation, Confirm | Approved; the row leaves the queue; order COMPLETED and the report Final (listed under Issued Reports) |
| D-6 | Owner: Audit Log, filter `DOCTOR_APPROVAL_RECORDED_BY_STAFF` | One row, actor = the Admin, text names the doctor and registration number |
| D-7 | Admin: **Assign doctor** on another pending result to `doc`'s profile; log in as `doc` | `doc` sees only that result; no other doctor's items |
| D-8 | `doc`: Review, Approve | No picker, no tick; audit shows `DOCTOR_APPROVED_OWN_RESULT`, actor `doc` |
| D-9 | Both-signature test: technician submits, then Admin approves | Review shows technician and doctor sign-off; both remain after approval |
| D-10 | Receptionist / Cashier / Lab Tech | No Doctor Sign-off item; direct URL shows no permission / API 403 |

### 18.3 Known not done
- No reject / send-back path (not decided).
- A both-signature result is still listed as Ready before the doctor signs (it cannot be finalized until then).
- In `medscope_dcms` the existing DOCTOR user `doc` is not linked to a doctor profile yet (the owner links it in User Management), and no doctor-required result currently waits for approval there.

## 19. Draft to Final Report (Module 14, Prompt 16): Verification and Owner Acceptance

### 19.1 Non-browser evidence

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only) | **222 passed, 0 failed** (202 + 20 in `tests/test_prompt16_final_reports.py`) |
| COMPLETED is not Final | a submitted technician-final result is COMPLETED with no report row and shows `can_finalize` |
| Technician-final | explicit Finalize creates the row (v1, `FINAL_AUTHORIZED`, snapshot, text signatures), audit, placeholder notification; leaves Ready; appears in the Issued list and snapshot; second Finalize 409; Receptionist 403; unknown order 404 |
| Blocked | draft and missing result 409; REJECTED / CANCELLED / SPOILED / Not Performed 409 |
| Doctor-required / both-signature | approval finalizes in the same step (signatures carry the doctor name and registration number, attestation flag); both-signature without approval 409 "Waiting for the doctor's approval", finalizes with it; the DOCTOR login's own approval finalizes too |
| Cultures | technician-final culture refused at INCUBATING / PRELIMINARY, stage FINAL alone does not create a report, then Finalize works; a both-signature culture approved before FINAL is finalized when the stage reaches FINAL |
| **Non-destructiveness** | after Finalize the result is changed directly in the database and the API refuses a re-save (409); the snapshot returned is identical; the ORM guard and the database trigger both refuse changes to content columns (4 columns tried with raw SQL); a reference-range new version afterwards leaves the stored range text and value unchanged (Prompt 14 style) |
| One Final per order | a second FINAL row for the same order is refused by the partial unique index |
| Result lock / edit conflict | result save refused after a doctor approval; stale `expected_updated_at` returns 409 naming the other user; fresh stamp and no stamp save normally |
| No SMS | only `PENDING_INTEGRATION` rows exist and the table has no phone or message column |
| `alembic heads` / `check` | before `c9a4e7b2d815`, after `d2b6f8a1c439` (single); "No new upgrade operations detected"; downgrade / upgrade round trip on `medscope_test` |
| `tsc -b` / `vite build` / `oxlint` | 0 errors / succeeds / 0 errors, same 122 warning lines as before |
| OpenAPI / permissions | 112 paths / 126 operations; 39 permission keys (21 money); no new key |
| Browser / Playwright | **Not run.** Owner does acceptance below. |

### 19.2 Manual acceptance checklist for the owner

| # | Click path | Expected result |
|---|---|---|
| F-1 | Lab: submit a result for a technician-final test, open Preview Report | Shows "Finalize report" enabled |
| F-2 | Click Finalize report | Toast with the report number; the row leaves Ready Results |
| F-3 | Reports > Issued Reports, search the patient, click View result | The stored result with technician signature; Deliver still works with the due rule |
| F-4 | Try to save the result again from Lab | Refused: the test has a Final report |
| F-5 | Submit a both-signature test result, open Preview Report | Finalize disabled, "Waiting for the doctor's approval" |
| F-6 | Doctor Sign-off: approve it (Admin on behalf, or the doctor) | The report is Final at once (Issued Reports shows it with the doctor name and registration number) |
| F-7 | Culture test: submit result, move stages | Not finalizable until FINAL; then Finalize (or automatic if already approved) |
| F-8 | Cancel / reject a test, open Preview Report | Finalize disabled with the reason |
| F-9 | Two browsers open the same draft; save in one, then the other | The second shows "changed by ..." |
| F-10 | Receptionist / Cashier open a Preview Report | No Finalize button; API 403 |
| F-11 | Dev DB: the two orders already approved by `doc` before Prompt 16 | Ready Results shows them with Finalize enabled (approval exists); finalizing creates their reports |

### 19.3 Known not done
- No corrections / new versions (Module 15), no signature image upload, no PDF / print, no QR, no real SMS (placeholder row only), no auto-save in the result modal.
- Orders approved before Prompt 16 have no report until someone clicks Finalize (no history was fabricated).
- A technician-final result is still COMPLETED (operational) before it is finalized; a Final report only exists after the click.

## 20. Handover and Dues (Modules 17 and 18, Prompt 17): Verification and Owner Acceptance

### 20.1 Non-browser evidence

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only) | **284 passed, 0 failed** (Prompt 19 added 3 in `tests/test_prompt19_referrer_edit.py`; 245 before Prompt 18, then Prompt 18's 3 tests, the verification suite `tests/test_prompt18_verification.py` and Prompt 18B's 3 in `tests/test_prompt18b_fixes.py`; Prompt 17's 23 tests are in `tests/test_prompt17_handover_dues.py`) |
| Settings | defaults `true` / `500`; Owner edits; Admin / front desk 403; negative limit 422; audit holds old and new value |
| Held report | held by default (receptionist 403, Admin needs a reason, logged with reason and "released despite due"); paying the due inline releases it with no override; setting off: never held, no reason, audit "hold setting off"; back on holds the next one |
| Handover search | finds a report by bill no., temporary bill no., patient no., test name, mobile and name; unknown term finds nothing; `has_due` true / false filters |
| Reprint | the reprint log row is persisted (it was not before), `is_duplicate` after a handover, count increases |
| Dues aging | bucket boundaries (0 and 7 days, 8 and 30, 31 and 90, 91); list filter by bucket; search by patient no.; call list groups a patient's bills, oldest first, bucket totals add up, paying removes a bill (derived); bad bucket 400; Lab Tech 403 |
| Write-off | Admin within the limit applies at once (due lowered, `written_off` raised; gross, discount, net, paid unchanged; audit says "Not a discount"; the rest can still be collected); above the limit pending with nothing changed, one pending per bill, Admin cannot approve, Owner approves / rejects; cumulative limit; Owner any amount; roles 403; validation (blank reason, amount above due, zero, unknown bill) |
| Cancellation after write-off | the cancellation arithmetic does not owe the written-off amount again |
| Doctor balances | Admin / Owner only; the two kinds sum separately (1000 - 250 = 750 and 300) and the response has no merged total |
| Permissions | 43 keys (24 money); Prompt 17's three keys and Prompt 18's `accounting.view` have the expected holders; `settings.manage` Owner only |
| `alembic heads` / `check` | `f9a2c4d6e8b1` (single); "No new upgrade operations detected" |
| `tsc -b` / `vite build` / `oxlint` | 0 errors / succeeds / 0 errors, no new warning in the new files |
| OpenAPI | 129 paths / 144 operations |
| Browser / Playwright | **Not run.** Owner does acceptance below. |

### 20.2 Manual acceptance checklist for the owner

| # | Click path | Expected result |
|---|---|---|
| H-1 | Reports > Issued Reports: search by bill no., temp bill no., patient no., test, phone, name | The report is found each way |
| H-2 | Open a held report (bill with a due) as Receptionist | DUE HOLD badge, Take payment button, no Deliver |
| H-3 | Take payment for the full due | Receipt shows; the row becomes deliverable; Deliver works without override |
| H-4 | As Admin, Override & Deliver another held report with a reason | Delivered; Audit Log shows "released despite due" |
| H-5 | Owner: Settings, untick the hold; Receptionist reopens a bill with a due | Deliver is available, no hold; tick it back on |
| H-6 | Reprint a delivered report | Marked Duplicate; Audit/reprint log has the entry |
| D-1 | Dues: use the age chips | Bills filter by 0-7, 8-30, 31-90, over 90 days; age badges match the bill dates |
| D-2 | Call list tab | Patients with dues, oldest first, with phone |
| D-3 | Admin: Write off a small amount (below the limit) | Done at once; the due drops and shows "written off"; discounts unchanged |
| D-4 | Admin: Write off above the limit | "Sent to the Owner"; due unchanged |
| D-5 | Owner: Dues > Write-offs > Approve | Applied; the bill's due drops |
| D-6 | Owner: Settings, change the Admin write-off limit | Admin's next write-off follows the new limit |
| D-7 | Doctor balances tab (Admin/Owner) | Two separate columns, all 0 with the explanatory note |
| D-8 | Receptionist / Cashier | No Write-offs or Doctor balances tabs, no Settings item; API 403 |

### 20.3 Known not done
- SMS reminders, corporate dues, online viewing and courier (deferred by decision); promised-payment-date notes; payouts and commissions (Modules 19 / 20); anything that fills the doctor balances (Modules 20 / 28).
- No write-off reversal. Handing the same report over twice is allowed (each handover is logged).

## 21. Accounting and Day Close (Modules 21 and 22, Prompt 18): Verification and Owner Acceptance

### 21.1 Non-browser evidence

| Check | Result |
|---|---|
| `python -m pytest` (`medscope_test` only) | **284 passed, 0 failed** (see sections 22 and 23 for the Prompt 18B fixes). Prompt 18 kept its own tests to the properties that cannot be checked another way; thorough verification is a separate, later prompt. |
| Ledger | after a bill with an initial payment, a line cancellation and a write-off, the Patient receivable account equals the invoice's due at each step; every journal entry in the database balances; the expected event types exist and no commission / visit-fee / consultant / outside-lab entry exists |
| Append-only | UPDATE / DELETE on `journal_lines`, UPDATE of an entry's memo, and a line that unbalances an entry are all refused by the database |
| Day close | expected cash equals opening + collections - refunds - deposits - withdrawals - expenses, deferred payouts 0 and unsynced items 0; Receptionist / Cashier 403 on the screen and movements; owner withdrawal Owner only; each movement lowers expected cash; close without counted cash 422; a variance above tolerance without a reason 400, with one 200 and the variance journaled; a closed day takes no movement (409); reopen Admin 403, no reason 400, Owner 200; adjustment before reopen 409, Admin 403, unbalanced manual lines 400, reversal 201, second reversal 409; re-close within the tolerance needs no reason |
| Permissions | 43 keys (24 money); `accounting.view` Admin and Owner |
| `alembic heads` / `check` | before `e5d7a2c9b138`, after `f9a2c4d6e8b1` (single); "No new upgrade operations detected"; round trip on `medscope_test` |
| `tsc -b` / `vite build` / `oxlint` | 0 errors / succeeds / 0 errors (119 warning lines, two of them the same set-state-in-effect pattern the other pages have) |
| OpenAPI | 129 paths / 144 operations |
| Browser / Playwright | **Not run.** Owner does acceptance below. |

### 21.2 Manual acceptance checklist for the owner

| # | Click path | Expected result |
|---|---|---|
| A-1 | Business Day as Admin, day open: read Expected cash | Opening cash, collections, refunds, deposits, withdrawals, expenses, four "not built yet" lines at 0, and a total that adds up |
| A-2 | Record an expense (with a what-for) and a bank deposit | Both listed; expected cash drops by their sum; the Accounting cash book shows two outflows |
| A-3 | As Owner, record an owner withdrawal; as Admin the option is absent and the API returns 403 | |
| A-4 | Enter counted cash different from expected | Variance shows with short / over; Close stays disabled until a reason is typed |
| A-5 | Settings (Owner): set the variance tolerance to 50; repeat with a variance of 20 | No reason needed |
| A-6 | Close the day | Status Closed; counted cash, variance and reason shown; no new payment can be taken (open a new day first) |
| A-7 | As Admin on the closed day | No Reopen button; API 403 |
| A-8 | As Owner: Reopen with a reason, then Reverse an entry with a reason, then Close the day again | The reversal appears in the cash book as a new row; the original is untouched |
| A-9 | Accounting: cash book, daily income & expense, dues, cost by referrer, with and without a date range | Figures match the bills and payments made since Prompt 18; cost by referrer shows 0 cost and the note |
| A-10 | Export CSV on each tab and open it in Excel | Same rows as on screen |
| A-11 | Receptionist / Cashier / Lab Tech | No Accounting item; the API returns 403 |

### 21.3 Known not done
- Postings for commission, visit-fee handover, consultant fee and outside-lab cost (Modules 19 / 20 / 28); P&L, balance sheet, cash flow; a real unsynced-items check; backfilling the journal for earlier bills and payments.

## 22. Prompt 18B Fixes: Verification

| Finding | Regression test (`tests/test_prompt18b_fixes.py`) |
|---|---|
| 1 Closed / reopened day bypass | a payment and a bill confirmation are 409 while the day is CLOSED and again while REOPENED, no payment row with a NULL day exists, and a payment on an OPEN day still returns 201 |
| 2 Bank deposit by Admin | documentation only; the existing Prompt 18 tests already assert Admin 201 on a bank deposit and 403 on an owner withdrawal |
| 3 New day while reopened | open while OPEN 400 (unchanged); close, reopen, open 400; close again, open 201 |
| 4 Adjusting entry and expected cash | after a manual Cash adjustment on a reopened day, expected cash and `adjusting_entries` move by the amount, and counting the new figure gives variance 0 |

Test-suite housekeeping: a conftest fixture now makes every test start with one OPEN day (days an earlier test left REOPENED are put back to CLOSED in `medscope_test`); the verification suite's expected-cash identity includes the new adjusting-entries term; two older worklist tests find their order by bill number because the test database holds more than 200 urgent orders. `pytest`: **281 passed, 0 failed**. Browser: not run.

## 23. Doctor / 3rd-party Edit (Prompt 19): Verification and Owner Acceptance

`tests/test_prompt19_referrer_edit.py` (3 tests): edit updates the same record (id unchanged, untouched fields kept, audit holds old and new, empty name refused, commission not exposed, unknown id 404); edit needs the same key as delete (Receptionist, Cashier, Lab Tech 403 on both; Admin and Owner allowed; a deleted record is 409 until restored); a saved doctor approval keeps its name and registration number after the doctor is renamed and the registration number corrected. `pytest` **284 passed, 0 failed**; `tsc -b`, `oxlint` (exit 0), `vite build` pass; no migration. Browser: not run.

| # | Click path (Admin or Owner) | Expected result |
|---|---|---|
| E-1 | Catalog & Deleted > Doctors & 3rd parties: click **Edit** on a row | A form opens with the row's name, type, phone, registration no., specialty, chamber |
| E-2 | Correct a phone number and Save | Toast; the list shows the new phone; the same doctor still appears on old bills |
| E-3 | Correct a registration number; open a report already approved by that doctor | The approval still shows the number it was signed with |
| E-4 | Receptionist / Cashier | No Catalog & Deleted item; the API returns 403 |

## 24. Audit Trail (Module 23, Prompt 19B): Verification and Owner Acceptance

`tests/test_prompt19b_audit.py` (13 tests): the database refuses UPDATE, DELETE and TRUNCATE on `audit_logs` (raw SQL and ORM); `reprint_logs` is gone and no code mentions it; no code under `backend/` deletes or purges audit rows and no `/audit-logs` route accepts anything but GET; draft discount edits write before / after (and an unchanged save writes nothing), confirm records the final discount state; the initial payment has its own event; every report open writes one row with no throttling and a 404 writes none; a ready-result preview is logged with the test order id; reprints are audit rows and the print counter still counts; domain grouping; viewer filters (domain, role, free text, literal `%`) and permissions; CSV has the BOM and column list, respects the filters, matches the list total and audits itself; spreadsheet formulas are neutralised. `pytest` **297 passed, 0 failed** (284 earlier tests + these 13); `tsc -b`, `oxlint` (exit 0, existing warnings only), `vite build`, `alembic heads` (single head `a19b5c7d9e31`) and `alembic check` pass. Browser: not run.

| # | Click path (Owner) | Expected result |
|---|---|---|
| A-1 | Audit Log: open the page | Filters for search, domain, action, entity, person, role and two dates; Export button |
| A-2 | Choose Domain = Discounts | Only discount rows (empty until a discount is used) |
| A-3 | New Invoice: save a draft, add a 10% line discount, save, change it to 40 Tk, save; then Audit Log > Discounts | Two `INVOICE_DISCOUNT_CHANGED` rows; Details shows Before and After text |
| A-4 | Finalize that draft with a 100 Tk payment | `INVOICE_DISCOUNT_CONFIRMED` and `INVOICE_INITIAL_PAYMENT` rows next to `CONFIRM_INVOICE` |
| A-5 | Open a finalized report (Reports > Preview / View), then Audit Log > Reports | One `REPORT_VIEWED` row per open, with your name and role |
| A-6 | Type part of a patient or invoice number in Search | Rows whose action, entity or before / after text contain it |
| A-7 | Set a filter, click **Export CSV (current filters)**, open the file in Excel | Only the filtered rows, readable accents, no formula cells; the log then shows an `AUDIT_LOG_EXPORTED` row with your filters |
| A-8 | Admin without `audit.view` | No Audit Log menu; the export API returns 403 |
| A-9 | (Optional, needs a database session) `UPDATE audit_logs SET action = 'X'` | Fails with "audit_logs is append-only" |
