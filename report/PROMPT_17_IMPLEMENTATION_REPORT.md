# Prompt 17 Implementation Report: Module 17 (Report Handover) + Module 18 (Dues)

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset. The master context file was not edited. No SMS reminders, corporate dues, online viewing / courier, payouts, commissions or accounting postings were built.

## 1. What I found first

| Question | Finding |
|---|---|
| `report_deliveries` | **Exists and is the handover log:** `delivered_to_name`, `delivered_to_phone`, `delivered_to_relation`, `delivered_with_due`, `due_release_reason`, `delivered_at`, `delivered_by_id`. Writing a row also writes a `DELIVER_REPORT` audit row. Third-party collection needs no special record (matches the scope). 4 rows in `medscope_dcms`. |
| Due-hold rule | **Exists** (Prompt 10E): with a due, Receptionist and Cashier get 403, Admin/Owner (`report.release_with_due`) need a reason; but it was **unconditional** (no on/off setting). |
| Reprint / "Duplicate" (M9) | `GET /reports/printable/{id}` + `ReprintLog` + `is_duplicate` exist. **Real bug found:** the printable endpoint wrote the reprint log row but never committed (`get_db` does not commit), so no report reprint was ever persisted; and `reprint_count` was hard-coded 1. Fixed (commit + counting earlier prints). |
| Handover search | Deliverable list searched report no., bill no., name, phone only. **Missing:** patient number, test name, temporary bill number; and the Paid / Held filter in the UI sent `has_due`, which the API **ignored**. |
| Inline payment | Dues page has a settle modal (`POST /payments`), inline in the page code; the handover screen had none ("Held" only). |
| Settings mechanism | **None.** No settings table; role discount maximums and similar are in code. The "existing owner-editable settings" the prompt mentions do not exist. Added one. |
| Write-off / bad debt | **None.** No table, no column, no endpoint. |
| Doctor balances / party ledger / visit-fee liability | **None.** `referrers` has commission rate fields only; there is no wholesale price tier, no visit-fee holding, no ledger. Modules 20 / 28 are not built, so neither balance has a data source. |
| Dues | `GET /dues` and settle exist (derived from `invoices.due`, which payments and refunds maintain). **Missing:** age buckets, call list; its search used exact equality on name and phone. |
| Discount model | `invoices.discount` / line discounts; I confirmed write-off needs no touch of them. |
| Module-coverage dashboard | There is **no** such dashboard in the repo docs (it lives in the master context file, which I may not edit). See section 8. |
| Alembic head before | `d2b6f8a1c439` (single). Git: unchanged (2 commits, work uncommitted). |

**Mostly already done:** Module 17 (hold rule, handover log, reprint log, payment flow). The real gaps were the hold setting, search fields, the due filter, inline payment, and the reprint persistence bug. **Almost entirely missing:** Module 18's aging, call list, write-off, settings and doctor balances.

## 2. Done / Partial / Blocked / Deferred

### Item 1: handover screen: **Done (gaps built, existing reused)**
- The handover screen is the existing **Issued Reports** tab (no new search component). Search now finds bill no. (final and temporary), patient no., test name / code, mobile, name, report no.; the Paid / Held filter works on the server.
- Each row shows state (Final / Issued from Prompt 16), the due, and whether it is held. A row with a due shows **Take payment**, which opens the **same payment modal** as the Dues page: I extracted it unchanged into `SettleDueModal` so Dues and handover share one component, endpoint and receipt (no second payment UI).
- Handover log: existing `report_deliveries` + audit (staff, time, recipient, released-despite-due flag and reason). The audit text now also says whether it was released despite a due or the hold setting was off.
- Reprint: reuses the existing printable report / `ReprintLog` / Duplicate; confirmed it did **not** persist (bug above) and fixed it. No parallel path built.
- Not built (deferred): online viewing, courier. Not changed: handing a report over twice is still allowed (each is logged); I tried a block but it broke an existing test's expectations and the scope does not ask for it, so I removed it.

