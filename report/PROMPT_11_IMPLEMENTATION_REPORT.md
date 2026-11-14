# Prompt 11 Implementation Report — Soft Delete / Draft Discard / Confirm Dialog / Audit Viewer

Date: 2026-11-13. Written for: the project owner (acceptance and decisions).
This run **resumed an interrupted session**. Everything below was checked against the real repository, not against the earlier session's claims.

## 0. What I found when resuming

| Item | State found |
|---|---|
| Migration `a4d8c2e6f1b7` | Written, already applied to `medscope_dcms` (`alembic current` = head), pre-migration dump `backups/medscope_dcms_pre_prompt11.dump` exists |
| Backend | Complete: soft-delete service, user delete/restore, referrer/test delete/restore/deleted lists, draft discard, audit endpoint, permissions, login/session gate, selection filters |
| Backend tests | `tests/test_prompt11_soft_delete.py` (13 tests) present and passing |
| Frontend | **Not started** (no ConfirmDialog, no Deleted view, no Audit page, no discard button) |
| `medscope_test` stray users | **Not done**, and there were **98** stray LAB_TECH fixtures, not 5 (every pytest run adds more) |
| Docs, README, project-context, report | **Not done** (still said "Prompt 11 not implemented") |

Git state: `git status` still shows the same 13 tracked-but-deleted files; I did not touch them. Nothing committed, pushed, stashed or reset. Starting head was `f3c9a1d7e5b2` per the prompt; the dev DB was already at `a4d8c2e6f1b7` when I resumed.

## Done

### Backend (verified, not re-written)
- Soft delete (`deleted_at`, `deleted_by_id`, `delete_reason`) on `staff`, `referrers` (doctors and 3rd parties share this table), `tests`; indexes on `deleted_at`.
- Delete requires a non-empty reason (400), the manage permission (403), 409 if already deleted; restore and Deleted lists need the same permission.
- User delete: self-delete refused, Owner accounts only by Owner, last active user-manager protected; user forced inactive, sessions revoked (same transaction), 10F room-emptying routine reused; login and session validation also check `deleted_at`.
- New-selection filters: `/tests`, `/referrers`, global search, assignment technician list, routing, invoice create/draft/finalize (400 for deleted test or referrer).
- Draft discard `DELETE /invoices/{id}/draft`: DRAFT only (409 otherwise), creator or ADMIN/OWNER (403 otherwise), refused with 409 if the draft somehow has a visit/lines/payments/refunds, audit row `INVOICE_DRAFT_DISCARDED` written first in the same transaction.
- Audit viewer: `GET /audit-logs` and `/audit-logs/meta`, `audit.view`, filters action / entity / actor / date range, newest first, paginated, no write/delete/export.

### Frontend (done in this run)
- `components/common/ConfirmDialog.tsx` — one reusable dialog on the existing `Modal`: names the item, one-sentence effect, required reason gating (`isConfirmReady`), Cancel.
- `features/admin/CatalogAdminPage.tsx` (`/catalog-admin`) — **one shared screen** for Test and Doctor/3rd-party delete, plus the shared Deleted view (Users, Doctors/3rd parties, Tests) with Restore.
- `features/admin/AuditLogPage.tsx` (`/audit-log`) — read-only list, filters, before/after detail, pagination.
- User Management: **Delete** button (disabled on own row) with ConfirmDialog; Deactivate unchanged.
- Invoices: **Discard** button on Draft rows with ConfirmDialog (no reason).
- Sidebar entries "Catalog & Deleted" and "Audit Log" (permission-gated); API client methods and types.

### Section 6 cleanup (`medscope_test` only)
Using the new `delete_user` service (audited, soft delete, not hard delete, because the users are referenced by audit and session rows and soft delete is the feature this prompt built), 98 stray LAB_TECH users (usernames ending in an 8-hex suffix) were soft-deleted by `admin_tariq` in two runs. The script asserted `current_database() == 'medscope_test'`; `medscope_dcms` was never connected to. Two seeded technicians (`tech_kamal`, `tech_nasrin`) remain. The `conftest.py` hard guard was not modified. The one-off script lived in the session scratchpad, not in the repo.

### Docs (all nine)
ARCHITECTURE (ADL-052 to ADL-055, head, frontend convention, M23 slice), SCOPE (decision table, M23 gaps), API (new §6, counts), WORKFLOWS (§9), DESIGN (§14), DATABASE (new section, chain, head), TESTING (§14 evidence + owner checklist P11-1 to P11-13; §12 and §13.4 intact), README, project-context. "Not implemented" lines for Prompt 11 were flipped. Past reports and the master context file were not edited.

## Assumptions table (owner to confirm or reverse)

