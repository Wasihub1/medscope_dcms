# Prompt_08 — Modal/Tab Bug Fix, Test Database Isolation and Test-Record Identification

You are working on **MedScope DCMS** (React 19 + TypeScript + Vite, FastAPI, PostgreSQL 18, SQLAlchemy 2.x, Alembic).

This prompt has three independent parts. Do them in order and report each one separately (Done / Partial / Blocked / Deferred per part):
- **Part A:** fix the bug where opening a modal switches the underlying tab to Patients (frontend).
- **Part B:** make automated tests use a separate database so they never write to the main database.
- **Part C:** identify (read-only, no deletion) the fake records that earlier test runs created in the main database.

Why B and C: tests currently run against the same PostgreSQL database the product owner uses (`medscope_dcms`), so fake patients, invoices, test orders, refunds and ledger rows are mixed with real QA data.

# PART A — The modal / tab bug (reported by the product owner)

When a modal/detail view is opened from a menu tab (example: Invoices tab → click **View** on an invoice), the modal opens but the **background silently switches to the Patients tab**. The same behavior happens in other places. Closing the modal should leave the user on the tab they were on, with the same filters/scroll/selection.

### A2. Tasks

1. **Audit every modal / drawer / detail-view opener** in the frontend (invoice view, patient detail, refund modals, worklist detail, sample/barcode modal, result entry modal, payment modal, etc.). Produce an inventory table: file, component, trigger, route/tab **before** opening, route/tab **after** opening, whether the bug reproduces.
2. **Find the root cause(s).** Look first at the central pieces: how the active tab/page is stored (state, context, router), how modals are rendered (global modal host, portals, shared layout), and any code that sets the active tab/route when a modal opens (for example a `setActiveTab('patients')`, a navigation call, a router `navigate`, a key/remount of the page, or modal data tied to the Patients page). Explain the cause in plain words in the report.
3. **Fix it centrally** so that opening or closing any modal/drawer **never changes the underlying page/tab**, and the underlying page keeps its state (filters, pagination, scroll, selection). Prefer fixing the single shared cause over patching each screen. Do not swap the routing approach unless the root cause truly requires it; if you must, explain why in an ADL entry.
4. **Regression protection.** Add automated tests so this cannot return silently (see Section 3).
5. Keep behavior of everything else unchanged. No redesign, no new features.

### A3. Limited browser-testing exception (Part A only)

For this Part A bug **only**, you **may** use Playwright (Chromium) to (a) reproduce the bug before the fix (record the failing result), and (b) add regression specs that pass after the fix.
- Playwright specs must be **read-only**: open tabs and open/close modals only. They must not create, edit or delete any data (no invoices, patients, payments, refunds, samples, results).
- Put the role/sign-in step used by the specs behind **one helper function** (the app currently has a development role switcher that will be replaced by real login in a later prompt).
- Do not use Playwright for anything else, and do not claim acceptance. Record this exception and its scope in `docs/TESTING.md`.
- Also add non-browser tests where practical (for example unit/component tests for the modal host and tab state).

### A4. Must NOT do

- No new features, no UI redesign, no change to business logic or backend behavior (change the backend only if the root cause is proven to be there, and say so).
- No authentication, login page, soft delete, or any other upcoming work.
- Playwright must not write data. Do not use Playwright beyond this bug.
- Do not remove the development role switcher in this prompt.

### A5. Report extras

Include: the inventory table (Section A2.1), root cause, what changed, which modals were affected, the Playwright failing-before and passing-after evidence (exact command and result), and anything you could not reproduce.

# PART B — Test database isolation (so tests never write to the main database)

1. Configure tests to use a **separate database** (for example `medscope_test`), selected through an environment variable (for example `TEST_DATABASE_URL`). Never hard-code credentials.
2. Add a **hard guard**: the test session must **refuse to start** (clear error) if the test database URL equals, or resolves to the same database as, the development/main database URL.
3. At test-session start, create the schema in the test database by running the Alembic chain from base to head (this also proves the full migration chain works on an empty database). Report any chain problem you find.
4. Provide a deterministic **test seed fixture** with the minimum baseline data the tests need (tenant `center-seba-01`, staff/roles, test catalog and test components, price list, whatever the existing tests rely on). Find out what the tests depend on by reading them; do not invent business data beyond what tests need. Test data must be clearly marked as test data.
5. Tests must run **in-process** against the test database. The old "live server on port 8000" mode must either be removed or guarded so that it can only run against a server explicitly pointed at the test database. Remove any path where pytest can write to the main database.
6. If the database user lacks the right to create a database, report **Blocked** for that step with the exact command/action the owner must run, and still deliver everything else.
7. Run the full suite against the test database and report the real counts. Update `docs/TESTING.md` with how to configure and run it.

# PART C — Identify test-created records in the main database (READ-ONLY)

