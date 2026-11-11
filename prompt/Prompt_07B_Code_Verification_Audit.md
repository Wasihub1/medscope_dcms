# Prompt_07B — Read-Only Code Verification Audit of Prompt 07 (Module 13 + Module 12 fixes)

You are working on **MedScope DCMS** (React 19 + TypeScript + Vite, FastAPI, PostgreSQL 18, SQLAlchemy 2.x, Alembic).

## 0. Nature of this task

This is a **read-only verification audit**. You must **not change any source code, migration, seed, configuration or documentation**. The only file you create is the report `PROMPT_07B_VERIFICATION_REPORT.md` in the repository root.

Purpose: the Prompt 07 report (`PROMPT_07_IMPLEMENTATION_REPORT.md`) makes claims that have not been independently verified. The product owner will do browser acceptance personally. Before that, we need an evidence-based list of what is actually true in the code, so that narrow fix prompts can be written afterwards.

## 1. Read first

1. All nine canonical docs: `README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`.
2. `PROMPT_07_IMPLEMENTATION_REPORT.md` and, if present, the Prompt 05 and Prompt 06 reports.
3. The actual code: backend models, routers, services, schemas, Alembic versions, seed scripts; frontend pages, API clients, hooks, components.

Where the docs and the code disagree, **the code is the truth**; record the disagreement.

## 2. Hard rules

- **No browser testing of any kind.** No Playwright, Selenium, Cypress, Puppeteer, no opening the app in a browser. Do not claim browser acceptance.
- **No code, migration, seed, config or doc edits.** No `alembic revision`, no `alembic upgrade/downgrade`, no seed execution, no formatting/auto-fix runs that modify files.
- Database access, if used, must be **read-only** (SELECT / schema inspection only). Never reset, truncate or modify data.
- Do not print or copy secrets, passwords, tokens or `.env` values into the report.
- Do not start Module 14 or any other new module.
- Never write PASS for something you did not actually observe in code or command output. If you cannot determine something, write **UNABLE TO DETERMINE** and say why.
- Allowed non-browser commands (they must not modify tracked files): `alembic heads`, `alembic current`, `alembic history`, `alembic check` (if supported), `pytest`, `tsc -b` / `tsc --noEmit`, the project linter in check-only mode, `grep`/search, `git status`/`git diff` (read-only). If a command writes files (e.g. build output, caches), say so and make sure no tracked file changed (`git status` before and after).

## 3. Context decisions from the product owner (do not "fix", only report facts)

- Automatic LOW/HIGH/CRITICAL/NORMAL result flags are **kept**. Verify the technician can select/override the flag.
- Role permissions for day open/close and for who may physically disburse a refund are **not fixed**; they are development-stage settings and will be configured per customer. Only Admin/Owner **approve** refunds; after approval, any permitted role may disburse. Therefore Section V18 asks you to **inventory** where roles are hard-coded, not to change them.
- Previous-result / delta comparison is **excluded from V1** (rule D25).
- QR authenticity, full stock management (Module 16), Draft-to-Final (Module 14), automatic critical alerts and offline architecture are **out of scope** for the current code state.

## 4. Verification checklist

For **each** item V1–V22, record: **Status** (PASS / PARTIAL / FAIL / UNABLE TO DETERMINE), **Evidence** (file path + function/class + line range, or exact command output), **Finding** (one or two sentences), **Severity** if not PASS (Blocker / High / Medium / Low). Keep findings factual.

**V1 — Alembic chain (rule: single head, correct down_revision).** Output of `alembic heads`, `alembic current`, and the ordered revision chain from base to head. State: number of heads, whether `a7d834bc912e` is the single head, whether `down_revision` links are contiguous (including the revisions between `c94589ffc4ee` and `f16c024d3e4a`), and whether the database revision equals the head. If `alembic check` is available, report whether models and migrations are in sync (any pending autogenerate diff).

**V2 — Docs vs code counts.** Count real tables and real API endpoints from code. Compare with the "26 tables" and "46 endpoints" claims in docs/report. List mismatches.

**V3 — Delta / previous-result comparison (D25).** Search backend and frontend for any delta, "previous result", "last result", trend or comparison logic in result entry. State whether anything exists and where. (Report only; do not remove.)

**V4 — Reference ranges (M5, D24).** Describe the real schema of `test_components` and any range table. Does it support ranges versioned by **sex and age band in days**, with a version/effective date? Or only a single `ref_min/ref_max` per component? How is a range chosen at result time (patient sex/age used or not)? Is there a `reference_range_version`-like table?

**V5 — Range snapshot in results (3.2, D24).** Which fields does `result_items` snapshot (component name, unit, normal range, critical limits, flag)? Is the snapshot immutable (no update path)? If a `test_components` row is edited later, does an existing saved result change? Show the code path.

**V6 — Automatic flags.** How are LOW/HIGH/CRITICAL/NORMAL computed (where, which fields)? Is the flag stored on the result item? Can the technician select or override the flag in UI and API, and is an override stored/audited? Confirm there is **no** automatic critical alert/notification.

**V7 — Impossible-value validation.** Where and how enforced (backend)? Confirm the Hemoglobin 150 example is rejected. What HTTP status and message? Are limits per component and configurable?

**V8 — Narrative template.** List the exact fields. Scope requires **findings, impression and comments**. Are all three present? Are extra fields (clinical history, technique) additive or replacing required ones?

