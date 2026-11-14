# MedScope DCMS — Full Read-Only Audit Report

- **Audit date/time:** 2026-11-12 23:49 (+06:00)
- **Git commit audited:** `a6c0243c5b2a6bb7ac23d7136241ab203443356e` ("landding and login page and menu tab change fix"), branch `main`, up to date with `origin/main`
- **Mode:** read-only. No repo file edited (apart from this report), no DB write by the auditor, no git state change, no migration, no SQL script executed.
- **Verdict vocabulary:** Confirmed / Not confirmed / Contradicts prior report / Could not verify.

## Headline findings

1. **Contradicts prior report (10B): the cleanup SQL WAS run and COMMITTED on the main DB `medscope_dcms`.** Audit row `TEST_DATA_CLEANUP` (audit_logs id 826, 2026-11-11 19:42:28) records 135 patients, 115 referrers, 209 invoices, 151 payments, etc. deleted. The script ships with `ROLLBACK;` as its default last line, so the owner edited it to `COMMIT`. The previous chat did not know this.
2. **`cleanup_test_data.sql` is not under version control.** `.gitignore:75` (`*.sql`) ignores it, so the file exists only on disk.
3. **Business-day / drawer balances are now stale**, exactly as warned (details in B5). `business_day_channel_balances.received_amount` is far above the real payments.
4. **Live logins verified (second pass, after the owner supplied the password).** All 4 accounts log in and land on the expected routes; the Patient History modal opens in place with no URL change. The first pass used only the test-suite password, which the live accounts reject, so the first attempts failed (see E2).
5. **Both Playwright specs are broken against the current UI.** All 6 specs in `test_modal_regression.spec.ts` fail because of a stale selector (`#username`; the login page now uses `#user`). `selectDevRole` still exists as a login-helper name.
6. **Docs contradictions:** `docs/DESIGN.md` narrative fields, `docs/ARCHITECTURE.md` and `docs/SCOPE.md` reduced-motion claims, and stale numbers in `project-context.md`.
7. **Prompt 11 (soft delete) is not implemented.**

Note: the main DB is in live use by someone else during this audit. `CONFIRM_INVOICE` and `AUTH_LOGIN_SUCCESS` rows appeared at 23:12–23:30 that I did not create. Counts below are a snapshot taken during this window.

---

## A. Repository state

### A1. Git state — Confirmed
- Branch `main`, commit `a6c0243…`. Two commits total (`964c7a3` initial, `a6c0243`).
- Staged: none. Untracked: `prompt/Prompt_FULL_AUDIT_Repo_DB_Docs_Browser.md` (plus this report once written).
- **Tracked-but-deleted files: 6 (not ~15):**
  - `prompt/Prompt_07B_Code_Verification_Audit.md`
  - `prompt/Prompt_07C_Safety_and_Correctness_Fixes.md`
  - `prompt/Prompt_08_Modal_Navigation_Fix_Test_DB_Isolation_and_Test_Record_Identification.md`
  - `prompt/Prompt_09_Role_Based_Authentication_and_Switcher_Removal.md`
  - `prompt/Prompt_10B_Test_Data_Cleanup_SQL_Script.md`
  - `prompt/Prompt_10_Login_and_Landing_Page_UI.md`
  - Not restored, not touched.

### A2. Alembic — Confirmed
`alembic current` = `b9e41d82f05a (head)`. `alembic heads` shows exactly one head, `b9e41d82f05a`. Matches the expected head. The `alembic_version` table in `medscope_dcms` also holds `b9e41d82f05a`.

