# Prompt 19B — Module 23 (Audit Trail): Build Report

Written for: the project owner. Browser acceptance has **not** been run; section 6 is the click path for it.

## 1. Found / confirmed before building

| Check | Finding |
|---|---|
| Cleanup script | `backend/scripts/sql/cleanup_test_data.sql` and its `sql/` folder **no longer exist**. Nothing under `backend/` or `Dev.ps1` touches `audit_logs` or `reprint_logs` with a delete. The only remaining deleters are the **test-fixture helpers** `tests/fixture_cleanup.py` (see section 2A: they run in `medscope_test` only). |
| `reprint_logs` dependents | Two writers (`invoices.py` reprint, `reports.py` print-events and the printable endpoint through `report_service`) and **one reader**: the report print counter (`reprint_count`, Duplicate marking) in `report_service`. The frontend only displays the counter returned by the API. Nothing else reads the table, so it was **dropped** in the migration. Seed script imported the model; fixed. |
| Catalog-test edit endpoint | Still absent. `tests.py` has only soft delete and restore (both audited). No edit event is needed and none was built. |
| Dev DB baseline | 591 `audit_logs` rows, 49 `reprint_logs` rows; `medscope_app` owns the table. |

## 2. Done / Partial / Blocked

| Item | Status | Notes |
|---|---|---|
| **A. Immutability** | **Done** | Migration `a19b5c7d9e31`: trigger function `audit_logs_append_only()`, per-row trigger for UPDATE/DELETE, per-statement trigger for TRUNCATE. No bypass or exception path inside the trigger. Verified against the dev DB in rolled-back transactions (UPDATE and TRUNCATE both refused) and by tests. |
| Reprint fold-in (decision 2) | **Done** | Reprints now go through `log_audit_event` (`INVOICE_REPRINTED` / `REPORT_REPRINTED`, acting role, before = "N earlier print(s)", after = "Print #N | reason: …"). 49 legacy rows copied into `audit_logs` (original time kept; role `UNKNOWN`, because the old table never stored a role and none was invented), table dropped. Migration is idempotent; downgrade restores `reprint_logs` from the audit rows and never deletes audit rows. |
| **B. Discounts** | **Done** | `INVOICE_DISCOUNT_CHANGED` on draft save/edit, only when the discount setup changed (master mode+value, each line's mode+value; line values are shown as inactive while a master discount is active). `INVOICE_DISCOUNT_CONFIRMED` at confirm, with the draft's discount as "before" (or "No discount") and the final state plus total taka as "after". |
| Payments | **Done** | `INVOICE_INITIAL_PAYMENT` (entity `PAYMENT`, id = payment id), separate from `CONFIRM_INVOICE`: amount, channel (and detail), reference, payer (patient name and code), received-by name, invoice paid/due after; before = paid 0 and net. |
| Report views (decision 4) | **Done** | One row per successful `GET /reports/{id}`, `/snapshot` and `/ready/{id}/preview`; no throttling; a 404 writes none. **Choice made:** the preview is for a *test order* that has no report version yet, so it writes `REPORT_PREVIEW_VIEWED` with `entity_type=REPORT` as specified but `entity_id` = the **test order id** (the text says so). The two report-version views write `REPORT_VIEWED` with the report version id. If the frontend calls both detail and snapshot on one open, that is two rows, as specified ("every open"). |
| Stock | **Left as the stub** | Only `STOCK_CONSUMPTION_INTEGRATION_TRIGGERED` exists; no inventory module, nothing invented. |
| Catalog edit gap | **Confirmed absent** | See section 1. |
| **C. Viewer: filters** | **Done** | New: domain (grouping of all ~60 action names into bills, discounts, payments, reports, stock, accounting, settings, permissions, plus lab, catalog, audit and other so no row is unreachable; defined once in `core/audit_domains.py`) and acting role. Existing action, entity, actor (now a name dropdown), date range kept. Each row shows its domain. |
| Viewer: search | **Done** | Free text over action, entity type, entity id, before and after (case-insensitive; `%` and `_` are literal). Debounced in the UI. |
| Viewer: view-only | **Done** | Only GETs exist under `/audit-logs`; a test asserts it and that PUT/PATCH/DELETE return 404/405. |
| Viewer: export | **Done** | `GET /audit-logs/export`, same filters, `audit.view`, CSV with BOM via the accounting `to_csv`. Cells starting `=`, `+`, `-`, `@` get an apostrophe so Excel cannot run them as formulas. The export writes `AUDIT_LOG_EXPORTED` (who, role, filters, row count). No row cap. |
| `audit.view` | **Unchanged** | Owner by default, grantable to Admin; no new permission key (still 43 / 24). |
| Vendor / session log (decision 3) | **Not built, as decided** | Dated decision recorded in `docs/SCOPE.md` section 15. |
| Retention test (decision 6) | **Done** | One test scans `backend/` (outside migrations) for any delete/purge/truncate/update of `audit_logs`; another asserts the database refuses it. |

### Things to know (honest notes)
1. **Test fixtures need a test-only exception.** `tests/fixture_cleanup.py` hard-deletes throwaway users and referrers (and the audit rows about them) in `medscope_test`. With the trigger there is no bypass, so those helpers now switch the triggers off inside their own transaction, only after asserting the database is `medscope_test`, and switch them back on before returning. This is test infrastructure; nothing under `backend/` can do it (a test enforces that).
2. **The trigger is not proof against the table owner.** The app's own DB role owns `audit_logs`, so that role (or a superuser) can still `ALTER TABLE ... DISABLE TRIGGER` or drop it. Normal application and SQL writers are blocked. Tighter database roles are a separate hardening step.
3. **Test DB round trip surfaced a bug that is fixed:** the first downgrade/upgrade copied the reprint rows twice. The migration's copy is now idempotent; the 185 surplus duplicate rows in `medscope_test` (disposable) were removed with the trigger switched off in that database only, and a second round trip left the count unchanged at 191.
4. **Domain grouping is name-based.** A new action name not covered by a rule appears under "Other" until a rule is added (this is the "no action registry" decision).
5. The legacy 49 reprint rows say "Reprint (copied from the legacy reprint log; the acting role was not recorded then)" with role `UNKNOWN`.

## 3. Files changed

Backend: `alembic/versions/a19b5c7d9e31_prompt19b_audit_immutable_fold_reprints.py` (new); `app/core/audit_domains.py` (new); `app/models/audit.py`, `app/models/__init__.py` (ReprintLog removed); `app/services/audit_service.py` (reprint writes via the audit log, `count_reprints`); `app/services/invoice_service.py` (discount and initial-payment events); `app/services/report_service.py` (view events, print counter from the audit log); `app/api/v1/endpoints/audit.py` (filters, search, meta, export); `endpoints/reports.py`, `endpoints/invoices.py`; `app/schemas/soft_delete.py`; `scripts/seed.py` (import).
Frontend: `src/features/admin/AuditLogPage.tsx`, `src/api/client.ts`, `src/types/index.ts`.
Tests: `tests/test_prompt19b_audit.py` (new, 13), `tests/fixture_cleanup.py`, `tests/test_prompt17_handover_dues.py` (reads the audit log instead of `reprint_logs`).
Docs: `docs/SCOPE.md`, `docs/API.md`, `docs/DATABASE.md`, `docs/TESTING.md`. The master context file and `project-context.md` were not touched.

## 4. Validation actually run

- `pytest`: **297 passed, 0 failed** (284 earlier + 13 new). `python -m py_compile "DCMS V1.py"` and `accounting.py`: pass.
- `tsc -b`: pass. `oxlint`: exit 0, warnings only (existing ones plus one `set-state-in-effect` note in `AuditLogPage.tsx` for the debounce effect, same kind as other pages). `vite build`: pass.
- `alembic heads`: single head `a19b5c7d9e31`. `alembic check`: "No new upgrade operations detected." Round trip (downgrade -1, upgrade head) on `medscope_test`, run twice.
- **Backup and migration command sequence** (password read from the git-ignored `backend/.env`, not shown):
  ```
  set PGPASSWORD=<from backend/.env>
  "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -h 127.0.0.1 -p 5432 -U medscope_app -F c -b -f backups\medscope_dcms_pre_prompt19b.dump medscope_dcms
  cd backend
  python -m alembic upgrade head
  ```
  The dump (261,831 bytes) is git-ignored. Afterwards on `medscope_dcms`: 640 audit rows (591 + 49 copied, 49 with role `UNKNOWN`), `reprint_logs` gone, two triggers present on `audit_logs`; an UPDATE and a TRUNCATE inside rolled-back transactions were both refused.
- **Not run:** any browser test, and any e2e (Playwright) spec.

## 5. Documentation changes

- `docs/SCOPE.md`: old "Module 23 still owes" line replaced; new section 15 (current truth for Module 23) including the dated Vendor-deferral decision (2026-11-14).
- `docs/API.md`: 130 paths / 145 operations; audit list/meta/export rows; reprint wording; new section 14 (new actions, report-view logging).
- `docs/DATABASE.md`: `reprint_logs` entry removed from the table list and diagram; new section for migration `a19b5c7d9e31` (trigger, fold-in, backup, round trip, test-only exception, owner-role limit).
- `docs/TESTING.md`: new section 24 (verification and click path).

## 6. Owner click path (browser acceptance)

1. **Audit Log** (Owner): filters for search, domain, action, entity, person, role, two dates; Export button.
2. New Invoice: save a draft, add a 10% line discount, save; change it to 40 Tk, save. **Audit Log > Domain = Discounts**: two `INVOICE_DISCOUNT_CHANGED` rows; **Details** shows Before / After.
3. Finalize with a 100 Tk payment: `INVOICE_DISCOUNT_CONFIRMED` and `INVOICE_INITIAL_PAYMENT` appear next to `CONFIRM_INVOICE` (payer, channel, received-by in the text).
4. Open a finalized report from Reports: Audit Log > Domain = Reports shows a `REPORT_VIEWED` row per open with your name and role. Open a ready-result preview: `REPORT_PREVIEW_VIEWED` (entity id is the test order).
5. Type part of an invoice or patient number in **Search**: matching rows only. Pick a Role: only that role's rows. Click **Clear filters**.
6. Set a domain and a role, click **Export CSV (current filters)**, open in Excel: only those rows, a BOM so accents read correctly. The log then shows `AUDIT_LOG_EXPORTED` with your filters and the row count.
7. Sign in as an Admin without `audit.view`: no Audit Log menu; the export URL returns 403.
8. Print a report and an invoice receipt twice: second report print is marked Duplicate (count from the audit log); two `*_REPRINTED` rows.
9. Optional, only with a real database session: `UPDATE audit_logs SET action = 'X'` or `DELETE FROM audit_logs` fails with "audit_logs is append-only".
