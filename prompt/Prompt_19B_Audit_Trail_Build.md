# Prompt 19B — Module 23 (Full Audit Trail): Build

Follow-up to Prompt 19 (`PROMPT_19_AUDIT_TRAIL_DISCOVERY_REPORT.md`). That investigation found **one** real audit mechanism (`audit_logs`, written via `audit_service.log_audit_event`, already used consistently by ~25 services) plus one satellite (`reprint_logs`) that should fold in. This prompt builds Module 23 as an **extension of `audit_logs`**, not a new parallel system.

**Owner's objective for this module, in his own words:** an Owner should be able to open the audit log and get *any* business-related information — filtered, searched, view-only — and export as much of it as a given business report needs. Treat the Owner-facing viewer (filtering, search, export) as a first-class deliverable here, not an afterthought to the backend logging.

**Backup discipline (standing rule, every prompt):** `pg_dump` into git-ignored `backups/` **before** any Alembic migration runs against `medscope_dcms`. Disclose the exact command sequence in the report.

## 1. Decisions already made (do not re-litigate these)

1. **Immutability enforcement.** Add a real Postgres trigger on `audit_logs` (and `reprint_logs`, until folded in — see #2) modeled on the existing `report_versions_immutable` trigger (Prompt 16): reject `UPDATE`, `DELETE`, and `TRUNCATE` outright, no bypass, no exception path. The owner has already removed `backend/scripts/sql/cleanup_test_data.sql`'s audit-deleting lines himself — confirm that script no longer touches `audit_logs`/`reprint_logs` at all before writing the trigger, and flag it in the report if it still does.
2. **`reprint_logs` folds into `audit_logs`.** Going forward, reprint events are written through the same `audit_service.log_audit_event` helper (with `acting_role` and structured before/after, which `reprint_logs` currently lacks), not a separate table. Migrate existing `reprint_logs` history into `audit_logs` so nothing is lost, then decide based on what you find: if nothing else reads `reprint_logs` directly (check for any "reprint_count" or similar display logic that queries it), drop the table in the same migration; if something still depends on it, leave it as a read-only legacy table and say so plainly in the report rather than guessing.
3. **Vendor / session log: fully deferred, not built in this prompt.** The "Vendor" concept in the spec traces to the legacy Streamlit prototype's "Platform Dev" idea, which has no equivalent in this backend and no connection to this audit log — multi-tenancy/vendor-profile work hasn't started. Do not create a Vendor role, a session table, or any related permission here. Record this explicitly as a dated decision in `docs/SCOPE.md`: Vendor has no current subject in this system; it will be scoped as its own module once tenancy/vendor-profile work begins.
4. **Report-view logging: simple, one row per view, no throttling.** Every open of a finalized report (`GET /reports/{id}`, `/reports/{id}/snapshot`, `/reports/ready/{id}/preview`) writes one `audit_logs` row (who, acting role, when, `entity_type=REPORT`, `entity_id`, action e.g. `REPORT_VIEWED`). Do not dedupe or rate-limit — this is ordinary usage history, not noise.
5. **Before/after stays free text for now.** Do not add a JSON column or an action-string registry/enum in this prompt — out of scope. Keep every new write in the same style as existing `audit_logs` rows.
6. **Retention:** no TTL, purge, or archival logic exists or is to be added. Add one test that asserts no code path deletes/purges `audit_logs` rows (besides the immutability trigger itself blocking it).

## 2. What to build

### A. Immutability (schema)
- New Alembic migration: trigger function + trigger on `audit_logs` blocking UPDATE/DELETE/TRUNCATE; same (or folded) for `reprint_logs` per decision #2.
- `pg_dump` before applying, as always.

### B. Coverage gaps — close the real ones
Per the discovery report's domain table, add proper `audit_logs` events (with real before/after, not just summary text) for:
- **Discounts:** mode (percent/fixed), master-discount vs. line-discount, old value → new value, on both draft edits and confirm — not just embedded inside the invoice-confirm summary string.
- **Payments:** a dedicated event for the initial payment taken at invoice confirm (`invoice_service.py:513`), separate from `CONFIRM_INVOICE`, with amount/channel/payer.
- **Report views:** per decision #4.
- Leave **stock** as the existing stub (`STOCK_CONSUMPTION_INTEGRATION_TRIGGERED`) — no inventory module exists yet, nothing real to log. Say so in the report rather than inventing something.
- Confirm in the report whether the catalog-test price/edit gap the discovery report flagged ("no update endpoint under `tests.py` apart from delete/restore") is still true; if an edit endpoint genuinely doesn't exist, no audit event is needed for it yet — just confirm, don't build a catalog-edit feature here.

### C. The Owner-facing audit viewer — primary deliverable
Build this out properly, since it's the actual point of the module for the owner:
- **Filters:** action/event type, domain (bills, discounts, payments, reports, stock, accounting, settings, permissions — group the ~55 action strings into these domains for the filter UI), actor, acting role, entity type, date range. Keep the existing filters (action, entity type, actor, date range) and add the domain grouping and acting-role filter.
- **Search:** free-text search across action, entity type/id, and the before/after text.
- **View-only:** confirm (as the discovery report found) that no write/update/delete/export-bypass path exists on this screen — keep it that way.
- **Export:** CSV, same style/format as `accounting_report_service`'s existing CSV export (BOM, etc.), respecting whatever filters are currently applied. Same `audit.view` permission gates export — no new permission key needed. The export action itself writes an `audit_logs` row (who exported, what filter set, when) — i.e. the audit viewer audits itself.
- Keep `audit.view` as the separate, Owner-only-by-default permission it already is; no change to that.

## 3. What NOT to do
- No Vendor role, session table, or related permission (decision #3).
- No JSON/structured-before-after column, no action registry (decision #5).
- No inventory/stock module.
- No large new automated test suite — per the standing Claude Code workflow split, add only the handful of tests that prove the correctness properties that can't be checked otherwise (immutability trigger rejects writes; no purge path exists; new discount/payment/report-view events are written correctly; export respects filters). Confirm the existing pytest suite, `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check` all still pass.
- Do not touch the master context file.
- Documentation: current-truth only, no historical/superseded sections kept.

## 4. Deliverable (same report format as previous prompts)
1. What was found/confirmed before building (cleanup script status, `reprint_logs` dependents, catalog-edit endpoint check).
2. Done / Partial / Blocked per item in Section 2.
3. Files changed.
4. Validation actually run (tests, lint, build, alembic heads/check), with the `pg_dump` command sequence disclosed.
5. Documentation changes (which docs, what changed) — including the dated `docs/SCOPE.md` entry recording the Vendor-deferral decision.
6. A consolidated click path for the owner's browser acceptance testing (viewer filters/search/export, a discount edit showing up with before/after, a report view producing a row, and — if testable without faking a DB superuser session — an attempt to update/delete an `audit_logs` row failing).