### A3. Prompt 10B outcome — Contradicts prior report
- `backend/scripts/sql/cleanup_test_data.sql` **exists** (750 lines). It is wrapped in a transaction, with a default `include_medium=TRUE` config, evidence-based name patterns, and protected-ID lists. The header says its default end is `ROLLBACK;`.
- It is **git-ignored** (`.gitignore:75 *.sql`), never committed.
- **Evidence it was run and committed against `medscope_dcms`:**
  - `audit_logs` id 826, action `TEST_DATA_CLEANUP`, actor 1/OWNER, `after_value` = `{"script":"cleanup_test_data.sql","patients_deleted":135,"referrers_deleted":115,"invoices_deleted":209,"visits_deleted":209,"invoice_lines_deleted":218,"payments_deleted":151,"test_orders_deleted":218,"test_order_events_deleted":153,"assignment_history_deleted":155,"samples_deleted":29,"results_deleted":3,"refund_requests_deleted":78,"reprint_logs_deleted":48,"audit_logs_deleted":587}`. Timestamp 2026-11-11 19:42:28.
  - Row counts now match the script's "kept" figures: 16 patients, 16 referrers. Invoices are 15 versus the 14 kept. The extra one, SD-000226, was created later (a `CONFIRM_INVOICE` at 23:19 today).
  - `pg_stat_user_tables` still has stale `_cand_*` temp-table stats, which is a leftover of the run.
- The 10B report says "Zero persistent mutations … dry run". That was true of the Antigravity session, but the owner has since executed it with COMMIT.

### A4. Prompt 11 (soft delete) — Confirmed unimplemented
- Zero `delete` operations among the 79 OpenAPI operations.
- No `is_deleted` / `deleted_at` / soft-delete code in `backend/` or `frontend/src/`.
- No confirm-delete dialogs found. `staff.active` exists but pre-dates this work.

### A5. Project checks — real counts
| Check | Result |
|---|---|
| `pytest` | **45 passed, 0 failed**, 5 warnings (5.2s). DB guard confirmed: with `TEST_DATABASE_URL` pointed at `medscope_dcms`, collection was refused with "FATAL SAFETY GUARD VIOLATION … Database: 'medscope_dcms'" (`tests/conftest.py`, `enforce_safety_guard`). Default run used `medscope_test`. |
| `tsc -b` | **Pass**, exit 0, no output. |
| `oxlint` | **0 errors, 120 warnings** (the count of lines containing "warning"). Mostly unused imports, `set-state-in-effect`, and `exhaustive-deps` in `InvoicesPage.tsx`, `PatientHistoryModal.tsx`, `TechnicianWorklistPage.tsx`, `ProfilePage.tsx` and others. |
| Frontend build | **Pass** (`vite build`, 733 ms). Output sent to the scratchpad so `dist/` was untouched. One warning: a 578.8 kB JS chunk exceeds 500 kB. |

Side effects: running pytest wrote rows into `medscope_test` (its own DB, as intended). `tsc -b` may refresh tsbuildinfo in ignored locations. Playwright wrote to the git-ignored `frontend/test-results/`.

### A6. Dev-role switcher — Confirmed absent from product code, but residue remains
- `frontend/src/` and `backend/app/`: **0 hits** for `selectDevRole`, `actorMode`, `toggleRole`, or `X-Staff-*` headers. Confirmed removed.
- Residue: `selectDevRole` is still the helper name in `frontend/e2e/test_modal_regression.spec.ts`. It is now just a login helper. `frontend/e2e/receptionist_corrections.spec.ts:43` still has a stale comment, "Toggle role to Admin via header role switcher".
- Docs still describe `selectDevRole` as "Isolated Role Switcher" (`docs/TESTING.md:199`, `project-context.md:722`).

### A7. `test_modal_regression.spec.ts` — Contradicts prior report
- It still references `selectDevRole` (7 call sites, lines 7–188).
- Run against live dev servers (5173/8000): **0 passed, 6 failed** (A1–A6).
- Cause: the helper fills `#username` / `#password`. The current login page (`LoginPage.tsx`) uses `#user` / `#pass` (`data-testid` `login-username`, `login-password`).
- Secondary: the spec's `bg-[#CF8852]` active-nav class and the "Filter by bill" placeholder were not reached or could not be confirmed.
- The "6 passed in 14.4s" in the Prompt 08 report is no longer true.

---

## B. Database state (`medscope_dcms`, SELECT-only, read-only transactions)

### B1. Tables — Confirmed (no drift from docs)
28 tables in `public` = 27 domain tables + `alembic_version`. This matches `docs/DATABASE.md` and `README.md` (28 / 27). It contradicts `project-context.md:702` ("25 domain tables").

