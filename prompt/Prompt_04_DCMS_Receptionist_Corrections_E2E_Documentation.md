# Prompt 04 — MedScope DCMS Receptionist Corrections, UI/API Audit, Playwright E2E & Documentation

## ROLE AND MISSION
You are Antigravity, the implementation agent working inside the existing MedScope / Diagnostic Center Management System (DCMS) repository. This is **Prompt 04**, continuing Prompt 03. Implement the confirmed corrections, inspect and repair all affected end-to-end workflows, run browser-based Playwright verification in your sandbox, and finish by updating all canonical project documentation and issuing an evidence-based completion report.

**Act on the actual source and runtime; do not treat old implementation reports as proof. Do not begin a new business module. Do not rewrite or redesign the already acceptable UI. Preserve all working features, historical transactions, and existing data.**

Read first: `project-context.md`, `README.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`, and relevant application code. Where available, consult the Receptionist phase handoff and Prompt 03/report as historical context. Latest user decisions in this Prompt 04 override conflicting earlier instructions.

## BASELINE / GUARDRAILS
- Production target: React/TypeScript, FastAPI, Pydantic v2, SQLAlchemy 2.x typed ORM, PostgreSQL, Alembic. Legacy Streamlit/SQLite is reference only, not the new runtime.
- Use whole-Taka integer amounts end-to-end. Do not use floating-point financial persistence or silently change historical invoice snapshots.
- Keep the existing dev role switcher for Receptionist/Admin (and Owner if already present). Full login/RBAC is deferred, but server-side authorization boundaries must still be enforced by the existing development actor mechanism. Never trust a client-only role toggle as production authentication. Document the dev-only security limitation.
- Business rules live in backend services, with Pydantic request/response validation. All financial and state changes must be transactional, tenant/center-scoped, audited, and safe under concurrency where relevant.
- Do not expose existing commission rates/amounts, test cost prices, profit, owner accounting, or other privileged data in Receptionist search, detail or API responses.
- Do not wipe/reset production or user-created data, recreate the database, or use destructive migrations. Back up/make a safety plan before migrations. Development-only seed must remain idempotent.
- Preserve the product palette (#CF8852, #E8E7E3, #525333), central theme tokens, responsive uneven Bento Grid, sidebar, existing routes, keyboard access, UI styling, and stable `data-testid` patterns.
- The old restriction “do not run tests” has been superseded: **Prompt 04 explicitly requires automated tests including real Playwright browser E2E**. Report actual results only.

## IMPLEMENT ALL 14 CONFIRMED CORRECTIONS

### 01 — Separate Prescribed By and Referred By
On New Invoice and corresponding invoice detail/print/data contracts provide **two distinct independent fields**:
1. `Prescribed By (Doctor)` — selects **Doctor only**.
2. `Referred By (Doctor / Third Party)` — selects Doctor or third-party referrer (e.g. Palli Chikitsak/Broker).
Both fields support search/autocomplete and **inline Add** without losing invoice form inputs. The same Doctor may be chosen in both. Both may be empty for walk-in patients unless an existing confirmed rule explicitly requires otherwise. Persist stable separate identities/relationships and show the correct semantic labels in invoice details/print. Do not overload a single referral field, and migrate data conservatively if schema expansion is needed.

For a **new** Doctor or Third Party, the inline Add workflow must support a commission entry as the user requested. The Receptionist must **not see existing/stored commission rates, amounts, calculations, or ledgers**. Implement a narrowly scoped write-only initial commission input (if permitted in dev workflow), with validation, no commission values in search/list/detail/creation responses, no ability to read back/update commission after creation, and an audit event. Never interpret this as permission to expose existing rates. Separate financial commission handling from general referrer details in backend and docs. If the current security architecture cannot safely support this requirement, implement the safest isolated server-side creation contract, explicitly document any remaining limitation, and do not silently reveal privileged data.

### 02 — Business Day Close: Admin/Owner only
Keep an **Open Business Day** action for Receptionist where otherwise eligible. Add/retain a **Close Business Day** option in Admin/Owner development mode; **Receptionist and Cashier must not close**, reopen, or adjust a closed day. Remove/hide close action in unauthorized role views and enforce **403/appropriate structured error** server-side. Validate one open day per tenant/center, required balancing/close invariants, concurrency, correct totals, and audit actor/time. Keep dev role switcher.

### 03 — Investigation catalogue suggestion filtering
Once a test is selected for an invoice, remove it from autocomplete suggestion results so it cannot be added twice unintentionally. When it is removed from the invoice, it should appear again if matching. Search, keyboard selection, and async results must honor selected IDs. Enforce duplicate-prevention/invoice integrity server-side where applicable; preserve intentional distinct order rules only if clearly specified.

### 04 — Discount in both % and amount
For each supported test-line and invoice-level discount, offer **Percentage (%)** and **Amount (৳)** modes, with synchronized equivalents where appropriate. Switching modes or editing a value must **not** apply the discount twice. The applicable maximum is the full eligible test price / subtotal (up to 100%), not an invented 50% or Receptionist discount cap. Never allow negative line payable or negative invoice payable. Define integer-Taka rounding behavior for percentage input and enforce all limits in Pydantic/backend, not only UI. Invoice preview, saved totals, and print must match exactly.

### 05 — Default paid amount zero
New Invoice's paid amount defaults to **৳0**. A valid invoice can be confirmed with no initial payment, leaving it Unpaid. Do not create a zero-value payment record. Partial payment remains supported; validate non-cash references only when a positive non-cash payment is actually made. Prevent overpayment.

### 06 — Generate → Preview → Back/Correction → Save & Print
Implement a clear two-stage creation flow:
`Invoice Form -> Generate Preview (non-final) -> Back & Correct OR Save [and Print] -> Persist -> Print available`.
Generating a **preview must not finalize or permanently number** an invoice or book payment. Back returns to the form with **all state intact** (patient, tests, discounts, both referral fields, urgency, payment details). Preview should display **Patient Copy** and **Office Copy** side-by-side on an appropriate A4 landscape print layout with readable invoice details, correct breakdown, and clear copy labels. No unsaved preview may masquerade as an official saved invoice. Final save assigns permanent number transaction-safely, persists accurate records once, and enables print. Prevent double submit/double invoice on click/retry. If print is blocked, saved invoice still exists and can be printed/reprinted later; show accurate status.

### 07 — Reset invoice form after successful save
After final persistence succeeds, reset New Invoice entry form to a clean state with Paid Amount = ৳0 and no selected patient/tests/referrals/discounts. Keep **the saved invoice preview/print context separately** so printing after reset remains correct. On API failure or unsaved Back action, preserve current entries. Do not accidentally carry previous invoice data into next entry.

### 08 — Global search inline, no modal
Remove the global search modal. Clicking/focusing the header search field must allow **typing directly in the bar**, showing grouped autocomplete results in an anchored dropdown below it. Preserve debouncing, keyboard navigation, accessible focus/escape, loading/empty/error states, and permitted patient/invoice/test/report search categories. No unrelated navigation or background page remount just from focusing/typeahead.

### 09 — Ctrl+F replaces Ctrl+K
Replace the app shortcut `Ctrl+K` with `Ctrl+F` to focus the inline global search when the application screen is active. Remove the old Ctrl+K app handler. Scope the event carefully: do not hijack native browser find in the print preview/print flow, and avoid interfering with text editors/appropriate contexts. Document platform/browser limitations where shortcuts cannot reliably override native behavior.

### 10 — Diagnostic Invoices print action
Fix the nonworking Print button in Diagnostic Invoices / Invoice Registry / Invoice Detail. For an existing saved invoice, clicking Print must load the correct invoice printable view and invoke the browser print dialog directly, without redirecting the user's background page to a different registry. For **reprints**, display `Duplicate` per existing policy and record actor/time through exactly one explicit audit event. Avoid double-counting print events across printable GET and print-event POST. Preserve historical invoice values and print both Patient/Office copies.

### 11 — Payment status labels
Across dashboard, list, filters, detail, receipts and print, standardize presentation labels:
- `Full Due` -> **Unpaid**
- `Partial Paid` -> **Partial Due**
- `Paid` -> **Paid**
Keep backend enums unchanged where possible and use a consistent mapping; do not confuse payment status with refund status. Ensure zero-paid invoices display Unpaid and partially paid invoices display Partial Due.

### 12 — Patient History -> Old Invoice context bug
When an old invoice is opened from Patient History, the invoice detail may open as an overlay/drawer/modal or appropriate nested detail **without changing the background screen from Patients to Invoice Registry**. Closing/back must return to the original patient, history tab, list filters, page, and scroll position. No stale record display. Audit source of unintended route/query-param/navigation coupling and fix deep links using contextual navigation or local overlay state. Direct URL access to invoice details should still work.

### 13 — Thorough Playwright UI/props/navigation audit
Perform source-level review of component **props**, callback wiring, click handlers, dialog open/close, router usage, keyboard focus, selected record IDs, stale async responses, and state persistence. Then use Playwright **in a real browser** to traverse every Receptionist screen plus permitted Admin close/refund boundary. Cover all meaningful buttons, inputs, autocomplete, tables, detail links, overlays, previews, prints (instrument browser print as needed), and Back/Close paths. Identify unexpected redirect, unintended background route changes, missing handlers, broken actions, wrong selected records, and lost form data. Fix observed defects and rerun relevant tests. Do not claim that merely reviewing code or passing backend tests constitutes browser E2E verification. Record findings and evidence/screenshots/traces in a reasonable location; keep generated bulky artifacts out of Git unless explicitly intended.

### 14 — Refund status on invoices
In Invoice List/Search and Invoice Detail, surface a **separate Refund Status** alongside Payment Status. Support applicable states such as `No Refund`, `Refund Pending`, `Refund Rejected`, `Partially Refunded`, and `Fully Refunded`, distinguishing approved-but-not-executed from money actually returned. Source statuses from backend request/refund/payment state, not guessed local labels. Display permitted request history, status transitions, and refund totals without restricted financial data. An approved request must not be marked refunded before actual refund transaction is recorded. Ensure correct aggregation when more than one line/request is involved and no duplicate refunds. **Do not investigate or fix the previously mentioned “৳1 maximum / maximum refundable ৳0” bug as a separate Prompt 04 requirement: the user explicitly deleted that earlier item.** Only change refund computation when demonstrably necessary for this status workflow or an otherwise blocking defect; clearly report scope.

## REQUIRED IMPLEMENTATION METHOD
1. **Audit current code, routes, contracts, migrations and docs first.** Produce an internal issue-to-file/API mapping and identify implemented/partial/missing behavior. Do not duplicate working code. Review all former Prompt 03 gaps, especially draft/preview lifecycle, business-day permissions, shared-mobile patient handling, and print audit boundaries.
2. For each correction, trace **UI -> state -> API -> Pydantic schema -> service -> ORM/migration -> persisted outcome -> UI response**. Implement every affected layer as needed. Do not introduce hidden client-only business rules.
3. Add safe and reversible Alembic migration(s) where required. Protect existing rows; document migration revision and strategy. Verify tenant scoping, accounting/payment append-only rules, refund approval gates, sample-lock restrictions, and historical snapshots.
4. Keep existing functionality intact: patient search/history, patient creation, test selection, invoice creation, due collection, assignment, permitted refund request, authorized report print/delivery, dashboard, business day, and own-profile correction.
5. Ensure errors are actionable and show meaningful UI states. Stable selectors (`data-testid`) for critical controls and states should be added/maintained.

## PLAYWRIGHT SANDBOX INSTALLATION AND VERIFICATION
- If Playwright is absent, **install it yourself in the Antigravity sandbox** using the repository's package manager. Add `@playwright/test` (or the established project-equivalent) as a dev dependency, update `package.json` and the lockfile, install required browser binaries/dependencies, and configure a reproducible test runner and sensible base URL. Do not ask the user to install it manually.
- If an isolated sandbox cannot install/browser-launch due to external restrictions, document the exact error, attempted fixes, and unexecuted tests; do **not** invent passing results.
- Maintain/update all backend Python dependencies in `requirements.txt` with sensible compatible version constraints; never omit packages used at runtime. Verify clean installation and `pip check`. Frontend and Playwright dependencies must be recorded in `package.json` + lockfile. Do not commit generated virtual environments, browser binaries, `.env`, secrets, or node_modules.
- Start or configure local dev frontend/backend and real PostgreSQL development DB using existing `.env` without printing secrets. Apply required migrations and development-only safe seed if necessary, with non-destructive precautions. Run tests against an **isolated/clearly designated test environment**, never a production/customer DB.
- Execute backend relevant tests and real Playwright browser E2E (desktop and key responsive viewport). Cover all 14 corrections plus regressions. Verify API responses, print event count, permissions, invoice totals/statuses, refund lifecycle, backdrop route preservation, and zero-payment behavior. Include both successful and forbidden paths.
- Provide command, environment, scenario, expected result, actual result, pass/fail/blocked counts, and evidence paths. Re-run corrected failed scenarios. Never report “100% tested” without supporting browser evidence.

## DOCUMENTATION CONTRACT — MANDATORY AT THE END OF THIS PHASE
Maintain the agreed **nine canonical Markdown files**, rather than proliferating a Markdown file per screen or phase. Update all affected sections to match the **actual delivered implementation**:

1. `README.md` — working setup, install/start commands, roles, URLs, troubleshooting, doc index.
2. `project-context.md` — Prompt 04 phase summary, implemented/partial/blocked, issue resolution, repository changes, migration revision, seed, actual test outcomes, outstanding work and next action.
3. `docs/SCOPE.md` — confirmed business rules, two referral fields, create-time commission permission limitations, Business Day permissions, preview/print, discount, statuses.
4. `docs/ARCHITECTURE.md` — architecture, security boundary/role-switcher limitation, relevant architecture decisions and their date/status/tradeoffs (ADL).
5. `docs/DESIGN.md` — design tokens, header inline search, shortcuts, preview, responsive print, UI behavior, accessibility, `data-testid` conventions.
6. `docs/API.md` — exact routes, methods, request/response/Pydantic models, error codes, permission matrices, payment/refund/print events and frontend wiring; remove stale endpoints.
7. `docs/WORKFLOWS.md` — every Receptionist view/action/API mapping, invoice preview/save/print sequence, patient history nested invoice context, Business Day, referrer addition, refunds, navigation state diagrams as needed.
8. `docs/DATABASE.md` — ORM/schema changes, migration revisions, indexes, constraints, new referral links, money models, audit and transaction rules, development seed instructions and safe upgrade.
9. `docs/TESTING.md` — runnable environment setup, Playwright install/run, test cases covering all corrections and regressions, actual results and evidence links, untested/blocked cases, reproducible manual verification.

Retain `AGENTS.md`, license, critical tool/config/instruction files, source code, tests and required build configuration. Do not blindly delete other Markdown files: if redundant, **merge unique authoritative content first**, update links/references, then archive/remove only truly redundant documentation. Do not alter historical handoff evidence without an explicit reason. Do not claim documentation updated unless actual file changes exist. Document exact commands and paths; never include credentials.

## MANDATORY ACCEPTANCE MATRIX
Before declaring completion, report the status of each item 01–14 with: frontend change, backend/API change, DB migration (if any), browser E2E scenario, actual outcome, evidence path, and remaining limitation. Include at minimum:
- Same Doctor selected as both Prescriber and Referrer; separate Third Party; inline Add including creation-time commission input without readable commission leakage.
- Receptionist can Open but cannot Close; Admin/Owner can Close; Cashier forbidden; one-open-day integrity.
- Selected investigation removed/reintroduced correctly.
- %/৳ discounts produce consistent rounded payable, obey 100% ceiling, zero floor, and cannot stack twice.
- Default zero paid, Unpaid label, no zero payment row; Partial Due displays correctly.
- Generate nonfinal preview, Back keeps state, Save once, form reset only on success, two side-by-side printable copies.
- Existing invoice Print opens dialog for correct invoice; reprint mark/audit once.
- Inline global search + Ctrl+F; no search modal/Ctrl+K handler.
- Patient History old-invoice overlay returns to unchanged Patients context.
- Separate refund status in invoice list/detail, distinguish pending/approved/actually refunded.
- Other Receptionist interfaces have no newly discovered broken navigation or controls.

## FINAL RESPONSE FORMAT (NO VAGUE CLAIMS)
Provide one concise but thorough implementation report with:
1. Prompt 04 completion summary and exact commit/hash if available.
2. **14-row correction matrix** (Done/Partial/Blocked; file paths; evidence).
3. New or modified routes, APIs, schema/migrations, and dependency manifests.
4. PostgreSQL migration revision and whether applied; existing-data safeguards; seed execution status.
5. Backend/frontend install and startup commands, URLs, dev identities / role switcher instructions (no passwords).
6. Playwright sandbox installation/configuration status and actual browser results, screenshots/trace paths, failed scenarios and fixes; backend test results separately.
7. Documentation update table for all nine canonical files with what changed.
8. Security/permission checks including write-only commission and Admin-only Close.
9. Known limitations and deferred decisions, with no fabricated test success.
10. Explicit recommendation on whether the Receptionist Phase is ready for user acceptance testing.

**Important:** Finish implementation, verification, and document updates in this run. Do not merely produce an audit or plan, and do not launch a different module.
