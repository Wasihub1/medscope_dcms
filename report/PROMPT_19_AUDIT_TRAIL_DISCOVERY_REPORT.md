# Prompt 19 — Module 23 (Audit Trail): Discovery & Gap Analysis — Findings

Investigation only. No code, schema, docs or data were changed; the live DB was not queried (code and migrations were read). Scope: the FastAPI/Postgres backend (`backend/app`). The legacy Streamlit app (`DCMS V1.py`) was not part of this inventory.

Legend: **Found / Partial / Missing**.

## 1. Inventory of audit-like mechanisms — Found (one core mechanism, plus satellites)

| # | Mechanism | Columns | who / role / when / what / before / after | Immutable? |
|---|---|---|---|---|
| 1 | **`audit_logs`** (`models/audit.py`, written only via `audit_service.log_audit_event`) | id, tenant_id, actor_id (FK staff, nullable), acting_role, action, entity_type, entity_id, before_value (text), after_value (text), created_at | All six present. before/after are free text, not structured. | **No, by convention only** (see §6) |
| 2 | `reprint_logs` (`log_reprint_event`) | tenant_id, entity_type, entity_id, reprinted_by_id, reason, reprinted_at | who + when + what (INVOICE/REPORT). No role, no before/after. Separate table. | No enforcement |
| 3 | `report_versions` | stored content | Content immutable via a hand-written Postgres trigger (Prompt 16). It is a record, not an audit log. | **Yes for content** (the only DB-level immutability in the project) |
| 4 | `test_order_events`, `assignment_history`, `notification_log` | event rows per workflow | Domain event history, partly overlapping with audit_logs (e.g. `ASSIGN_TEST_ORDER`). No acting role. | No enforcement |
| 5 | `due_writeoffs`, `refund_requests`, `doctor_approvals`, `doctor_balance_entries`, `business_days` (variance/close/reopen fields) | business records with requester/approver/reason fields | These are state tables, not logs. Each *also* writes an `audit_logs` row (`DUE_WRITTEN_OFF`, `REFUND_DISBURSED`, `DOCTOR_APPROVAL_ASSIGNED`, `CLOSE_BUSINESS_DAY`, ...). | Rows are mutable (status changes) |
| 6 | Soft-delete (`soft_delete_service`) | deleted flag + reason on the entity | Reason kept in the entity and also in `audit_logs` (`*_SOFT_DELETED` / `*_RESTORED`; reason parsed back out of `after_value` by `extract_reason`) | Entity mutable; audit row is the record |
| 7 | `UPDATE_REFERRER` / `CREATE_REFERRER` / `DELETE_REFERRER`-style entries | — | These are plain `audit_logs` rows, not a separate mechanism | see #1 |

So: **there is one real audit table, and every service uses the same helper.** The "scattered" impression is about *coverage and enforcement*, not about parallel tables. The only genuine one-offs are `reprint_logs` and the domain event tables.

Distinct `action` strings currently written: about 55 literal values plus a few templated ones (`SAMPLE_{status}`, `OUTSOURCED_{x}`, `CULTURE_{stage}`, `DAY_{kind}`, user-admin and soft-delete actions). Free text, no registry or enum.

## 2. Coverage by domain

| Domain | Status | What is logged | What is not |
|---|---|---|---|
| Bills | **Partial** | draft create/update, `CONFIRM_INVOICE`, `INVOICE_DRAFT_DISCARDED`, `INVOICE_LINE_UNLOCKED`, pre-lock cancellation, reprint (reprint_logs) | Confirm row logs Gross/Net/Paid/Due as an after-summary only; no before values |
| Discounts | **Partial / weak** | Only incidentally: the discount total is inside the draft/confirm summary strings (`Net`, `Gross`). Mode (percent/fixed, master vs individual) and per-line values are **not** recorded. No dedicated discount event. | Discount changes on drafts leave no before/after |
| Payments | **Partial** | `COLLECT_PATIENT_DUE`, `DUE_WRITEOFF_*`, `REFUND_*`, `COMMISSION_REVERSED` | The initial payment taken at invoice confirm (`invoice_service.py:513`) is covered only by the `CONFIRM_INVOICE` summary; no per-payment event |
| Reports | **Partial** | `REPORT_FINALIZED`, `DELIVER_REPORT`, notification-due, reprint (reprint_logs) | Result entry is logged (`RESULT_SAVED_DRAFT` / `RESULT_ENTERED`); doctor approval logged. No report *view* log (§3) |
| Stock | **Missing (stub)** | One marker, `STOCK_CONSUMPTION_INTEGRATION_TRIGGERED`. No inventory module exists. | Everything real |
| Accounting | **Found** | `OPEN/CLOSE/REOPEN_BUSINESS_DAY`, `DAY_*`, `POST_ADJUSTING_ENTRY` (Prompt 18) | Journal entries themselves rely on their own tables |
| Settings | **Found** | `SETTING_CHANGED` with before/after | — |
| Permissions | **Found** | `USER_PERMISSIONS_CHANGED`, `USER_ROLE_CHANGED`, create/update/deactivate/restore/soft-delete, password reset, lock/unlock, login success/failed/logout | — |
| Catalog / reference data (outside the spec list) | **Partial** | test soft-delete/restore, reference-range create/version/retire, referrer create/update | Test **price and catalog edits**: no update endpoint under `tests.py` apart from delete/restore, so nothing to log yet; confirm in 19B |
| Patients | **Partial** | `CREATE_PATIENT` | No patient edit action found |

**Zero-coverage domains:** stock (stub only) and report-viewing. Discounts are the weakest of the domains that nominally have coverage.