### B2. Row counts (snapshot, `medscope_dcms`; for comparison `medscope_test` in parentheses)
| Table | Count | Table | Count |
|---|---|---|---|
| patients | 16 (64) | payments | 16 (124) |
| visits | 15 (151) | refund_requests | 2 (54) |
| invoices | 15 (151) | audit_logs | 94 (485) |
| invoice_lines | 52 (156) | staff | 4 (30) |
| test_orders | 52 (156) | staff_roles | 6 (32) |
| samples | 9 (59) | auth_sessions | 14 (74) |
| results | 2 (13) | report_versions / deliveries | 6 / 4 |
| referrers | 16 (49) | tests | 1250 (25) |
| business_days / channel balances | 2 / 10 | sequence_counters | 4 |

### B3. Accounts and roles — Confirmed
| Username | Primary role | Roles in `staff_roles` | Active |
|---|---|---|---|
| reception_fatima | RECEPTIONIST | RECEPTIONIST*, **CASHIER** | yes |
| admin_tariq | ADMIN | ADMIN*, OWNER | yes |
| tech_kamal | LAB_TECH | LAB_TECH* | yes |
| tech_nasrin | LAB_TECH | LAB_TECH* | yes |

- **CASHIER role present in DB:** Confirmed (assigned to `reception_fatima`).
- **CASHIER referenced in backend permission code:** Confirmed, but thinly. Only two places:
  - `backend/app/core/security.py:83`, where `require_receptionist` allows `("RECEPTIONIST","CASHIER","ADMIN","OWNER")`.
  - `backend/app/services/auth_service.py:76`, which treats `RECEPTIONIST`/`CASHIER` alike.
  - There is no cashier-specific guard (e.g. for drawer close or refund disbursement) beyond being allowed through the receptionist gate. "Enforced CASHIER permission" is therefore Not confirmed as a distinct role.

### B4. Test/QA leftovers in the main DB
- Patients matching test patterns (E2E / Refund Patient / Zero Pay / Dedup / Filter / Unpaid / Dup / Prescriber / Playwright): **0**.
- Referrers matching test-ish patterns: **2** (ids 11 and 31). These are the ones the cleanup script deliberately protected, because legitimate QA invoices reference them. Not a defect.
- The remaining 16 patients, 16 referrers and 15 invoices equal the seed + manual-QA set the script protected, plus SD-000226 (post-cleanup).
- Verdict: the test-data pollution is Confirmed cleaned.

### B5. Business-day / drawer staleness — Confirmed STALE
| Day | Channel | `received_amount` in balances | Actual `SUM(payments.amount)` |
|---|---|---|---|
| 1 (CLOSED) | CASH | 17,200 | 3,300 |
| 1 | BKASH | 3,200 | 1,000 |
| 1 | NAGAD | 1,600 | 0 |
| 1 | BANK_TRANSFER / POS_CARD | 2,800 / 4,500 | 0 / 0 |
| 2 (OPEN) | CASH | 70,430 | 21,580 |
| 2 | BKASH | 4,360 | 4,360 (match) |
| 2 | NAGAD | 1,000 | 1,000 (match) |
| 2 | BANK_TRANSFER / POS_CARD | 0 / 0 | 0 / 0 |

- Day 1 is CLOSED, but with `closing_cash_counted` and `closing_variance` both NULL.
- Day 2 is OPEN (opened 2026-11-07 00:09) and has `day_number=2` while day 1 has `day_number=14`, an odd numbering.
- Nothing was reconciled, per scope.

Other state: `sequence_counters` invoice = 226, visit = 231, patient = 151, report = 15 (see D5).

---

## C. Docs vs code

### C1. The nine canonical docs — all exist, Confirmed
All nine have a last git commit date of **2026-11-11**: `README.md` (160 lines), `project-context.md` (866), `docs/SCOPE.md` (225), `ARCHITECTURE.md` (331), `DESIGN.md` (390), `API.md` (177), `WORKFLOWS.md` (286), `DATABASE.md` (226), `TESTING.md` (350).

