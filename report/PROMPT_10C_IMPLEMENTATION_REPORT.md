# Prompt 10C — Docs vs Code Mismatch Fix: Implementation Report

- **Date:** 2026-11-13
- **Base commit:** `a6c0243` (branch `main`)
- **Scope:** documentation only. No product code, tests, e2e specs, migrations, configuration, `.gitignore` or database changed. No SQL scripts were run. No `alembic upgrade/downgrade`. No browser or Playwright runs.
- **Input:** `report/FULL_AUDIT_REPORT_2026-11-12.md`. I re-checked every item against the code before editing.

## 1. Summary

| Area | Status |
|---|---|
| Part A: 9 corrections | **Done** (9/9 verified in code and fixed) |
| Part B: owner decisions recorded | **Done** (ADL-032 to ADL-037, plus SCOPE §5, WORKFLOWS §6 and notes in API, DESIGN, README, project-context) |
| Part B: pre-go-live cleanup list | **Done** (`docs/TESTING.md` §12; paths only, no values; not acted on) |
| Part C: consistency sweep | **Done** (5 extra mismatches found and fixed, see §4) |
| Non-browser checks | **Done** (all pass, see §5) |
| Spec fixes, D15 code fix, invoice Draft/Finalize, role changes | **Deferred** (out of scope by design) |

## 2. Part A — Per-item verdicts

| # | Item | Code evidence checked | Verdict | Docs changed |
|---|---|---|---|---|
| 1 | Narrative result fields | `backend/app/models/result.py:26-28` and `backend/app/schemas/result.py:42-44,74-76` have `findings`, `impression`, `comments`. No `technique`/`recommendations` in `backend/app` or `frontend/src`. | **Fixed.** Wrong field list found in 3 docs, not just DESIGN. | `docs/DESIGN.md` (§ narrative template), `docs/SCOPE.md` §4.11, `project-context.md` (Prompt 07 section). Also `docs/ARCHITECTURE.md` ADL-018 ("findings/impression" → "Findings, Impression, Comments"). |
| 2 | Reduced-motion claim | `grep` for `reduced-motion`/`prefers-reduced`/`matchMedia` in `frontend/src` gives **0 hits**. Removal reason confirmed in the Prompt 10 report §9 (read from git `HEAD`, since the file is deleted in the working tree). | **Fixed.** Now states the fallback was intentionally removed and the owner's "Pause animations" decision is still open. Code not touched. | `docs/SCOPE.md` §4.16, `docs/ARCHITECTURE.md` ADL-031, `docs/DESIGN.md` §13.3, `project-context.md` (Prompt 10 section) |
| 3 | Role-switcher wording | `selectDevRole` is defined only in `frontend/e2e/test_modal_regression.spec.ts:7` and is a login helper. No switcher code in `frontend/src` or `backend/app`. | **Fixed.** Described as a login helper with a stale name. | `docs/TESTING.md` §7.1, `project-context.md` (Prompt 08 section). Prompt 05 history line marked "removed in Prompt 09". |
| 4 | Playwright modal regression status | Spec fills `#username`/`#password` (lines 10-11). `LoginPage.tsx` uses `id="user"` / `id="pass"` (`data-testid` `login-username`/`login-password`). Stale comment at `receptionist_corrections.spec.ts:43` confirmed. Spec **not re-run** (no browser testing allowed). The 0/6 result comes from the audit. | **Fixed.** Recorded as "currently failing, selector update pending". The old "6 passed" is kept only as a labelled historical Prompt 08 result. Stale comment documented; spec not edited. | `docs/TESTING.md` §2 (status note), §7.1, §11; `project-context.md`; `docs/ARCHITECTURE.md` directory layout; `README.md` |
| 5 | Table count | 27 `__tablename__` entries in `backend/app/models`. `alembic check` shows no drift, so 27 domain tables + `alembic_version` = 28. | **Fixed.** The "25 domain + 1 = 26" line was accurate *at Prompt 07C* (Prompt 09 later added `staff_roles` and `auth_sessions`). It is now labelled as the 07C figure, with the current 27/28 stated beside it. | `project-context.md` (07C "Current State"), `docs/ARCHITECTURE.md` (stack diagram said "25 Domain Tbl") |
| 6 | Volatile data counts | Not verifiable from code; dev data changes constantly. | **Fixed.** Removed or generalized "223 invoices", the "16 patients / 16 referrers / 14 invoices" assertions, the Prompt 10B per-table candidate/remaining table, the drawer Taka figures, and "invoice count unchanged at 223". Prompt 08 forensic counts are marked as a historical snapshot. A general "dev/QA data; counts vary" note was added to DATABASE.md §1. Structural facts were kept. | `project-context.md`, `docs/DATABASE.md` §1, §6.2, §7.2, §7.4, §7.5, `docs/TESTING.md` §8.1, §10.2 |
| 7 | Cleanup script status | File exists locally (`backend/scripts/sql/cleanup_test_data.sql`). It is git-ignored by `.gitignore:75` (`*.sql`) and ends with `ROLLBACK;` / `-- COMMIT;`. I did **not** query the DB; execution evidence (audit_logs id 826, `TEST_DATA_CLEANUP`, 2026-11-11) comes from the audit report. | **Fixed.** Now says executed and committed by the owner on 2026-11-11 (audit id 826). It is a dev/testing utility only: not schema, not Alembic, not a product feature. Git-ignored, local only. Explicitly *not* claimed to be identical to the executed copy. Past `report/` files not edited. | `docs/DATABASE.md` new §7.0 + §7.4/7.5, `docs/TESTING.md` §10.1, `project-context.md` (10B section), `docs/ARCHITECTURE.md` directory layout |
| 8 | Alembic / schema policy | `alembic heads` gives a single head, `b9e41d82f05a`. | **Fixed.** One policy statement added: DDL only via Alembic migrations, the head is the single source of truth, and seed/cleanup scripts are outside the chain. | `docs/DATABASE.md` §1, `docs/ARCHITECTURE.md` new §5 (+ ADL-037), echoed in `README.md` |
| 9 | D15 refund wording | `refund_service.py:416-418` has `invoice.refund_due += line.net_price` / `invoice.net -= line.net_price` (floored at 0). Request amount defaults to `net_price` (line 312). | **Fixed.** Docs now give the intended rule (refund ≤ amount actually paid) and a clearly labelled **"Known issue — to be fixed"** note on current behavior. The buggy behavior is not documented as the rule. | `docs/API.md` §2.10, `docs/ARCHITECTURE.md` ADL-019 (+ ADL-036), `docs/WORKFLOWS.md` §2, `docs/SCOPE.md` §5, `project-context.md` |

