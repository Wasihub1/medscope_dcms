# Prompt_07C — Safety and Correctness Fixes (from the Prompt 07B verification audit)

You are working on **MedScope DCMS** (React 19 + TypeScript + Vite, FastAPI, PostgreSQL 18, SQLAlchemy 2.x, Alembic).

## 0. Purpose and boundaries

`PROMPT_07B_VERIFICATION_REPORT.md` (read-only audit) found real defects in the Prompt 07 / Prompt 06 code. This prompt fixes **only** the backend safety/correctness group listed in Section 3, plus matching documentation corrections and tests. Everything else found in the audit is deliberately deferred to later prompts (see Section 7).

## 1. Read first (before editing anything)

1. All nine canonical docs: `README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`.
2. `report/PROMPT_07B_VERIFICATION_REPORT.md` and `PROMPT_07_IMPLEMENTATION_REPORT.md` (if present on disk).
3. The actual code named in each fix below. **The code is the truth**; if the audit report and the code disagree, trust the code and say so in your report.

**Working-tree check first.** Run `git status`. The 07B audit output showed many tracked files as *deleted* (e.g. `PROMPT_07_IMPLEMENTATION_REPORT.md`, files under `prompt/` and `report/`). Do **not** restore, delete or move any of them. Just list them in your report under "Working tree observations" so the product owner can decide.

## 2. Hard rules (permanent)

- **No browser testing of any kind** (no Playwright, Selenium, Cypress, Puppeteer, no opening the app in a browser). Never claim browser acceptance; the product owner does that personally.
- Non-browser checks are expected: `pytest`, TypeScript typecheck, lint, build, `alembic check`, DB inspection. Report exactly what you ran and the actual result. Never write "passed" for anything you did not observe.
- **Alembic rule:** any change to a database model/schema definition requires a matching migration with the correct `down_revision` and a **single head**. Current head is `a7d834bc912e` — verify before touching anything. Never reset or destroy data. This prompt is **not expected to change the database schema**; if you find one is unavoidable, follow the rule and explain why.
- **Docs rule:** at the end, update **all nine** canonical docs so they are mutually consistent (if one has no substantive change, verify it and say it was reviewed). `project-context.md` must show the current phase, state, completed work, known limitations and next step. Also write `PROMPT_07C_IMPLEMENTATION_REPORT.md` (in the `report/` folder, like the 07B report).
- Financial amounts are whole-taka integers. Payments, refunds, audit rows, events and snapshots are **append-only**: never rewrite historical rows.
- Preserve accepted workflows and existing data. Keep the development role switcher. Keep secrets out of code, docs and reports.
- Do not start Module 14 or any other module.

## 3. Fixes to implement

### Fix 1 — D15 refund must go through the original payment channel (rules 3.1, D18, M29)
Audit finding V11(c): `disburse_refund` (`backend/app/services/refund_service.py`, around line 495) accepts any `method` from the request body.
- Validate that the disbursement `method` is one of the payment methods actually used on that invoice's recorded payments. Reject otherwise with HTTP 400 and a clear message.
- Non-cash methods require a reference/transaction number (same rule as payments).
- If the invoice was paid through several methods, a method's disbursed total must not exceed what was actually paid through that method (net of earlier disbursements). If the current data model cannot express per-method tracking, implement the strongest safe check you can, and list the gap under **Partial** in your report.
- Cash disbursement must still reduce the drawer/business-day ledger exactly as today. Approval must still **not** mark the invoice refunded; only actual disbursement does.
- Apply the same validation to every code path that can disburse a refund (including any duplicate/alias route, e.g. `/refunds/disburse/{id}` and `/refunds/{id}/disburse`).

### Fix 2 — Segregation of duties on refund approval (rule 3.6, D56)
Audit finding V11(f): `admin_review_refund_request` does not compare the reviewer with the requester.
- Block approval/rejection when `reviewer_id == requested_by_id` (HTTP 403, clear message) and write an audit row recording the blocked attempt.
- Put this logic in **one small, clearly named function** (for example `enforce_segregation_of_duties(...)`) so it can later be switched on/off per customer (D56 "Small center mode"). **Do not** build a settings table or a permission framework in this prompt; only isolate the check in one place.
- Do not change which roles may approve or disburse. Those role lists are intentionally not fixed yet (product owner decision) and will be made configurable later.