| Claim checked | Docs say | Code/DB says | Verdict |
|---|---|---|---|
| API path/op counts (`docs/API.md:8-9`) | 69 paths / 79 operations | OpenAPI introspection: **69 / 79** | Confirmed |
| Table count (`docs/DATABASE.md`) | 28 total / 27 domain | DB: **28 / 27** | Confirmed |
| Narrative fields (`docs/DESIGN.md:302`) | "Technique, Detailed Findings, Impression, and Recommendations" | `backend/app/models/result.py:26-28` and `schemas/result.py`: **findings, impression, comments**. No `technique` or `recommendations` anywhere in `frontend/src`. | **Contradicts** (docs wrong; code is findings/impression/comments) |

### C2. Other material mismatches
- `docs/SCOPE.md:221` and `docs/ARCHITECTURE.md:306`, `project-context.md:816` claim a full `@media (prefers-reduced-motion: reduce)` fallback. **No such rule exists in `frontend/src`** (see D1). It was removed on purpose per `report/PROMPT_10_IMPLEMENTATION_REPORT.md` §9, but the docs were not updated.
- `project-context.md:784`: "untouched operational records (223 invoices)". Actual is **15**, after the cleanup.
- `project-context.md:702`: "25 domain tables" vs the actual 27.
- `docs/TESTING.md:199`, `project-context.md:722`: describe `selectDevRole` as a role switcher and claim "6 passed". Both are false (A6, A7).
- Report 10B ("zero persistent mutations") does not reflect that the cleanup was later committed (A3).

---

## D. Specific risk items

1. **`prefers-reduced-motion` removed — CONFIRMED ABSENT.** `grep` for `reduced-motion` and `matchMedia` in `frontend/src` returns nothing. `index.css:88-146` has keyframes with no media-query fallback. It is present only in the `docs/design-reference/*.html` mock-ups and in docs prose. This is an accessibility regression versus the docs and the design references. It was intentional (Prompt 10 §9, a Windows "animations off" case).

2. **Plaintext credentials in committed files — CONFIRMED PRESENT** (paths only, values not reprinted):
   - DB connection string with a real-looking password:
     - `tests/conftest.py:40` (hard-coded fallback to the main DB URL)
     - `README.md` (lines 51-52)
     - `docs/TESTING.md:215`
     - `report/PROMPT_08_IMPLEMENTATION_REPORT.md` (lines 105/107)
     - `report/PROMPT_10B_IMPLEMENTATION_REPORT.md:160`
     - `.env.example` and `backend/.env.example` (line 20). These may be intentional placeholders, but they carry a concrete value.
   - Hardcoded login passwords for the test accounts: `tests/conftest.py` (`TEST_PASSWORD_DEFAULT`), `tests/test_prompt09_auth.py`, `frontend/e2e/test_modal_regression.spec.ts:11`.
   - Not committed: `.env` and `backend/.env` (git-ignored, not tracked).
   - `backend/app/core/config.py:60` only builds the URL from settings (no literal).
   - Note: the `conftest.py` fallback means the main-DB credential is in git history.

3. **Result-entry guard vs later states — CONFIRMED ABSENT (does not wrongly block)**, with a caveat.
   - Guards: `backend/app/services/result_service.py:126`: `if not is_imaging and (not sample or sample.status != "COLLECTED")`. `result_service.py:278`: `if not sample or sample.status != "COLLECTED"` (409). `worklist_service.py:887`: same, on COMPLETED.
   - `Sample.status` only takes COLLECTED / REJECTED / SPOILED (`models/sample.py:18`). Culture incubating stage lives in `test_order.culture_stage`, and outsourced SENT/RECEIVED lives in `test_order.outsourced_status`. Neither changes `sample.status`, so valid later states are not blocked by `!= "COLLECTED"`.
   - Caveat (Could not verify end-to-end): outsourced tests with no sample record (`not sample`) would be blocked at result entry if `sample_type` is set. I did not exercise this because it needs write actions.