No item turned out to be already correct. All nine mismatches were real.

## 3. Part B — Owner decisions recorded (all labelled "Decided — not yet implemented")

ADL numbering continues from the last entry (ADL-031) in `docs/ARCHITECTURE.md`:

| ADL | Decision | Also recorded in |
|---|---|---|
| ADL-032 | One login = one fixed role; no acting-role switching. Supersedes ADL-028 (which is marked superseded but is still the implemented behavior). The header switcher is to be removed later. | SCOPE §5, WORKFLOWS §5.3 / §6, DESIGN §5.1 note, API `/auth/acting-role` row, README, project-context |
| ADL-033 | Every login lands on the Dashboard. Supersedes the per-role home routes (ADL-030 marked accordingly). | SCOPE §5, WORKFLOWS §6, README, project-context |
| ADL-034 | More roles/users (Owner, Cashier, others); one default LAB_TECH per lab section/room; a "Create User" tab with role assignment and per-user permission add/remove, as the first step of the central permission layer. Notes that CASHIER only shares the receptionist gate (`backend/app/core/security.py:83`, `backend/app/services/auth_service.py:76`). | SCOPE §2 Cashier row + §5, WORKFLOWS §6, README, project-context |
| ADL-035 | Invoice "Save Draft" (keeps Draft, where the "Unsaved Draft" tag is) plus a separate "Finalize" (replaces "Save Invoice"). Today saving finalizes immediately (`DualCopyInvoiceModal.tsx`, `POST /api/v1/invoices`). | SCOPE §5, WORKFLOWS §6, API §2.7, project-context |
| ADL-036 | D15 refund amount capped at what was actually paid (fix in a later prompt). | API §2.10, WORKFLOWS, SCOPE §5 |
| ADL-037 | Work order: Prompt 10B related work first, then Prompt 11 (soft delete/deactivate with confirm dialogs). Plus the schema policy (§5). | SCOPE §5, WORKFLOWS §6, project-context |
| — | **Pre-go-live cleanup list** (hard-coded credentials and connection strings, password rotation, removal of the main-DB fallback in `tests/conftest.py`, replacement of hard-coded test passwords). Paths only. | `docs/TESTING.md` §12, pointer in `README.md` |