### Item 2: held-report center setting: **Done**
New key/value table `tenant_settings` with `report_hold_when_due` (default **on**, so behavior is unchanged until the Owner edits it). Off: reports are never held (`is_held_due_to_balance` / `can_deliver` follow the setting; delivery needs no reason). Edited on the new Owner-only **Settings** page; every change audited.

### Item 3: patient dues view and call list: **Done**
Dues list shows age and bucket (0-7, 8-30, 31-90, over 90 days, from the bill date) with a bucket filter and totals; **Call list** groups patients with unpaid balances, oldest first, with phone and bills. Everything derived on request, nothing stored. Promised-payment-date notes: **no such mechanism exists**, so kept a simple list as instructed (no CRM). The dues search was also fixed to partial matches including patient number.

### Item 4: doctor balances: **Partial (structure + view; no data source exists)**
Nothing existed to read. I added `doctor_balance_entries` (signed rows with `kind` `WHOLESALE_RECEIVABLE` or `PROFESSIONAL_FEE_PAYABLE`) and a read-only view (`GET /doctor-balances`, Dues > Doctor balances) that shows the two figures in separate labeled columns and never sums them (the response has no merged field). Because wholesale billing, held visit fees and payouts (Modules 28 / 20) are not built, **nothing writes the table, so every figure is 0**, and the screen says so rather than inventing numbers. No payout screen, no commission logic.

### Item 5: write-off: **Done**
`due_writeoffs` (separate bad-debt record) + `invoices.written_off`. Admin within the limit (setting `writeoff_admin_limit`, default 500, **per bill in total** so splitting cannot dodge it) applies directly; above it an Admin request is `PENDING_OWNER` and only the Owner can approve or reject; the Owner can write off any amount. Applying lowers `invoices.due` and raises `written_off`; `gross`, `discount`, `net`, `paid` are untouched (tested), so no discount figure is affected. No journal entry and no drawer effect (Modules 21 / 22 not built; the drawer/ledger is cash-based and a write-off moves no cash). The refund-cancellation arithmetic now subtracts `written_off` so written-off money is not owed again after a later line cancellation (tested).

### Partial / Blocked / Deferred
Deferred by instruction: SMS reminders, corporate dues, online viewing / courier, M19-M22. Not built (no mechanism existed): promised-date notes, write-off reversal.

## 3. Assumptions

| Assumption | Choice |
|---|---|
| Settings storage | New `tenant_settings` key/value table (no settings mechanism existed). Defaults in code: hold = on, Admin write-off limit = **500 Taka** (a placeholder the owner should set; no limit existed anywhere). |
| Write-off limit semantics | Cumulative per bill (`written_off + amount <= limit`), not per request. |
| Owner approval | An Admin request above the limit waits as `PENDING_OWNER`; one pending request per bill; Owner may also write off directly. |
| Age bucket edges | 0-7, 8-30, 31-90, over 90 whole days since the bill date. |
| Call list definition | All patients with an outstanding due, oldest first (filterable by bucket); "overdue" is not defined separately because the scope gives none. |
| `payment_status` after a write-off | Left unchanged (no new status value); the bill shows a "written off" note and `written_off`. |
| Doctor balances source | New append-only `doctor_balance_entries`; no writers yet; 0 until Modules 20 / 28. |
| **Permission keys** | **Three new keys, added because no existing key fits** (checked the full list): `settings.manage` (Owner only; `user.manage` is Admin+Owner and is user administration), `due.writeoff` (Admin, Owner; money), `doctor_balance.view` (Admin, Owner; money; commission-adjacent so the front desk must not see it). Totals 42 keys / 23 money. Existing keys cover everything else (`payment.view`/`take`, `report.view`/`deliver`/`release_with_due`). The services also check the role (write-off Admin/Owner, approval Owner), so a per-user grant cannot widen it. |
| Existing tests updated | Three older assertions that pinned the key list or Owner-vs-Admin defaults (`39`/`21` keys, Owner = Admin + audit + unlock) now include the new keys; the doctor-queue test passes `limit=1000` because the test database accumulates probe orders (a new optional `limit` on the queue endpoint). |