### Fix 3 — Culture stage FINAL must not auto-complete the TestOrder (rule D19, M12)
Audit finding V16: `record_culture_stage` (`backend/app/services/worklist_service.py`, around lines 643–649) sets `order.status = "COMPLETED"` when the stage becomes `FINAL`.
- Remove that automatic coupling. Culture stage (Incubating → Preliminary → Final) and TestOrder status must be independent.
- A culture TestOrder may become `COMPLETED` only through the normal completion path (technician marks results entered, per the existing rules), and only after the culture stage is `FINAL`. Enforce that guard in the backend. Choose the minimal path using what already exists (the existing complete action or the narrative result submit) and describe your choice in the report. Do not build a new culture result template.
- Status other than `COMPLETED` for non-final stages must keep working as today.

### Fix 4 — Result-save guards (rules 3.2, D24, M13, B10 state machine)
Audit findings V5 and V10 (`backend/app/services/result_service.py`, `save_test_result`).
- (a) Reject saving/replacing results when the TestOrder is already `COMPLETED` (as well as the existing CANCELLED/REJECTED/SPOILED checks). HTTP 409 with a clear message. Post-completion edits belong to the future Corrections module (M15), not to this endpoint.
- (b) **Saving a DRAFT must not change the TestOrder status.** Remove the draft-time advancement to `IN_PROGRESS`. Submitting (`ENTERED`) keeps its current transitions: `AWAITING_DOCTOR` when doctor interpretation is required; `COMPLETED` for technician-final tests (scope: "Completed = technician marked results entered"); otherwise `IN_PROGRESS`. Do **not** implement Draft→Final/report publishing (that is Module 14).
- (c) For **sample-based** tests, saving or submitting a result before the sample has been taken (Sample Taken/line lock) must be rejected with HTTP 409. Determine "sample-based" from the test catalog's existing sample-requirement field; no-sample tests (e.g., imaging/ultrasound) are not affected. If the current flow intentionally allows entry earlier, do not change it — report it under **Partial** with your reasoning.
- Re-saving a DRAFT (before submission) may continue to replace the draft items.

### Fix 5 — Technician financial isolation (rule M11.3, 3.8: technicians never see money)
Audit finding V19.
- `POST /api/v1/worklist/{id}/d15-refund-request` currently returns `RefundRequestResponse` containing `amount`. Return a clinical-only response for LAB_TECH callers (no amount, no price, no refund value). Admin/Owner/Receptionist views of refund requests remain unchanged.
- The test-order events timeline (`GET /api/v1/worklist/{id}/events`) must not expose monetary amounts to LAB_TECH. For **new** events, keep the technician-facing description amount-free and store any amount in a structured/admin-only place (audit log). For **existing** event rows, do **not** modify history (append-only); instead sanitize at read time for LAB_TECH. Admin/Owner may still see amounts.
- Then scan **every** endpoint a LAB_TECH can call (worklist list/detail, result-template, result save, sample taken, reject-sample, patient-contact, culture-stage, imaging-performed, status, events, d15 request) and list in your report any remaining financial field in a response. Fix what you find within this scope; report anything you cannot fix.

### Fix 6 — Align ORM models with the existing migration (Alembic)
Audit finding V1: `alembic check` fails on `backend/app/models/result.py` — `ResultItem.result_id` lacks `ondelete="CASCADE"`, and `Result.test_order_id` is declared `unique=True, index=True` while migration `a7d834bc912e` created a named unique constraint `uq_results_test_order_id`.
- Fix the **models** so they match the already-applied migration. Do **not** change the live database and do **not** add a new migration unless you prove it is the only correct option (then follow the Alembic rule and explain).
- Required end state: `alembic heads` shows the single head `a7d834bc912e`, `alembic current` equals the head, and `alembic check` reports no new operations. Report the actual outputs.

### Fix 7 — Test suite honesty (audit finding V22)
`pytest tests` gave 20 failed / 8 passed when no backend server was running, because older integration tests call `127.0.0.1:8000`.
- Preferred: make those tests run in-process (FastAPI `TestClient` / ASGI transport) if that is feasible without a large rewrite.
- Otherwise: mark them with a clear marker (for example `requires_server`) so that, with no server, they are reported as skipped with an explicit message rather than failing mysteriously, and document exactly how to run them with a live server.
- Add new automated tests for Fixes 1–5 (original-channel rejection, self-approval block, culture FINAL not completing the order, draft not advancing status, COMPLETED re-save rejected, technician response/event contains no amounts).
- Report the real numbers for: (i) full run with no server, and (ii) full run with a live local server (you may start the backend yourself; this is not browser testing).