## 3. Report-view logging — **Missing (confirmed)**
- `GET /reports/{id}`, `/reports/{id}/snapshot`, `/reports/ready/{id}/preview` write nothing.
- `GET /reports/printable/{id}` and `POST /reports/{id}/print-events` write `reprint_logs`, which is reprint, not view, and is a different table with no role column.
- There are no report-view rows in `audit_logs`.

## 4. Vendor session log — **Missing (confirmed)**
- No Vendor role exists in the backend (grep for `vendor` returns nothing). Roles are Owner, Admin, Receptionist, Cashier, Lab Tech.
- Only `AUTH_LOGIN_*` / `AUTH_LOGOUT` rows exist, and they apply to tenant staff. The Platform Dev concept belongs to the Streamlit app and is not modelled in this backend.
- "Immutable even for vendor" therefore has no subject today and needs a decision on what a Vendor is.

## 5. "Viewing audit is a separate permission" — **Found**
- Permission key `audit.view` (`core/permissions.py:85`), enforced with `require_permission("audit.view")` on both `GET /audit` and `GET /audit/meta`.
- It is a distinct key, placed in `_OWNER_ONLY` defaults, so it is ON for Owner only; an Owner may grant it to an Admin through per-user overrides. Not folded into a role check.
- Viewer scope: read-only, paginated, filters on action, entity type, actor, date range. **No export**, no report-view or session-log tab.

## 6. Immutability and retention — **Partial / Missing enforcement**
- **ORM/API level:** no endpoint updates or deletes `audit_logs`. The viewer router says "no write, delete or export operation exists here". Good.
- **DB level: nothing.** No trigger, no REVOKE, no RULE on `audit_logs` or `reprint_logs`. The only immutability trigger in the project is `report_versions_immutable` (Prompt 16).
- **Code paths that *can* delete audit rows:**
  - `backend/scripts/sql/cleanup_test_data.sql` deletes from `audit_logs` (about line 465) and `reprint_logs` (about line 470) for test entities. It was **executed and committed on the main dev DB on 2026-11-11** (`TEST_DATA_CLEANUP` row, per `docs/DATABASE.md`). That directly contradicts "nobody can delete", though it targeted test data.
  - Any superuser/DB-owner connection can UPDATE or DELETE.
  - `scripts/seed.py` writes `AuditLog` rows and the `d7e5a91c4f02` migration touched `audit_logs` sequences.
- **FK note:** `audit_logs.actor_id` references `staff.id`. User delete is soft (`USER_SOFT_DELETED`), but `_sync_single_role` hard-deletes `StaffRole` rows, and the `staff` relationships cascade delete-orphan. Hard-deleting a staff row would be blocked or would orphan audit rows; confirm in 19B.
- **Draft discard** hard-deletes the `invoices` draft row (`invoice_service.py:678`). The audit row survives, but the entity it points to is gone.
- **Retention:** no TTL, purge or archival logic anywhere. Nothing conflicts with "kept forever", but nothing enforces it either.
- **Tenant isolation:** `tenant_id` is a plain column, no FK to a tenant table on `audit_logs`.

## 7. Fragmentation assessment

**Assessment: (a) with a small (b) component.** The project is not facing several incompatible mechanisms. It has one genuine table (`audit_logs`) with the right six columns, used consistently through a single helper by about 25 services. The real gaps are:
1. **Enforcement:** no DB-level append-only guard, and an approved delete script exists.
2. **Coverage holes:** report-view logging, discount detail, per-payment detail, stock, vendor/session log.
3. **Structure:** before/after is unstructured text and `action` is unregistered free text; this limits exports and filtering.
4. **Satellites:** `reprint_logs` (no role, no before/after) is the one one-off that should fold into `audit_logs` (or be mirrored there). `test_order_events` / `assignment_history` are workflow history and can stay.

## Recommendation

Build Module 23 as **(a) an extension of `audit_logs`**, plus folding `reprint_logs` in (a light version of (b)). No fresh parallel table is needed. If the existing free-text rows must stay readable, keep columns as they are and add only additive columns.

**Decisions the 19B prompt needs to make:**
1. **Immutability enforcement:** Postgres trigger rejecting UPDATE/DELETE (and TRUNCATE) on `audit_logs`, like `report_versions_immutable`; what happens to `cleanup_test_data.sql` (retire it, or restrict to a clearly marked test tenant with a documented bypass). Include `reprint_logs` or retire it.
2. **Retention:** state "kept forever" explicitly and add a test that proves no purge path exists; decide on archival if the table grows.
3. **Report-view logging:** which endpoints count as a "view" (`GET /reports/{id}`, `/snapshot`, `/preview`, printable) and whether to log once per user per report per window to avoid noise; whether to add an acting-role column to the reprint path.
4. **Vendor / session log:** define what a Vendor is (platform Dev from the Streamlit app, or a new role), where its sessions are stored, and whether login/logout audit rows suffice or a dedicated session table is needed.
5. **New instrumentation vs. existing:**
   - New: report views, discount detail (mode, value, master vs line, before/after), per-payment events at confirm, stock (depends on inventory existing), vendor session.
   - Already present: settings, permissions/roles/auth, accounting/day close, write-offs/refunds, finalization/delivery, soft-delete, reference ranges.
6. **Structured before/after:** keep text, or add a JSON column and an action registry (enum or constants) so new actions are validated.
7. **Viewer scope:** keep `audit.view` as the separate permission; decide whether report-view logs and session log need their own keys or tabs, and whether the viewer itself should be audited ("who viewed the audit").
8. **Export:** format (CSV with BOM, like `accounting_report_service`), who may export, and whether export is itself audited.
9. **Visibility of the actor:** `actor_id` is nullable and `acting_role` is free text; decide whether system/background actions need a reserved actor.
10. **Backfill:** do not fabricate history for the coverage gaps; document the cutover date.