The current-behavior sections were left describing what the code does today.

## 4. Part C — Extra mismatches found and fixed

| # | Doc / location | Was | Actual (evidence) | Fix |
|---|---|---|---|---|
| E1 | `docs/ARCHITECTURE.md` §1 and stack diagram; `README.md` §5 | 62 paths / 72 operations, 12 or 14 modules | OpenAPI: **69 paths / 79 operations**; 15 endpoint modules in `backend/app/api/v1/endpoints/` | Updated to 69/79, 15 modules |
| E2 | `docs/ARCHITECTURE.md` stack diagram; `docs/WORKFLOWS.md` §2 wiring matrix | "Dev Staff Switcher" (`X-Staff-Id`/`X-Staff-Role`) | Removed in Prompt 09; header has a user menu with `POST /auth/acting-role` and logout | Replaced with the current user-menu rows |
| E3 | `README.md` staff table; `project-context.md` (Prompt 09) | Admin/Owner landing `/` | `getRoleHomeRoute` in `frontend/src/utils/navigation.ts` returns `/dashboard` | Changed to `/dashboard` |
| E4 | `docs/WORKFLOWS.md` disbursement row | Channels `ROCKET`, `CARD` | `schemas/refund.py`: `CASH, BKASH, NAGAD, POS_CARD, BANK_TRANSFER`, restricted to channels used on the invoice | Corrected the channel list |
| E5 | `docs/DATABASE.md` §2 `staff_roles` / `auth_sessions` | `staff_roles`: `tenant_id`, `assigned_at`, `assigned_by_id`. `auth_sessions`: `last_activity_at`, `is_revoked`, `revoked_by_id`, `revocation_reason` | `backend/app/models/user.py`: `staff_roles` = `id, staff_id, role, is_primary, created_at`. `auth_sessions` = `id, session_token_hash, staff_id, tenant_id, acting_role, created_at, expires_at, last_seen_at, revoked_at, user_agent, ip_address`. `alembic check` shows the model matches the DB. | Column lists corrected |
| E6 | `docs/ARCHITECTURE.md` directory layout | 2 migration ids, "21 models", 1 e2e spec, 2 test modules | 7 migration files, 27 tables, 2 e2e specs, 5 test modules + `conftest.py` | Layout updated |
| E7 | `docs/TESTING.md` §3 | Lists 2 test modules | 5 test modules (45 tests) | Module list updated |

Cheap facts that were checked and already matched: Alembic head `b9e41d82f05a` (single head), 28 tables / 27 domain (DATABASE.md, README), role names (`OWNER`, `ADMIN`, `RECEPTIONIST`, `CASHIER`, `LAB_TECH`), route names `/`, `/login`, `/dashboard`, `/invoices`, `/worklist`, and the test-DB guard in `tests/conftest.py`.

Note on the prompt's path: the prompt says `backend/tests/conftest.py`, but the repo has **`tests/conftest.py`** (no `backend/tests/`). The docs use the real path.

## 5. Command results (real, run 2026-11-13)

| Command | Result |
|---|---|
| `python -m alembic -c backend/alembic.ini heads` | `b9e41d82f05a (head)`, a single head |
| `python -m alembic -c backend/alembic.ini check` | `No new upgrade operations detected.` |
| OpenAPI introspection (`app.openapi()`) | 69 paths, 79 operations |
| `python -m pytest -q` | **45 passed, 5 warnings in 5.25s**. Target database resolved to `medscope_test` (checked by name only). The warnings are `PytestCollectionWarning` on ORM classes named `Test*`. |
| `git diff --stat` | Only the nine docs are modified by this prompt: `README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`. This report is the only new file. |