### Fix 8 — Documentation corrections (all nine docs)
Correct the following known inaccuracies and keep all nine docs consistent:
- **API endpoint count.** Docs claim "46"; FastAPI actually registers 62 paths / 72 operations (including alias duplicates). Recompute from `app.openapi()`, state the method used, and note the alias duplicates.
- **Table count.** `docs/DATABASE.md` says "21 Domain Entities"; the ORM has 25 domain tables (26 in PostgreSQL including `alembic_version`). Fix the heading and list.
- Remove any claim of "delta comparisons" or a "clinical history" narrative field (neither exists; delta is excluded by D25).
- The Prompt 07 report/docs mention `backend/scripts/seed_components.py`; that file does not exist. The component seed currently runs just-in-time inside the result-template fetch in `result_service.py`. Document this truthfully as a known limitation (a GET with a side effect) and mark a proper seed script as deferred. Do not change the seed values.
- Record the product-owner decisions in `docs/SCOPE.md` and `docs/ARCHITECTURE.md` (ADL):
  1. Automatic LOW/HIGH/CRITICAL/NORMAL result flags are **kept**; the earlier "flags dropped from V1" wording is superseded. Technicians **cannot** select or override the flag (decided); the scope's earlier "technician types any flag" wording is superseded. Automatic critical-result *alerts* remain excluded.
  2. Day open/close roles and who may physically disburse an approved refund are **not fixed**: current behavior is a development-stage setting; they will be configurable per customer. Only Admin/Owner approve refunds.
  3. Design direction: a single central, configurable role-permission layer is planned; role checks are currently scattered (see audit V18).
  4. Self-approval of refunds is blocked by default (Fix 2) and isolated in one function so it can become a per-customer setting (D56).
- `docs/TESTING.md`: state which tests need a live server, how to run each group, and the **actual** counts from Fix 7. Do not copy the old "28 passed in 2.45s" claim unless you reproduce it.

## 4. Must NOT do

- No browser testing; no claim of browser acceptance.
- No Module 14 (Draft→Final / report publishing), no QR, no SMS, no full stock module, no offline work.
- **Not in this prompt:** reference-range versioning by sex/age band (D24), barcode direct-open, invoice auto-refresh, imaging lock-timing change, owner same-day unlock (D14), a configurable permission layer/settings table. Do not start any of these, even partially.
- Do not change which roles may open/close the business day, approve, or disburse refunds.
- Do not change the seeded clinical values, ranges or limits. Do not invent clinical thresholds.
- Do not rewrite or delete historical rows (events, audit, payments, results). Do not reset the database.
- Do not remove duplicate/alias routes; only document them.
- Do not restore, delete or move files shown as deleted in `git status`; only report them.
- Do not expose secrets.

## 5. Acceptance-style checks you must run and report (non-browser)

`alembic heads`, `alembic current`, `alembic check`; `python -m py_compile` on every changed Python file; TypeScript typecheck (`tsc -b`); lint (state errors and warning count); frontend build; full `pytest` (with and without a live server, per Fix 7). Quote real outputs and counts.

## 6. Report — `PROMPT_07C_IMPLEMENTATION_REPORT.md`

Sections: (1) Summary table Fix 1–8 with status **Done / Partial / Blocked / Deferred**; (2) per-fix detail: files changed, behavior before → after, rule numbers; (3) migration/head status (state clearly whether any migration was created); (4) API changes and any changed responses/permissions; (5) tests added and actual results; (6) docs updated (all nine, one line each); (7) Working tree observations (the deleted-files list); (8) remaining limitations and anything you could not verify; (9) explicit statement that no browser testing was performed.

## 7. Deferred to later prompts (do not touch now)

Reference-range versioning by sex/age (D24); barcode scan direct-open (M11.4); invoice view auto-refresh; imaging lock at result completion plus the started-not-completed cancellation path and owner unlock (D13/D14); central configurable permission layer; Module 14.