4. **D15 refund logic — CONFIRMED PRESENT (as feared).** `backend/app/services/refund_service.py:416-418`:
   ```python
   # Reduce invoice net and add to refund_due
   invoice.refund_due += line.net_price
   invoice.net -= line.net_price
   ```
   `refund_due` grows by the line's full `net_price` regardless of how much was actually paid on the invoice. Disbursement is capped per channel at what was paid (`refund_service.py:564-574`), so cash cannot be over-disbursed. But `refund_due` and the invoice `net` can overstate or go inconsistent for unpaid or partly paid invoices (`net` is floored at 0). Request creation can also cap at `net_price` (line 312).

5. **Invoice numbering gaps — CONFIRMED (gaps exist; no compaction).** `sequence_service.py:6-32` increments `sequence_counters.current_value` and returns `SD-{val:06d}` with no reuse. The counter is at 226 while only 15 invoices exist, with numbers SD-000001…SD-000226 (e.g. 000001-5, 000031, 000066, 000006-8, 000099, 000135-137, 000226). The cleanup created these gaps. The script says "numbering gaps are normal", and that is the actual behavior.

---

## E. Live app (Playwright, read-only; frontend :5173, backend :8000)

Screenshots are in `C:\Users\zituser\AppData\Local\Temp\2\claude\0076039d53f86387\6b090537-a899-4a90-9fb4-17fc70ec408a\scratchpad\shots\` (kept outside the repo to honor "write ONE file"): `page_root.png`, `page_login.png`, `mobile_root.png`, `mobile_login.png`, `404.png`, `after_*.png`.

### E1. `/` and `/login` — Confirmed render; console errors Not clean
Both pages render with title "MedScope DCMS — Diagnostic Center Management System". Console shows only **401 Unauthorized resource errors** (2 on `/`, 4 on `/login`) while logged out. This is consistent with an unauthenticated session probe, but it is noise in the console. No JS exceptions.

### E2. Login as the 4 accounts — Confirmed (second pass)
- First pass (test-suite password): rejected for all 4 accounts, one failed attempt each (`failed_attempts=1`, no lock). The owner then supplied the real password (not recorded here), and the second pass succeeded for all 4. A successful login resets the counter (`auth_service.py:162`).
- Results (logged in, screenshot taken, logged out via `sign-out-btn`; each logout returned to `/login`):

| Account | Landing route | Expected | Role switcher in header user menu | Verdict |
|---|---|---|---|---|
| reception_fatima | `/invoices` | `/invoices` | receptionist, cashier | Confirmed |
| admin_tariq | `/dashboard` | `/dashboard` | admin, owner | Confirmed |
| tech_kamal | `/worklist` | `/worklist` | none (fixed LAB_TECH) | Confirmed |
| tech_nasrin | `/worklist` | `/worklist` | none (fixed LAB_TECH) | Confirmed |

- Console after login: 2-3 resource errors per session (not itemised; the logged-out 401 probes in E1 are one source). Not investigated further.
- Screenshots: `after_reception_fatima.png`, `after_admin_tariq.png`, `after_tech_kamal.png`, `after_tech_nasrin.png` in the scratchpad `shots` folder.
- Side effect: 4 more `AUTH_LOGIN_SUCCESS` / `AUTH_LOGOUT` audit rows and 4 new `auth_sessions` rows, plus the earlier failed-login rows. The second pass also ran twice for admin (the first script run aborted on a logout click after a successful login).

### E3. 390px width — Confirmed
`/`: scrollWidth 390 = clientWidth 390. `/login`: 390 = 390. No horizontal scroll on either.

### E4. `/abc` — Confirmed
The branded 404 renders: "Page not found — The page you are looking for does not exist or has been moved." with a "Back to home" link; URL stays `/abc`.

### E5. Invoices → Patient History modal — Confirmed
Logged in as `reception_fatima`, `/invoices` listed 15 invoice rows. I opened the first one in view mode ("View Invoice Details"), clicked "Patient History", and the URL stayed `http://127.0.0.1:5173/invoices` before and after (no route change); history content appeared (`patient_history.png`). Nothing was submitted or created.

---

