# Prompt 18 Implementation Report: Module 21 (Accounting) + Module 22 (Day Open/Close)

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it; checklist in `docs/TESTING.md` §21.2). Nothing was committed, pushed, stashed or reset (the working tree was already uncommitted from earlier prompts; `git log` still shows the same 2 commits). The master context file was not edited. Per the scope note, only 3 new tests were written; thorough verification is left to the later prompt.

## 1. What I found first

| Question | Finding |
|---|---|
| Drawer | **Exists:** `business_days` (opening float, `closing_cash_counted`, `closing_variance`), `business_day_channel_balances` (per channel, with `closing_counted` / `variance` columns that nothing wrote). Payments and **cash** refund disbursement already move the drawer. |
| Day open | **Exists** (`POST /business-day/open`, opening float, channel openings). Reused unchanged. |
| Day close | **Existed but was a bare status flip**: no counted cash, no expected cash, no variance, no reason, no tolerance. Rebuilt on the same endpoint. |
| Reopen / closed-day protection | **None.** Payments only ever target the OPEN day, so a closed day was incidentally safe, but there was no reopen and no adjusting-entry concept. Added. |
| `/business-day/state` | Unchanged (money-free, every role). |
| Journal / ledger | **None** in the API (only the legacy Streamlit `accounting.py`, not touched). Cancellation / refund / write-off had no journal effect. |
| Export | **No export mechanism anywhere** in the app. Added one small CSV helper (UTF-8 BOM so Excel opens it). |
| Settings | `tenant_settings` (Prompt 17) reused for the variance tolerance. |
| Permissions | `business_day.close` (Admin/Owner) already covers close; reused. No existing key fits the reports / journal, so **one** was added (below). |

**Reused vs built:** reused the day table, channel balances, open flow, `/state`, `business_day.close`, `tenant_settings`, the Prompt 17 dues list and write-off, the existing cancellation / refund / payment flows. Built: the journal, postings, day-close maths, movements, reopen / adjustments, reports, the day panel and the Accounting page.

## 2. Done / Partial / Blocked / Deferred

