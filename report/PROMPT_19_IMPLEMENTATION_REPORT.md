# Prompt 19 Implementation Report: Doctor / 3rd-party Edit

**Date:** 2026-11-14. No browser testing. Nothing committed, pushed, stashed or reset (git unchanged). Master context file not edited. **No schema change, no migration** (`alembic heads` still `f9a2c4d6e8b1`; `medscope_dcms` untouched, so no `pg_dump`).

## 1. What I found first
- **No edit capability existed anywhere.** The referrers API had only list, create, soft delete, restore and the deleted list (no PUT/PATCH); the frontend had no update call. On Catalog & Deleted the rows only had **Delete**. The inline-add during billing (`POST /referrers`) can only add a new referrer, not edit a selected one. Nothing is hidden elsewhere that needed surfacing.
- **No rate-card editor exists** in the repository (no table, endpoint or screen). The referrer table holds only commission type / rate, which are write-only at creation (never returned). So there was nothing to link to; I left commission and rates untouched and did not build one.
- **Fields to edit:** exactly what creation captures: name, type, phone, registration no., specialty, chamber address (all already columns).
- **Tests tab:** the test catalog shows the same pattern (Delete only); I did not build an edit there, per scope.

## 2. Done / Partial / Blocked
**Done.** `PATCH /referrers/{id}` (key `referrer.manage`, the same as Delete; no new key). Updates the existing row in place; only the fields sent change; empty name or type refused; 404 for unknown id; 409 for a deleted record (restore first); commission is neither accepted nor returned; audited as `UPDATE_REFERRER` with old and new values. Frontend: **Edit** button beside **Delete** on Doctors & 3rd parties, opening an edit modal (`ReferrerEditModal.tsx`) with those six fields, saving through the new endpoint and reloading the list. Delete / restore code is unchanged.

## 3. Snapshot safety (how I checked)
- **Doctor approvals:** `doctor_approvals` copies `doctor_name` and `doctor_registration_no` at signing, and the Prompt 16 report snapshot reads them from the approval. **Test proves** a signed approval keeps its name and registration number after the doctor is renamed and the number changed.
- **Bills:** invoices store only `referrer_id`; the bill does not print a registration number. Bill and report **listings show the referrer's current name** (live read, e.g. `referred_by` in the deliverable list), so a rename appears on them. This is how they always worked; I flagged it rather than reworking it (it is a data-flow change, not a one-line fix, and the name is not a legal identifier like the registration number). The Doctor balances view in Dues also reads the live name / registration number.
- **Commission ledger:** no commission entries exist (Module 19 not built); commission fields are not touched by the edit.
- **Delete / restore** unchanged; rows keep their id, so bills stay linked.

## 4. Files changed
Backend: `schemas/referrer.py` (`ReferrerUpdate`), `api/v1/endpoints/referrers.py` (PATCH).
Frontend: new `features/admin/ReferrerEditModal.tsx`; edited `features/admin/CatalogAdminPage.tsx`, `api/client.ts` (`updateReferrer`).
Tests: new `tests/test_prompt19_referrer_edit.py` (3 tests).
Docs: see section 6.

## 5. Validation (actually run)
| Check | Result |
|---|---|
| `pytest` (`medscope_test` only) | **284 passed, 0 failed** (281 + 3 new) |
| New tests | edit updates in place with audit and no commission exposure; edit needs the same key as delete (Receptionist, Cashier, Lab Tech 403 on both; deleted record 409; Admin and Owner allowed); signed doctor approval snapshot unchanged after rename / registration change |
| `tsc -b` / `vite build` | 0 errors / succeeds |
| `oxlint` | exit 0 |
| OpenAPI | 129 paths / 144 operations (was 128 / 143) |
| `alembic heads` | `f9a2c4d6e8b1`, unchanged (no migration, so no `alembic check`) |
Browser: **not run**; owner checklist is `docs/TESTING.md` §23.

## 6. Documentation (current truth only)
| Doc | Change |
|---|---|
| `docs/API.md` | Counts 129 / 144; new `PATCH /referrers/{id}` row in the Prompt 11 delete / restore table |
| `docs/DESIGN.md` | New §22 (Edit button and modal) |
| `docs/SCOPE.md` | New §14: the gap is closed; who can edit; what snapshots exist and the live-name behavior of listings |
| `docs/ARCHITECTURE.md` | ADL-079 |
| `docs/WORKFLOWS.md` | New row in the workflow table |
| `docs/TESTING.md` | New §23 (evidence and owner checklist); counts updated |
| `README.md`, `project-context.md` | Counts updated; short Prompt 19 section |
| `docs/DATABASE.md` | No substantive change (no schema change) |