## F. Docs-vs-Code Mismatch Register

Every place where a document states something the current code, database or test run contradicts. "Truth" is what I verified at commit `a6c0243` and in `medscope_dcms` on 2026-11-12. Nothing was edited; the "Suggested doc fix" column is a recommendation only.

### F1. Mismatches (docs wrong)

| # | Doc and location | Doc claims | Actual (evidence) | Severity | Suggested doc fix |
|---|---|---|---|---|---|
| 1 | `docs/DESIGN.md:302` | Narrative template has "Technique, Detailed Findings, Impression, and Recommendations" | Code has `findings`, `impression`, `comments` (`backend/app/models/result.py:26-28`, `schemas/result.py:42-44,74-76`); no `technique` or `recommendations` anywhere in `frontend/src` | High (clinical report fields) | Replace with "Findings, Impression, Comments" |
| 2 | `docs/SCOPE.md:221`, `docs/ARCHITECTURE.md:306`, `project-context.md:816` | Landing/login animations have a full `@media (prefers-reduced-motion: reduce)` fallback | No such rule in `frontend/src` (`index.css:88-146` keyframes only). Removed on purpose, see `report/PROMPT_10_IMPLEMENTATION_REPORT.md` section 9 | Medium (accessibility claim is false) | State that the fallback was removed, or restore it without the stacking bug described in that report |
| 3 | `docs/TESTING.md:199` | Role switching in Playwright is an "Isolated Role Switcher" `selectDevRole(page, role)` | `selectDevRole` is now only a login helper (`e2e/test_modal_regression.spec.ts:7-15`); the switcher UI was removed in Prompt 09 | Low | Rename in docs to "login helper"; note that it is stale (item 5) |
| 4 | `project-context.md:722` | Modal regression suite "6 passed in 14.4s" | Run on 2026-11-12: **0 passed, 6 failed** (spec fills `#username`/`#password`; page now uses `#user`/`#pass`) | High (false test status) | Mark the suite as failing and fix the selectors |
| 5 | `docs/TESTING.md` (e2e section), `report/PROMPT_08_IMPLEMENTATION_REPORT.md` | Regression specs are pre-approved and passing | Same as item 4. Also `e2e/receptionist_corrections.spec.ts:43` still says "Toggle role to Admin via header role switcher" | Medium | Update the specs, then the docs |
| 6 | `project-context.md:784` | Primary DB has "untouched operational records (223 invoices)" | `medscope_dcms` has **15 invoices** (after the cleanup) | High (data claim is false) | Correct counts and record the cleanup |
| 7 | `project-context.md:702` | "25 domain tables + 1 alembic_version = 26" | 28 tables = 27 domain + `alembic_version` (this matches `docs/DATABASE.md`, so the file contradicts itself and the DB) | Low | Update or mark as historical |
| 8 | `docs/DATABASE.md:197`, `docs/TESTING.md:334-346`, `project-context.md:842`, `report/PROMPT_10B_IMPLEMENTATION_REPORT.md` | Cleanup script is only dry-run verified; "zero mutations against live `medscope_dcms`" | The script was later executed and committed on `medscope_dcms`: `audit_logs` id 826 `TEST_DATA_CLEANUP` (2026-11-11 19:42:28); 135 patients, 209 invoices etc. deleted | High | Add an "executed on 2026-11-11" note with the audit-log reference |
| 9 | `docs/DATABASE.md:197` | Kept-entity assertion "16 patients, 16 referrers, 14 invoices" | Current: 16 / 16 / **15** (SD-000226 created after the cleanup) | Low | Note as "at time of cleanup" |
| 10 | Docs on cleanup script location (`docs/DATABASE.md`, `report/PROMPT_10B_IMPLEMENTATION_REPORT.md`) | `backend/scripts/sql/cleanup_test_data.sql` is a delivered repo deliverable | Git-ignored by `.gitignore:75` (`*.sql`); not in git, so it is lost on a fresh clone | Medium | Remove `*.sql` ignore for `backend/scripts/sql/` or state that the file is local only |
| 11 | `docs/DATABASE.md`, `docs/ARCHITECTURE.md` (business-day / drawer sections) | Drawer/channel ledger reflects recorded payments | `business_day_channel_balances.received_amount` is stale after the cleanup, e.g. Day 2 CASH 70,430 vs 21,580 actual payments; Day 1 CASH 17,200 vs 3,300 (section B5) | High (financial) | Document the discrepancy and the reconcile plan |
| 12 | `docs/API.md:98`, `docs/ARCHITECTURE.md:215` (refund approval) | "Approval moves request to APPROVED and invoice to REFUND_APPROVED", implying `refund_due` reflects what is owed | `refund_service.py:416-418` adds the line's full `net_price` to `refund_due` regardless of amount paid (section D4) | High (financial logic) | Document the actual rule, or fix the code and then the docs |
| 13 | `README.md:51-52`, `docs/TESTING.md:215`, `report/PROMPT_08*`, `PROMPT_10B*` | Show connection strings as setup instructions | They contain a concrete DB password; `tests/conftest.py:40` hard-codes the main-DB fallback (section D2) | High (security) | Use placeholders such as `<password>` |