**Do not delete, update or insert anything in the main database.** Use SELECT/schema inspection only.

1. Take a backup first if `pg_dump` is available: write it to a **git-ignored** folder (add the folder to `.gitignore`), never commit it, never print its contents. Report the path and size only. If you cannot take a backup, say so.
2. Find candidate test-created records using evidence, not guesses: names/mobile numbers/references that the existing test files create (read the tests to learn the patterns), timestamps clustered around pytest runs, audit rows, records tied to test-only orders. Cover at least: patients, visits, invoices and invoice lines, payments, refund requests and disbursements, test orders and events, samples and sample events, results and result items, drawer/ledger entries, commission entries, audit logs, referrers or other master data created by tests.
3. Produce `report/TEST_RECORD_CANDIDATES.md` with, per entity: table name, row ids, key fields, created time, **why it matched**, and **confidence (High / Medium / Low)**. Separate High-confidence rows from uncertain ones. The owner will review this list.
4. Produce a **dependency map**: for the candidate rows, which other rows reference them (payments, ledger, audit, test orders, samples, results, commission, counters), and the safe deletion **order**. Note the effect on: the active/closed business-day cash totals, invoice/bill number counters (gapless numbering), dashboard figures, and any append-only rule that a deletion would touch.
5. Write a **draft cleanup plan** (ordered steps, expected row counts per table) but **do not execute it**. The owner will review the list and then ask for a separate deletion prompt.

# Must NOT do (Parts B and C)

- **No deletion, update or insert in the main database.** Do not run any cleanup.
- No browser testing. No new product features. No authentication work.
- Do not change the schema of the product (a test-only database is not a product schema change; if the Alembic chain needs a fix to run from base, explain it first in the report and only fix what is strictly required, following the Alembic rule).
- Do not touch the owner's QA data.

## Report extras

Per part: Part A — the inventory table (A2.1), root cause, what changed, Playwright failing-before and passing-after evidence (exact command and result). Part B — how to configure/run, guard behavior, real test counts, any Blocked step with the exact owner action. Part C — path to `report/TEST_RECORD_CANDIDATES.md` and the backup path/size (not contents).

## Permanent project rules (apply to this prompt)

1. **Inspect first.** Read all nine canonical docs (`README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`) and the actual code you will touch. **The code is the truth.** If a doc disagrees with the code, say so in your report and correct the doc.
2. **Browser testing is prohibited** (no Playwright, Selenium, Cypress, Puppeteer, no opening the app in a browser), **except where this prompt explicitly grants a narrow exception**. Never claim browser acceptance; the product owner performs acceptance personally.
3. **Non-browser checks are expected:** `pytest`, TypeScript typecheck (`tsc -b`), lint, build, `alembic heads/current/check`, read-only DB inspection. Report exactly what you ran and the real output. Never write "passed" for anything you did not observe.
4. **Alembic rule.** Any change to a database model/schema requires a matching migration with the correct `down_revision` and a **single head**. Verify the current head before creating anything (last reported head: `a7d834bc912e`; later prompts may have moved it). Never reset, truncate or destroy existing data. If a migration cannot be applied, still create/review it and state the exact remaining action.
5. **Docs rule.** At the end, update **all nine** canonical docs so they are mutually consistent and match the code. If one has no substantive change, verify it and record that it was reviewed. Record every decision from this prompt in the right docs (SCOPE.md for business rules, ARCHITECTURE.md ADL for technical decisions, DATABASE.md, API.md, WORKFLOWS.md, DESIGN.md, TESTING.md). `project-context.md` must show current phase, state, completed work, known limitations, next step. Before finishing, **audit the docs you touched against the code** and fix mismatches.
6. **Report.** Write `report/PROMPT_08_IMPLEMENTATION_REPORT.md` with: Done / Partial / Blocked / Deferred table, files changed, migration/head status (say clearly if no migration was created), API and permission changes, tests added and their **actual** results, docs updated (one line each), remaining limitations, and an explicit statement about browser testing.
7. **Business rules to protect:** whole-taka integer money; payments, refunds, stock, audit, events, results and snapshots are append-only (never rewrite history); technicians never see financial data; keep accepted workflows and existing data.
8. **Owner decisions in force:** automatic LOW/HIGH/CRITICAL/NORMAL result flags are kept and technicians cannot override them; who may open/close the business day and who may physically disburse an approved refund are **not fixed** and will become configurable per customer later (do not change them now); only Admin/Owner approve refunds; self-approval of refunds is blocked by default.
9. **Working tree.** `git status` has previously shown ~15 tracked files as deleted (old prompt/report files and `DCMS Final Scope V1.docx`). Do **not** restore, delete or move them; just list them in the report.
10. **Never** put secrets, passwords or tokens in code, docs, reports, prompts or logs. Do not start any phase or module other than the one in this prompt.