## 4. Files changed

Backend: new `app/models/dues.py`, `app/services/settings_service.py`, `app/services/dues_service.py`, `app/api/v1/endpoints/settings.py`, `app/api/v1/endpoints/doctor_balances.py`, migration `alembic/versions/e5d7a2c9b138_prompt17_dues_settings.py`; edited `app/models/invoice.py`, `app/models/__init__.py`, `app/core/permissions.py`, `app/schemas/payment.py`, `app/services/payment_service.py`, `app/services/report_service.py`, `app/services/refund_service.py` (one line: subtract `written_off`), `app/api/v1/endpoints/payments.py`, `app/api/v1/endpoints/reports.py`, `app/api/v1/endpoints/doctor_approvals.py` (optional `limit`), `app/api/v1/router.py`.
Frontend: new `components/common/SettleDueModal.tsx`, `features/admin/SettingsPage.tsx`; rewritten `features/dues/DuesPage.tsx` (tabs, buckets, write-off); edited `features/reports/ReportsPage.tsx`, `components/layout/Sidebar.tsx`, `App.tsx`, `api/client.ts`, `types/index.ts`.
Tests: new `tests/test_prompt17_handover_dues.py` (23 tests); edited `tests/test_prompt11_soft_delete.py`, `tests/test_prompt10d_roles_permissions.py`, `tests/test_prompt15_doctor_signoff.py` (see assumptions).
Docs: all nine. Backup (git-ignored): `backups/medscope_dcms_pre_prompt17.dump`.

## 5. Migration details

| | |
|---|---|
| Revision / `down_revision` | `e5d7a2c9b138` / `d2b6f8a1c439` |
| `alembic heads` before / after | `d2b6f8a1c439` / `e5d7a2c9b138` (single both times) |
| `alembic check` | "No new upgrade operations detected." (test and dev DB) |
| Autogenerate review | Three new tables (`tenant_settings`, `due_writeoffs`, `doctor_balance_entries`, with indexes and named unique constraint) and `invoices.written_off` (server default 0). Purely additive, no unnamed constraint to repair, nothing existing altered or dropped. |
| Round trip | `downgrade d2b6f8a1c439` then `upgrade head` on `medscope_test`: both succeed. |

**Exact command sequence against `medscope_dcms` (in order):**
1. Target check: read `DATABASE_URL` from `backend/.env` and printed its database name: `medscope_dcms`.
2. `pg_dump -Fc -d medscope_dcms -f backups/medscope_dcms_pre_prompt17.dump` (host/user/password from `backend/.env` through `PG*` variables).
3. `pg_restore -l` on that dump, searched for `tenant_settings`: **0 matches** (so the dump is pre-migration); `git check-ignore` confirmed it is ignored.
4. `ALEMBIC_DATABASE_URL=<dev URL> alembic current` -> `d2b6f8a1c439` (before).
5. `ALEMBIC_DATABASE_URL=<dev URL> alembic upgrade head` (override set explicitly to the dev URL, printed `medscope_dcms` just before) -> ran `d2b6f8a1c439 -> e5d7a2c9b138`.
6. `alembic current` -> `e5d7a2c9b138 (head)`; `alembic check` -> no new operations; row counts: 35 tables, 24 invoices all `written_off = 0`, `tenant_settings` 0 rows.
Everything before step 2 (autogenerate, upgrade, tests, round trip) ran with `ALEMBIC_DATABASE_URL` pointed at `medscope_test` and each command printed `TARGET: medscope_test` first. No other command touched `medscope_dcms` apart from the read-only row counts and the `alembic heads` check, which does not connect.