| # | Assumption | Notes |
|---|---|---|
| A1 | Permissions: User delete reuses `user.manage`. Doctors/3rd parties use new `referrer.manage`, tests use new `test_catalog.manage`, plus new `audit.view`. | The existing `referrer.create` / `test_catalog.view` are front-desk keys held by Receptionist/Cashier, so reusing them would let front desk delete. Defaults: Admin+Owner for the two manage keys; `audit.view` Owner only, grantable to Admin. Keys 35 → 38, money 20 → 21 (`audit.view`). |
| A2 | User deleted vs inactive: deleted forces `active = false` and `deleted_at` is also checked at login/session. Reactivating a deleted user is refused. | Restore leaves the user inactive; Admin/Owner then Reactivates. |
| A3 | Restore triggers no room/assignment side effect. | Reactivate runs the normal release-on-join. |
| A4 | One shared Deleted view for all four entities (not four screens). | `/catalog-admin`, Deleted tab. |
| A5 | "Doctor" = a `referrers` row of doctor type; doctor sign-off attestation is by DOCTOR-role **users**, covered by user delete. | |
| A6 | Delete history is the append-only audit log (reason inside the delete row's `after_value`), not a history table. | Restore clears the columns. |
| A7 | There was no existing UI to manage tests/referrers, so delete lives on the new Catalog & Deleted page. | |
| A8 | "5 stray users" was stale; 98 cleaned. Each pytest run creates new LAB_TECH fixtures again, so the pile regrows. | Suggest making test fixtures clean up after themselves (not done). |
| A9 | Draft discard needs `invoice.create` plus (creator or ADMIN/OWNER). | |

## Partial / Blocked / Deferred
- **Not done:** no automated frontend test (project has no unit-test framework); ConfirmDialog gating verified by code review only. No Playwright spec for the new screens (browser testing is banned for the agent).
- **Not run:** browser acceptance. Owner does it via `docs/TESTING.md` §14.3. I make no claim of browser verification.
- **Deferred (explicitly out of scope):** the rest of Module 23, Module 14, doctor sign-off, `performing_role`, 671 unmapped-room tests, urgent-fee rule, master discount (A3), reduced motion.

## Migration / head
Before: `f3c9a1d7e5b2`. After: `a4d8c2e6f1b7` (single head, `alembic heads`). `alembic check` → "No new upgrade operations detected." All columns nullable; dump `backups/medscope_dcms_pre_prompt11.dump` taken before applying. Table count unchanged (29).

## Validation (real results, this run)
| Command | Result |
|---|---|
| `python -m pytest` (`medscope_test`) | **135 passed**, 0 failed (122 before Prompt 11 + 13 new). Run twice (before and after the cleanup and frontend work), same result |
| `alembic heads` / `current` / `check` | `a4d8c2e6f1b7` single head / at head / clean |
| `tsc -b` | 0 errors |
| `oxlint` | 0 errors; warnings only (existing baseline style; 2 `set-state-in-effect` warnings in the new pages match the project's existing pattern) |
| `vite build` | succeeds (chunk-size notice only) |
| OpenAPI | 96 paths / 110 operations (was 85 / 98) |

## Regression check
- Full previous suite (all Prompt 04–10F tests) still passes with the Prompt 11 changes: 135/135.
- Reviewed every `select/get` of `Test`, `Referrer` and `Staff` in `backend/app`: new-selection paths filter deleted rows; paths that read existing records by id (orders, results, old lines, commission) intentionally do not, so old records keep working.
- No change to `set_user_active`, billing snapshots, or permissions of existing keys.
- Frontend `tsc -b`/`vite build` clean, existing pages only gained additive buttons.

## Doubtful things noticed, not fixed
1. `medscope_test` accumulates LAB_TECH/other fixtures on every run (A8); other roles also pile up (e.g. ~170 receptionists).
2. The Invoices page already carried many unused imports (oxlint warnings) — pre-existing.
3. `GET /tests` for the catalog screen is capped by `limit` (200 in the new page); search narrows it.
4. Audit `before/after` text may contain amounts; hence `audit.view` is classified as a money key (not given to LAB_TECH/DOCTOR).

## Files changed (this run) / created in the Prompt 11 work
Backend (earlier session, verified): `alembic/versions/a4d8c2e6f1b7_prompt11_soft_delete.py`, `core/soft_delete.py`, `core/permissions.py`, `schemas/soft_delete.py`, `services/soft_delete_service.py`, `services/user_admin_service.py`, `services/invoice_service.py`, `services/auth_service.py`, `services/routing_service.py`, `services/search_service.py`, `services/assignment_service.py`, endpoints `audit.py`, `users.py`, `referrers.py`, `tests.py`, `invoices.py`, `router.py`, models `user.py`/`referrer.py`/`test.py`, `tests/test_prompt11_soft_delete.py`.
Frontend (this run): `components/common/ConfirmDialog.tsx`, `features/admin/CatalogAdminPage.tsx`, `features/admin/AuditLogPage.tsx`, `features/users/UserManagementPage.tsx`, `features/invoices/InvoicesPage.tsx`, `components/layout/Sidebar.tsx`, `App.tsx`, `api/client.ts`, `types/index.ts`.
Docs (this run): the nine docs listed above and this report.