### F2. Docs that were checked and match the code (no action)

| Claim | Where | Verified |
|---|---|---|
| 69 API paths / 79 operations | `docs/API.md:8-9` | OpenAPI introspection returns 69 / 79 |
| 28 tables (27 domain + `alembic_version`) | `docs/DATABASE.md:10,47`, `README.md:28` | DB has 28 |
| Alembic head `b9e41d82f05a` | `docs/DATABASE.md` | `alembic heads` returns one head, same revision |
| Business-day close rejects Receptionist/Cashier | `docs/API.md:30`, `docs/ARCHITECTURE.md:129` | Endpoint depends on `require_receptionist`, but the rejection happens in the service (`business_day_service.close_business_day` calls `reject_close_business_day_for_receptionist`). Matches |
| Cashier has the same front-desk permissions as Receptionist | `docs/SCOPE.md:27` | Code uses one shared gate (`security.py:83`); consistent |
| Role home routes (`/invoices`, `/worklist`, `/dashboard`) | `docs/ARCHITECTURE.md:300` | Confirmed in live login (section E2) |
| Dev role switcher removed | `README.md:91`, `docs/DESIGN.md:139` | No switcher code in product source; the header shows a multi-role switch for dual-role accounts only |

### F3. Items I could not check against the docs
- Docs statements about report delivery, commission reversal and the drawer ledger beyond those listed above were not exercised, because that needs write actions.
- Note on the cleanup script: the file on disk now ends with `ROLLBACK;` (line 748) and `-- COMMIT;` commented out (line 749), yet the DB shows the cleanup was committed. The executed copy therefore differed from what is on disk, or the file was restored afterwards. Docs should not describe the on-disk file as what was run.

---

## Summary of verdicts
| Item | Verdict |
|---|---|
| Head `b9e41d82f05a`, single head | Confirmed |
| 10B script not executed | **Contradicts prior report** (committed 2026-11-11 19:42) |
| 10B script in git | Not confirmed (git-ignored) |
| Prompt 11 soft delete | Confirmed unimplemented |
| pytest 45/45, tsc, build | Confirmed pass |
| lint | 0 errors, 120 warnings |
| selectDevRole removed | Partly (product code yes; e2e helper and docs still reference it) |
| Modal regression spec passes | **Contradicts prior report** (0/6; stale selectors) |
| 4 accounts / CASHIER in DB | Confirmed |
| CASHIER-specific permission code | Not confirmed (only a shared receptionist gate) |
| Drawer / channel balances | Stale (Confirmed) |
| API 69/79, DB 28/27 | Confirmed |
| DESIGN.md narrative fields | Contradicts code |
| Reduced-motion | Absent; docs say present |
| Plaintext secrets in committed files | Present (paths above) |
| D15 refund_due over-credit | Present |
| Invoice number gaps | Confirmed (counter 226 vs 15 invoices) |
| Live logins (4 accounts, landing routes, role switchers) | Confirmed |
| Patient History modal opens without URL change | Confirmed |