## 6. API path / operation counts

| | Before (Prompt 16) | After |
|---|---|---|
| Paths | 112 | **119** |
| Operations | 126 | **134** |
| Permission keys / money | 39 / 21 | **42 / 23** (3 new, justified above) |
| Tables in `medscope_dcms` | 32 | 35 |

New: `GET /settings`, `PUT /settings`, `GET /dues/call-list`, `GET /dues/write-offs`, `POST /invoices/{id}/write-off`, `POST /dues/write-offs/{id}/approve`, `POST /dues/write-offs/{id}/reject`, `GET /doctor-balances`. Changed: `GET /dues` (age, bucket, search), `GET /reports` (search fields, `has_due`, hold setting), `POST /reports/deliver/{id}` (hold setting), `GET /reports/printable/{id}` (commits the log, counts prints), `GET /doctor-approvals/queue` (optional `limit`).

## 7. Validation results (non-browser, actually run)

| Check | Result |
|---|---|
| `pytest` (`medscope_test` only) | **245 passed, 0 failed** (222 before + 23 new) |
| `tsc -b` | 0 errors |
| `oxlint` | 0 errors; 117 warning lines (below the previous 122; none new from the changed files) |
| `vite build` | succeeds |
| `alembic heads` / `check` | `e5d7a2c9b138` single / no new operations |

The new tests cover: key holders; settings defaults, Owner-only edit, validation, audit; hold on/off behavior and inline payment releasing the hold; search by all six terms and the due filter; reprint persistence and Duplicate; bucket boundaries, list filter, call list grouping/sorting/derivation; write-off direct, above-limit pending, Owner approve/reject/direct, cumulative limit, validation and roles, discount untouched, cancellation arithmetic; doctor balances kept apart and gated. **Not done:** no browser test, no Playwright, no claim of browser acceptance (owner checklist: `docs/TESTING.md` §20.2).

## 8. Documentation: all nine files, current truth only

| Doc | What changed |
|---|---|
| `README.md` | Counts (119/134, 35 tables, head `e5d7a2c9b138`), phase and test results replaced with Prompt 17. |
| `project-context.md` | New Prompt 17 section (what pre-existed, what is new); the stale "Current phase: Prompt 16" sentence removed. |
| `docs/SCOPE.md` | New section 12 with a **module coverage table for Modules 17 and 18** (what is covered now versus not built), the held-report setting, handover, dues, write-off, doctor-balance rules; a new row in the role matrix. |
| `docs/ARCHITECTURE.md` | ADL-072 (settings), ADL-073 (write-off), ADL-074 (doctor balances, handover findings); head and table count corrected. |
| `docs/DESIGN.md` | New section 20 (handover, Settle Due modal, Dues tabs, Settings page). |
| `docs/API.md` | Counts, permission count line, new section 12 for every new / changed endpoint. |
| `docs/WORKFLOWS.md` | Dues and handover table rows corrected; new section 15. |
| `docs/DATABASE.md` | Head, table count (35 / 34 domain), migration row, catalog entries 32 to 34, new section; a sentence from the Prompt 16 section describing its process deviation removed (current truth only). |
| `docs/TESTING.md` | New section 20 (evidence, owner checklist, known not done). |

**Module-coverage dashboard:** the dashboard that listed Module 17 as "Not established" is in the **master context file**, which I was told not to edit; nothing in the nine canonical docs contained such a dashboard. So I stated the corrected Module 17 / 18 coverage in `docs/SCOPE.md` §12 (and `project-context.md`), and the owner should update the master dashboard: **Module 17 is largely built** (search, hold-while-due with Admin/Owner release, handover log, reprint-as-Duplicate, due payment on the screen; only online viewing / courier deferred), and **Module 18 is partly built** (derived dues, age buckets, call list, write-off with limit and Owner approval, separate doctor balances structure; SMS reminders and corporate dues deferred, doctor balance data pending Modules 20 / 28).
