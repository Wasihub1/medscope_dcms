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

### Test Scenarios & Execution Outcomes (6 Test Suites covering all 14 items)

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

### Test Modules:
1. `tests/test_receptionist_e2e.py` (Prompt 03 Core Scenarios — 14 tests)
2. `tests/test_prompt04_corrections.py` (Prompt 04 Specific Corrections — 6 tests)

### Baseline Execution Command (Prompt 04/05 accepted baseline):
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
1. **Invoice Intake & Line Locks:** Verified that `InvoiceLine.is_locked` is set upon specimen collection or imaging completion, and checked that `refund_service.py` prevents ordinary pre-sample cancellation when locked.
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