### Item 1: journal / ledger model: **Done**
`accounts` (16 accounts seeded per tenant on first posting: Cash, bKash, Nagad, Rocket, Card, Bank, Other channel, Patient receivable, Refunds payable, Owner drawings, Test revenue, Urgent fee revenue, Discount given, Operating expense, Bad debt, Cash variance), `journal_entries`, `journal_lines`. Append-only and balanced **in the database**: triggers refuse UPDATE / DELETE (an entry's `created_by_id` may be re-pointed only, which the test-fixture staff purge needs) and a deferred constraint trigger refuses an unbalanced entry at commit; the service also validates first. A reversal is a new entry with `reverses_entry_id` (unique, so once only). `journal_lines.referrer_id` is reserved (nullable) for a later commission module.

### Item 2: real postings: **Done (real events only)**
Hooked as a side effect after each existing flow's own logic (no cancellation / write-off / billing logic changed): bill confirmed, payment received (initial and due settlement), line cancelled (both the immediate path and the approval path, with a refund owed moved to Refunds payable), refund paid, due written off, cash variance, bank deposit, owner withdrawal, small expense. Exact lines are in `docs/SCOPE.md` §13.
**Deferred, nothing posted:** commission accrued / reversed / paid, visit-fee handover, consultant fee, outside-lab cost (Modules 19 / 20 / 28 do not exist). No visit-fee liability line is posted because no visit-fee line exists. No "doctor-fee liability" account was created for the same reason.

### Item 3: V1 reports: **Done (cost by referrer is honestly empty)**
`GET /accounting/cash-book`, `income-expense`, `dues` (reuses the Prompt 17 list, only an optional bill-date range was added to it), `cost-by-referrer`, plus a read-only `journal`. Flexible `from` / `to`; `format=csv` on each. Cost by referrer shows real billing per referrer next to a cost of **0** with an explicit note (commission is Module 19). Income / expense is on a billing basis (the day a bill is confirmed). No P&L / balance sheet / cash flow.

### Item 4: day screen: **Done**
- **Open:** existing, reused.
- **Expected cash (D45):** opening cash + cash collections - cash refunds - bank deposits - owner withdrawals - small expenses, computed from source tables (not the journal, so a day that began before the journal is still right). The four payout kinds of unbuilt modules are shown as lines at 0 labelled "not built yet"; write-offs are not in the formula. "Unsynced items" is reported as 0 and always passes.
- **Count / variance / reason:** counted cash required; wallet and bank channels counted on their own lines (expected = opening + collections - refunds on that channel); variance = counted - expected; a reason is required when `abs(variance)` exceeds `cash_variance_tolerance` (new `tenant_settings` key, default **0**, edited by the Owner on the Settings page).
- **Reopen:** Owner only, reason required, status `REOPENED`. A closed or reopened day refuses any ordinary journal entry (409); a reopened day takes **adjusting entries only** (reversal of one of that day's entries, or a balanced manual entry; Owner, reason). Re-closing keeps the original close time and posts only the change in variance.
- **Movements:** bank deposit / owner withdrawal (Owner only) / expense (what-for required) from the open day's cash, never above the expected cash.
- **Close authority unchanged** (Admin/Owner; the Prompt 04 supersession stands).

### Needs the owner's decision (not blocking)
1. **No backfill.** The journal starts at deployment; the dev DB's earlier bills and payments have no entries, so the reports show activity only from now. I did not invent historical postings (repository rule 8). Say if you want a derived backfill.
2. **Tolerance default 0** (every variance needs a reason until the Owner sets a tolerance).
3. **Existing close contract changed on purpose:** `POST /business-day/close` now requires `counted_cash` (the old bodyless call returns 422). One older test sent the old body and was updated.

## 3. Files changed

Backend: new `app/models/accounting.py`, `app/services/accounting_service.py`, `accounting_report_service.py`, `day_close_service.py`, `app/api/v1/endpoints/accounting.py`, migration `alembic/versions/f9a2c4d6e8b1_prompt18_accounting_day_close.py`; edited `app/models/business_day.py`, `app/models/__init__.py`, `app/core/permissions.py`, `app/api/v1/router.py`, `app/api/v1/endpoints/business_day.py` (close rewritten; day-screen, movements, reopen, adjustments added), `endpoints/settings.py`, `services/settings_service.py`, `business_day_service.py` (old close function removed), `invoice_service.py`, `payment_service.py` (posting call; optional date range on the dues list), `refund_service.py`, `dues_service.py` (posting calls only).
Frontend: new `features/business_day/DayClosePanel.tsx`, `features/accounting/AccountingPage.tsx`; edited `features/business_day/BusinessDayPage.tsx`, `features/admin/SettingsPage.tsx`, `App.tsx`, `components/layout/Sidebar.tsx`, `api/client.ts`, `types/index.ts`.
Tests: new `tests/test_prompt18_accounting_day_close.py` (3 tests); edited `test_prompt11_soft_delete.py`, `test_prompt15_doctor_signoff.py` (key counts 43 / 24), `test_prompt17_handover_dues.py` (settings shape), `test_prompt09_auth.py` (close body).
Docs: all nine. Backup (git-ignored): `backups/medscope_dcms_pre_prompt18.dump`.

## 4. Migration details

| | |
|---|---|
| Revision / `down_revision` | `f9a2c4d6e8b1` / `e5d7a2c9b138` |
| `alembic heads` before / after | `e5d7a2c9b138` / `f9a2c4d6e8b1` (single both times) |
| `alembic check` | "No new upgrade operations detected." (dev and test DB) |
| Autogenerate review | Four new tables and five nullable `business_days` columns; additive. **Fixed by hand:** the unnamed FK on `business_days.reopened_by_id` got its PostgreSQL default name so the downgrade works. **Added by hand:** the append-only and balanced-entry triggers (plus their drop in the downgrade). |
| Round trip | `downgrade e5d7a2c9b138` then `upgrade head` on `medscope_test`: both succeed. |

**Exact command sequence against `medscope_dcms` (in order):**
1. Target check: read `DATABASE_URL` from `backend/.env`, printed the database name `medscope_dcms`.
2. `pg_dump -Fc -d medscope_dcms -f backups/medscope_dcms_pre_prompt18.dump` (connection from `PG*` variables set from `.env`; exit 0, 240,505 bytes).
3. `pg_restore -l` on the dump, searched `journal_entries`: **0 matches** (pre-migration); `git check-ignore` confirmed it is ignored.
4. `ALEMBIC_DATABASE_URL=<dev URL> alembic current` -> `e5d7a2c9b138` (target printed as `medscope_dcms` first).
5. `alembic upgrade head` -> `e5d7a2c9b138 -> f9a2c4d6e8b1`.
6. `alembic current` -> `f9a2c4d6e8b1 (head)`; `alembic check` -> no new operations; counts: 39 tables, `accounts` / `journal_entries` / `journal_lines` / `day_movements` 0 rows, `business_days` 3 rows unchanged.
Everything before step 2 (autogenerate, upgrade, downgrade, tests, baseline pytest) ran with `ALEMBIC_DATABASE_URL` pointed at `medscope_test`, each time printing `TARGET: medscope_test` first. An earlier attempt to run steps 4-6 stopped on a PowerShell env-var cleanup error **before any alembic command ran**; I re-ran the sequence cleanly from step 4 (the backup was already taken).

## 5. API counts

| | Before (Prompt 17) | After |
|---|---|---|
| Paths | 119 | **128** |
| Operations | 134 | **143** |
| Permission keys / money | 42 / 23 | **43 / 24** (one new: `accounting.view`, Admin/Owner; no existing key describes the reports and journal) |
| Tables in `medscope_dcms` | 35 | 39 |

New: `GET /accounting/{cash-book,income-expense,dues,cost-by-referrer,journal}`, `GET /business-day/day-screen`, `POST /business-day/movements`, `POST /business-day/{id}/reopen`, `POST /business-day/{id}/adjustments`. Changed: `POST /business-day/close` (counted cash), `GET` / `PUT /settings` (tolerance).

## 6. Validation results (non-browser, actually run)

| Check | Result |
|---|---|
| `pytest` (`medscope_test` only) | Baseline before any change **245 passed**; after **248 passed, 0 failed** (3 new) |
| `tsc -b` | 0 errors |
| `oxlint` | exit 0, 0 errors; 119 warning lines (was 117; two are the same set-state-in-effect pattern the other pages already have, in `DayClosePanel.tsx` and `BusinessDayPage.tsx`'s existing effect) |
| `vite build` | succeeds |
| `alembic heads` / `check` | `f9a2c4d6e8b1` single / no new operations |

The 3 new tests cover only what cannot be checked another way: the receivable follows the invoice through bill, partial payment, cancellation and write-off and every entry balances (with no commission / visit-fee / consultant / outside-lab entries); the database refuses UPDATE / DELETE and an unbalanced entry; and the day-close flow (D45 identity, Admin/Owner gates, variance reason against the tolerance, closed day refuses movements, Owner-only reopen, adjusting entries only, re-close). **Not done:** no browser test, no claim of browser acceptance.

## 7. Documentation: all nine files, current truth only

| Doc | What changed |
|---|---|
| `README.md` | Counts (128 / 143, 39 tables, head `f9a2c4d6e8b1`), phase and test lines replaced with Prompt 18. |
| `project-context.md` | New Prompt 18 section; Prompt 17's stale "Current phase", counts line and "accounting postings not built" removed. |
| `docs/SCOPE.md` | New §13 with the module coverage table (what is covered, what is deferred), postings, reports, expected cash, variance, reopen rules; the stale "accounting postings (Modules 21 / 22)" cell in §12 removed. |
| `docs/ARCHITECTURE.md` | ADL-075 / 076 / 077; head and table count corrected; ADL-073's "no journal entry" note corrected. |
| `docs/DESIGN.md` | New §21 (day panel, accounting page); Settings page description gains the tolerance card. |
| `docs/API.md` | Counts (128 / 143, 43 / 24); close endpoint row updated; new §13 for every new / changed endpoint. |
| `docs/DATABASE.md` | Head, table count, four new tables in the list, migration row, new accounting section (accounts, triggers, columns); `tenant_settings` key list. |
| `docs/WORKFLOWS.md` | Close-day row corrected; new §16 (postings, day close, reopen, reports). |
| `docs/TESTING.md` | Prompt 17's section 20 figures updated to current values; new §21 (evidence, owner acceptance checklist, known not done). |