Not run (by rule): Playwright/browser tests, `alembic upgrade/downgrade`, SQL scripts, and any DB query outside pytest's own test database. Pytest writes only to `medscope_test`, as designed.

## 6. Files changed

- `README.md`
- `project-context.md` (also adds a "Prompt 10C" section before the Mandatory Phase-End clause)
- `docs/SCOPE.md` (new §5 "Owner Decisions — Decided, Not Yet Implemented")
- `docs/ARCHITECTURE.md` (ADL-032 to ADL-037, new §5 Schema Change Policy)
- `docs/DESIGN.md`
- `docs/API.md`
- `docs/WORKFLOWS.md` (new §6 "Decided Workflow Changes")
- `docs/DATABASE.md` (new §7.0 status)
- `docs/TESTING.md` (new §11 Current Verification Status, §12 Pre-Go-Live Cleanup List)
- `report/PROMPT_10C_IMPLEMENTATION_REPORT.md` (this file, new)

Not touched: product code, tests, e2e specs, migrations, `.gitignore`, configuration, `master_context_all_harness.md`, and the past `report/` files.

## 7. Tracked-but-deleted files (reported only; not restored, deleted or moved)

`git status` now shows **13** tracked files deleted in the working tree. The audit counted 6, and the 7 `report/` files have been deleted since then:

- `prompt/Prompt_07B_Code_Verification_Audit.md`
- `prompt/Prompt_07C_Safety_and_Correctness_Fixes.md`
- `prompt/Prompt_08_Modal_Navigation_Fix_Test_DB_Isolation_and_Test_Record_Identification.md`
- `prompt/Prompt_09_Role_Based_Authentication_and_Switcher_Removal.md`
- `prompt/Prompt_10B_Test_Data_Cleanup_SQL_Script.md`
- `prompt/Prompt_10_Login_and_Landing_Page_UI.md`
- `report/PROMPT_07B_VERIFICATION_REPORT.md`
- `report/PROMPT_07C_IMPLEMENTATION_REPORT.md`
- `report/PROMPT_08_IMPLEMENTATION_REPORT.md`
- `report/PROMPT_09_IMPLEMENTATION_REPORT.md`
- `report/PROMPT_10B_IMPLEMENTATION_REPORT.md`
- `report/PROMPT_10_IMPLEMENTATION_REPORT.md`
- `report/TEST_RECORD_CANDIDATES.md`

The docs still reference some of these historical reports by path. They remain available in git at commit `a6c0243`. I read the Prompt 10 report §9 from `git show HEAD:...` for item 2.

## 8. Deferred / Partial / Blocked

| Item | Status | Note |
|---|---|---|
| Fix e2e selectors (`#user`/`#pass`), rename `selectDevRole`, remove the stale comment in `receptionist_corrections.spec.ts:43` | **Deferred** | A separate coding task; the prompt forbids spec edits |
| D15 `refund_due` capping fix in `refund_service.py` | **Deferred** | Owner decision; scheduled for a later prompt |
| Implementing ADL-032 to ADL-035 (fixed role, Dashboard landing, Create User tab, Draft/Finalize) | **Deferred** | Decided, not implemented |
| Pre-go-live credential cleanup / password rotation | **Deferred** | Listed in `docs/TESTING.md` §12 only. Concrete credential values already in the docs (README env block, TESTING.md §7.2/§9.3, project-context Prompt 10 section) were **left in place** as instructed ("not to be acted on now"). No new secret was written. |
| Business-day / drawer balance reconciliation after the committed cleanup | **Deferred** | Documented as stale in `docs/DATABASE.md` §7.0/§7.4; no DB action |
| Cleanup script git-ignored (`*.sql`) | **Reported only** | `.gitignore` not changed; the docs state the file is local only |
| Item 7 execution evidence (audit_logs id 826) | **Partial verification** | Taken from the 2026-11-12 audit. I did not query `medscope_dcms` in this prompt (no DB access by rule). The on-disk file's `ROLLBACK;` ending was verified directly. |
| Item 4 "0 passed, 6 failed" | **Partial verification** | The selector mismatch was verified in code. The run result is the audit's, since no browser runs were allowed. |
| Blocked | None | — |