**V9 — Ultrasound template.** Describe the structure (JSONB shape), organ list, and whether it still passes through the same result/status rules.

**V10 — Result status vs TestOrder status.** Document the actual state machine: Result DRAFT/ENTERED vs TestOrder statuses. Confirm: saving a draft does not advance the TestOrder; submitting transitions to IN_PROGRESS or AWAITING_DOCTOR (state the exact condition); nothing publishes a final report; Technician "Complete" semantics. List any endpoint that could set a TestOrder to COMPLETED and under which conditions.

**V11 — D15 lifecycle and guards (D15, 3.3, M29).** Trace the full chain in code: reject/spoil → `outcome = NOT_PERFORMED` → request (`D15_NOT_PERFORMED`, `PENDING_ADMIN_APPROVAL`) → approve/reject → `REFUND_APPROVED` → disburse. For each step list: endpoint, allowed roles (as coded), state change, audit row written. Confirm: (a) approval does not mark the invoice refunded; (b) disbursement records method/reference, staff, time; (c) refund uses the **original payment channel** (is the original channel enforced or just free text?); (d) commission reversal uses the **original line snapshot** (show where); (e) consumed stock is not restored; (f) the requester cannot approve their own request (enforced or not); (g) invoice refund status is derived from actual disbursement records; (h) generic pre-sample "Initiate Refund" is blocked for locked/D15 lines in both backend and UI.

**V12 — Invoice sample status auto-refresh.** From the frontend code, explain exactly how the Invoice View gets updated after Sample Taken/Collected is performed in the worklist (query invalidation, refetch, polling, shared store, event, or only on full reload). Static reading only. State clearly whether an already-open invoice view would update without page reload.

**V13 — Stat Urgent badge.** Show the exact condition. Confirm it disappears only when TestOrder status is exactly `COMPLETED`, and stays through SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, REJECTED, SPOILED.

**V14 — Line Locked badge.** Confirm the badge is removed from the Technician Worklist UI and that backend `InvoiceLine.is_locked` and lock/refund protections are intact. Is the badge still shown anywhere else (e.g., invoice view) and is that intended?

**V15 — Imaging lock timing (D13, 3.3).** At which event is an imaging (no-sample) line locked in code (`IMAGING_PERFORMED`, result submit, or completion)? Scope says lock at **result completion**. Is there any admin/owner cancellation path for "imaging started but not completed" with wastage logging? Is there an owner same-business-day unlock (D14)? (Existence only.)

**V16 — Culture lifecycle.** Confirm culture stage `FINAL` is kept separate from TestOrder `COMPLETED`. Show where each is set and whether one can set the other.

**V17 — Barcode scan (M11.4).** Does scanning/entering a barcode **resolve and open the matching task directly**, or only filter the worklist list? Show the code path and the endpoint used.

**V18 — Hard-coded role checks inventory.** Produce a table of every place where roles are hard-coded in backend and frontend, with columns: file, function/route, action protected, roles allowed as coded. Cover at least: business-day open/close, refund request/approve/reject/disburse, D15 request, result entry/submit, sample taken, reassignment, invoice cancel/refund initiation, price/catalog edit, referrer rate visibility. Then state whether a central permission layer already exists (single mapping/settings table) or whether checks are scattered. **Report only; do not change.** This feeds a later prompt to make permissions configurable per customer.

**V19 — Technician financial redaction.** Inspect the response schemas of every endpoint a LAB_TECH can call (worklist list/detail, result-template, result POST, sample actions, D15 request). List any financial field (price, due, payment, discount, commission, refund amount, cost price) that can appear in those responses. Confirm none, or list them.

**V20 — Invoice Payment Status dropdown.** Report the **current** choices and filter semantics exactly as implemented (the owner changed this manually after Prompt 04). Read only; do not modify. Check whether docs describe it correctly.

**V21 — Seed data.** List the 26 seeded components (names, units, ranges, critical and physiological limits) in a table. Confirm the seed is tenant-scoped (`center-seba-01`), idempotent, and **not** run automatically on app start. Note in the report that these values are development/demo configuration and require clinical sign-off before real use. Do not judge or alter the clinical values.

**V22 — Non-browser validation (actually run, report actual output).** Run and report result and counts: `pytest` (full backend suite), TypeScript typecheck, linter (check-only), frontend build if it does not modify tracked files. Record exact pass/fail numbers. If any command fails, include the first relevant error lines. Do not fix failures.

## 5. Report format — `PROMPT_07B_VERIFICATION_REPORT.md`

1. **Summary table:** V1–V22 with Status and Severity.
2. **Detailed findings** per item (Status, Evidence, Finding, Severity).
3. **Docs-vs-code disagreements** (list: doc, claim, reality).
4. **Scope-rule conflicts found** (rule number, what code does, what scope says).
5. **Proposed narrow fix groups** (names only, no code): e.g. "Fix group A — …". Group related findings; mark each Blocker/High/Medium/Low. Do not implement them.
6. **Commands run** (exact command, working directory, outcome).
7. **Explicit statement** that no source, migration, seed, config or documentation file was modified, and that no browser testing was performed. Include `git status` output showing only the new report file as changed/untracked.

## 6. Do NOT do

- Do not modify code, migrations, seeds, config or the nine canonical docs.
- Do not run browser tests or open the app in a browser.
- Do not start Module 14 or any other module.
- Do not remove or "clean up" anything you find (delta comparison, role checks, etc.); only report.
- Do not claim anything passed that you did not observe.
- Do not expose secrets.
