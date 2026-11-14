# Prompt 11: Soft Delete / Deactivate / Draft Discard / Confirm Dialogs

**Project:** MedScope DCMS. **Prompt id:** `11` (follows 10F; all of 10D/10E/10F are reported Done but still uncommitted in the working tree — do not commit, push, stash or reset).
**Prompt file:** `prompt/Prompt_11_Soft_Delete_Discard_Confirm.md`. **Report file:** `report/PROMPT_11_IMPLEMENTATION_REPORT.md`.

You are the coding agent with repository access. This prompt is self-contained. Work carefully and completely; do not shortcut any item. The real repository and the nine docs are the source of truth, not any report or this prompt's guesses about it.

---

## 0. Why this prompt exists

The owner has decided the soft-delete / deactivate scope that was left open since Prompt 10. This prompt implements exactly that scope: nothing else, and nothing is deleted-as-in-destroyed except Draft Invoices.

Current baseline (reported, verify against the repo): Alembic head `f3c9a1d7e5b2` (single head), 122 pytest tests passing (10F), `tsc -b`, oxlint and `vite build` clean, OpenAPI 85 paths / 98 operations, 35 permission keys (20 money). Base git commit `a6c0243`; 10D, 10E and 10F are all uncommitted.

## 1. Read first (mandatory, before any change)

1. The nine docs, the ADL list (up to ADL-051), `report/PROMPT_10F_IMPLEMENTATION_REPORT.md`, and this project's handoff note on Prompt 11 (soft delete scope, the 13 tracked-but-deleted files rule, the 5 stray `medscope_test` LAB_TECH users).
2. The real code for: user management (`user_admin_service.py`, the `/users` API, the existing `set_user_active` deactivate path and its 10F room-demotion wiring — reuse it, do not duplicate it); the doctor and referrer (3rd-party) models/services/endpoints; the test catalog service/endpoints and anywhere a test is looked up for new billing (price list, Assign Tests routing, invoice line creation); the invoice/bill service for Draft-state handling (`Save Draft`, the Drafts filter, `SD-…`/`DRAFT-<hex>` numbering); the permission module `permissions.py`; the existing audit-writing pattern (same-transaction rule, the 10F fix to `revoke_all_user_sessions`); any existing confirm-dialog or modal component in the frontend to reuse rather than duplicate.
3. `git status` and `alembic heads` / `alembic current` so you know the real starting state. Identify the 5 stray `LAB_TECH` test users in `medscope_test` by name so you know exactly what Section 6 below is cleaning up.

Write down in the report what you found for each item before changing it.

## 2. Standing rules (all apply)

- **No browser testing of any kind** (no Playwright runs, Selenium, Cypress, Puppeteer, no opening the app). The owner does browser acceptance. Never claim browser acceptance.
- Allowed checks: `pytest` (only against `medscope_test`, hard guard stays), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`, static analysis, read-only DB inspection.
- Money is whole-taka integers. Financial, audit and event data is append-only. Never print or repeat any password, secret or connection string.
- Every authorization decision goes through the central permission module; backend enforcement is mandatory, UI hiding alone is never enough.
- Audit rows are written in the **same DB transaction** as the action that triggers them.
- Do not restore, delete or move the 13 tracked-but-deleted files in `git status`. Do not edit past reports or the master context file.

## 3. Scope: what gets a soft delete (Category A)

**Soft-deletable, reason required, hidden from normal search, visible + restorable only in an Admin/Owner "Deleted" view:**
- **User / Staff** (this is the delete alongside the existing deactivate — see Section 3a for how the two relate).
- **Doctor**.
- **3rd Party / Referrer**.
- **Catalog Test**.

For each of the four entities above, implement all of the following:

1. **Soft-delete field(s).** Add whatever the model needs to represent "soft-deleted" distinctly from any existing "active/inactive" flag (they are not the same thing — a user can be inactive but not deleted, and this prompt must not collapse the two). Record who deleted it, when, and the reason, append-only (do not overwrite a previous delete's audit trail if the row is later restored and re-deleted — a history list or an audit-log lookup is enough, you do not need a dedicated history table unless the existing pattern already has one for a similar case).
2. **Delete action (API + UI):** requires the relevant manage permission (reuse existing permission keys that already gate editing/deactivating that entity type; do not invent a key if an existing one already fits — state your reasoning in the report either way) plus the global rule "last active OWNER/ADMIN protected" and "no self-delete of your own user account" must still hold for User delete, exactly as they hold today for deactivate. **Reason is mandatory** and must be a non-empty string; reject with a 4xx if missing.
3. **Effect of delete — new selection blocked, nothing else touched (owner's decision 5, reused from 10F):**
   - Deleted **User**: cannot log in (if currently logged in, existing session-revocation pattern applies — reuse the 10F `revoke_all_user_sessions(commit=False)` wiring, same-transaction, and reuse the 10F room-emptying routine so a deleted LAB_TECH empties their room exactly like a deactivated one does). Already-assigned past work, audit rows, and anything they created stays exactly as is.
   - Deleted **Doctor**: no longer selectable as "Tests ordered by", "Patient referred by", or for Doctor-approval attestation on new work. Existing bills, referrals, commission ledger entries, and reports that already reference this doctor are untouched and still display the doctor's name correctly.
   - Deleted **Referrer (3rd party)**: no longer selectable on new bills or rate-card screens. Existing bill referrer links, commission accruals and the party ledger stay exactly as they are and keep showing the referrer's name and history.
   - Deleted **Catalog Test**: no longer appears in test search/selection for new invoice lines, new price-list entries, or new packages. Existing invoice lines, bill line snapshots (price, name, commission base), test orders, samples, results and reports that already reference this test are completely unaffected — they already carry their own snapshot per the existing billing-snapshot rule, so deleting the catalog row must not touch them. Prove this with a test that deletes a test used by an existing invoice line and asserts the old line, its stored price, and its result are unchanged.
4. **"Deleted" view (Admin/Owner only, one per entity type, or one shared UI pattern reused four times — your call, state which):** list of soft-deleted rows with who deleted them, when, and the reason; a **Restore** action that clears the soft-delete fields and makes the row selectable again (restore does not need to re-run the demotion/empties-room cycle, since the row was never reassigned anywhere else automatically — but if your implementation does move it, say so and test it). Restore requires the same manage permission as delete. Restoring a deleted User does not automatically reactivate a session; they simply can log in again if also marked active.
5. **Normal lists exclude soft-deleted rows everywhere** (search, dropdowns, Assign Tests routing, billing test search, price lists, referrer search, doctor selection) — audit this exhaustively; a soft-deleted test or doctor leaking into a new-selection dropdown is the main failure mode to guard against.

### 3a. User delete vs. the existing deactivate — do not merge these

`set_user_active(False)` (deactivate, from Prompt 10D/10E/10F) must keep working exactly as it does today: a reversible, no-reason-required, "switched off for now" state. Soft delete is a separate, reason-required, heavier state layered on top: implement it so that a user can be deactivated without being deleted, but a deleted user is implicitly treated as not usable for login or new selection regardless of their active flag. Do not change the meaning or the API of `set_user_active`. State in the report exactly how the two flags interact (e.g. is a deleted user also forced inactive, or are they independent and you check both at the login/selection gate).

## 4. Scope: Draft Invoice discard (Category B — hard delete, not soft)

**This is different from Section 3: it is a real, permanent delete, no restore, no "Deleted" view.**

1. A **Discard** action on a bill/invoice that is still in **Draft** state only (per the existing Draft/Finalize workflow from 10D). Discarding a Confirmed, Finalized, Cancelled or any non-Draft invoice must be refused with a clear 4xx; write a test for this.
2. **Who can discard:** the staff member who created the draft, or any ADMIN/OWNER. Enforce in the backend, not just the UI.
3. **No reason required.**
4. **Effect:** the draft invoice row (and anything that exists only because the draft exists — e.g. unconfirmed bill lines attached to it, if the schema stores them separately) is permanently removed from the database. Nothing about a Draft invoice should have created test orders, samples, payments, stock movements or commission accruals yet (per the existing Draft/Finalize design — confirm this is still true in the real code before deleting; if you find any side effect already exists for a Draft, stop and report it instead of silently deleting data that something else depends on).
5. **Audit:** write one audit row for the discard (who, when, which invoice's temporary/placeholder identifier, since the row itself will be gone) **before** the delete completes, in the same transaction, so there is a durable record that a draft existed and was discarded even though the draft itself leaves no trace.
6. This also resolves the "drafts accumulate" backlog item and gives the owner a way to clear the currently-stuck ~14 test drafts; do not write a one-off script for that cleanup — the owner will use the new UI/API.

## 5. Confirm Dialog framework (shared UI infrastructure)

1. Build or extend **one reusable confirm-dialog component** used for every destructive or semi-destructive action this prompt adds: soft delete (with a required reason field), restore, and draft discard (no reason field). If the frontend already has a generic modal/dialog primitive, build on it rather than introducing a second one.
2. The dialog must: name the exact item being acted on (not a generic "Are you sure?"), state the action's effect in one short sentence (e.g. "This hides the test from new billing. Existing invoices keep their saved price and are not affected."), require the reason field to be non-empty before the confirm button is enabled when a reason is required, and have a clear Cancel.
3. Wire it into all four soft-delete entities' UI and into the draft discard UI. Do not add a separate bespoke confirmation per screen.

## 6. Cleanup: stray `medscope_test` LAB_TECH users

The 5 leftover `LAB_TECH` test users in `medscope_test` (no room, no staff CHECK) are a known data-hygiene item. Using the new soft-delete you just built (or a straightforward hard delete if these are pure test fixtures with nothing referencing them — check first), remove or properly soft-delete them from `medscope_test` only. Do **not** touch `medscope_dcms` (the owner's dev/QA database) in this step. State in the report which of the two you did and why, and confirm `medscope_test`'s existing hard guard in `conftest.py` was respected throughout.

## 7. Audit Log viewer (small M23 slice — not the full Audit module)

Sections 3, 4 and 6 above make this prompt write new audit rows (soft delete, restore, draft discard, the stray-user cleanup). Those rows are worthless if nobody can see them, so add a minimal, read-only **Audit Log** screen. This is **not** the full Module 23 (no export logging, no report-view logging, no vendor session log, no retention policy work, no redesign of the existing audit table) — it is the smallest viewer that makes this prompt's own audit rows usable.

1. **Permission:** reuse the existing `audit.view`-style permission if one already exists in `permissions.py` (the permission matrix already lists "View audit log" as Owner yes / Admin granted); if no such key exists yet, add exactly one (`audit.view`), default ON for OWNER, grantable to ADMIN (matching the existing matrix), OFF for everyone else including a deleted/restored user's own actions. Never grant it to LAB_TECH, DOCTOR, RECEPTIONIST or CASHIER.
2. **Endpoint:** one read-only, paginated `GET` endpoint over the existing audit table, filterable at minimum by action type, entity type, actor, and date range. Reuse the existing audit table and its existing columns (who, acting role, when, action, before, after) exactly as the current schema defines them — do not add new audit columns here beyond what Sections 3/4/6 already require for the delete/discard/restore actions themselves.
3. **UI:** one simple list screen (table: when, who, acting role, action, entity, reason if present, a way to see the before/after detail for one row) reachable from the Owner/Admin navigation. No edit, no delete, no export in this prompt — view only.
4. **Scope of rows shown:** all existing audit rows already in the table (so the screen is useful immediately, not just for new 10F/11 rows going forward), newest first.
5. Document this as a deliberately small slice of Module 23 in `docs/SCOPE.md` and the ADL, and list what M23 still needs later (export logging, report-view logging, vendor session log, retention/legal-hold policy, any audit coverage gaps outside this prompt's own actions) so it is not mistaken for the finished module.

## 8. Schema and DDL discipline (expected to apply here — this prompt almost certainly needs one)

This prompt is very likely to require new nullable columns (soft-delete flag, deleted_by, deleted_at, delete_reason) on at least `users`, `doctors`/referrers' table(s), and the test catalog table. The Audit Log viewer in Section 7 reuses the existing audit table and needs no new columns of its own unless you find the existing table cannot support the filters required — if so, treat that as part of this same migration and explain why. Treat all of this as expected, not exceptional:

1. Create an Alembic migration with a correct `down_revision` (current head `f3c9a1d7e5b2`), review every autogenerated operation by hand, and end with a **single head**.
2. All new columns must be nullable or safely defaulted; never wipe or reset existing data. Take a fresh `pg_dump` into the git-ignored `backups/` folder before applying anything to `medscope_dcms`. Never print or repeat the connection string.
3. Run `alembic heads`, then `alembic upgrade head` against the dev DB, then `alembic check` (must come back clean). Report the exact head hash before and after.
4. If, after reviewing the real schema, you determine no schema change is needed (e.g. a generic status/flag column already exists and can be extended safely), you must still prove it with `alembic heads` and `alembic check`, and explain exactly why no migration was needed — do not assume this is likely going in, confirm it against the real code.
5. Update `docs/DATABASE.md` with the new columns, their meaning, any new indexes needed for the "exclude soft-deleted" queries, and the full migration chain. Update the ADL (continue numbering from ADL-051) explaining the soft-delete design, why deactivate and delete are kept separate, why Draft discard is a hard delete while everything else is soft, and the Audit Log viewer's scope (Section 7).

## 9. Documentation (mandatory, with this prompt)

Update **all nine docs**. If a doc has no substantive change, verify that and record "reviewed, no change" in the report; do not invent content.

- `docs/ARCHITECTURE.md`: new ADL(s) per Section 8.5; the confirm-dialog pattern as a shared frontend convention; the Audit Log viewer's deliberately small scope and what M23 still owes later.
- `docs/SCOPE.md`: the finalized Category A / B / C decision table (soft-delete entities, hard-delete draft discard, never-deletable list), the "new selection blocked only" rule, reason-required vs not; the Audit Log viewer noted as a slice of M23 with the remaining M23 gaps listed explicitly.
- `docs/API.md`: every new/changed endpoint (delete, restore, discard, the Deleted-view list endpoints, the audit log list endpoint), their permissions, payloads, and error codes, with real counts (update the 85/98 baseline to the real new numbers).
- `docs/WORKFLOWS.md`: the delete→hidden→restore flow for each of the four soft-delete entities; the draft discard flow; where the confirm dialog appears in each; how to reach and filter the Audit Log screen.
- `docs/DESIGN.md`: the confirm dialog component, the Deleted-view screens, the Audit Log screen, any new empty/error states.
- `docs/DATABASE.md`: per Section 8.
- `docs/TESTING.md`: new non-browser evidence; a new **owner manual-acceptance checklist for Prompt 11** (one click path + one expected result each, covering: delete and restore for each of the four entity types including the "doesn't affect existing records" check; a self-delete and a last-active-OWNER/ADMIN delete attempt both being refused; a non-Draft discard attempt being refused; a creator discarding their own draft; an ADMIN discarding someone else's draft; the stray-user cleanup confirmation; opening the Audit Log and finding the rows for all of the above); keep the pre-go-live list (Section 12) and the known-not-done list intact.
- `README.md` and `project-context.md`: current phase = Prompt 11 done (reported), next step = owner acceptance; updated counts and head.
- **Docs rule from the owner:** flip any line in the docs that currently records this scope as "decided, not yet implemented" (the Prompt 11 categories, the stray-user cleanup) to implemented now that it is built.

## 10. Tests and validation (real results only)

Add backend tests for at least:
- Each of the 4 soft-delete entities: delete requires reason (400 without one); delete requires the correct permission (403 otherwise); delete hides the row from every normal list/search/dropdown you touched; existing records that reference the deleted row are completely unaffected (write at least one concrete test per entity proving an old invoice line / old bill / old commission entry / old assignment keeps working and displaying correctly after the referenced row is deleted); restore works and requires the same permission; a non-Admin/Owner cannot see the Deleted view.
- User delete specifically: self-delete refused; deleting the last active OWNER or ADMIN refused; deleting an active LAB_TECH triggers the same room-emptying routine as deactivate (reuse the 10F test pattern); a deleted user cannot log in even if still flagged active (or confirm your chosen interaction from Section 3a with a test either way).
- Draft discard: refused on non-Draft invoices (409 or 400); creator can discard their own draft; ADMIN/OWNER can discard anyone's draft; a different non-privileged staff member cannot discard someone else's draft; the audit row survives after the draft row is gone; no orphaned child rows remain (bill lines, if stored separately, are also gone — write a test asserting the row count).
- Confirm dialog: this is frontend-only; if the project has frontend unit tests, add minimal ones for the reason-required gating logic; otherwise note that this was verified by code review only (non-browser) and say so plainly.
- Audit Log viewer: `audit.view` permission enforced (403 for every role not entitled to it, per Section 7.1); each delete/restore/discard action from this prompt produces a row that the endpoint returns; filters (action type, entity type, actor, date range) narrow results correctly; no write/delete/export operation exists on this endpoint.

Run and report the actual results: `pytest` (against `medscope_test` only), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`. Do not run Playwright; state plainly that the owner does browser acceptance for this prompt (the new checklist in `docs/TESTING.md`).

## 11. Report: `report/PROMPT_11_IMPLEMENTATION_REPORT.md`

Sections: Done / Partial / Blocked / Deferred (real results only). Include: an **Assumptions table** for the owner to confirm or reverse (at minimum: which existing permission keys were reused per entity vs. any new key added and why; exactly how deleted-vs-inactive interact for User; whether restore re-triggers any room/assignment side effect; whether the Deleted view is one shared component or four separate ones); files changed; migration/head before and after (or the proof that none was needed); API and permission changes with real counts; docs updated per file; validation command results with real numbers; anything doubtful you noticed but did not fix.

## 12. Must NOT do

- No browser testing, no Playwright run, no app opened in a browser.
- Do not add delete or deactivate capability to Patient, Confirmed/Finalized Invoice, Payment, Refund, Result, Sample, Audit row, Business day, Ledger entry, or Stock movement. These stay permanently non-deletable and non-deactivatable; do not even add a disabled button for them.
- Do not give Draft Invoice discard a restore path, a reason field, or a soft-delete flag — it is a real delete, full stop.
- Do not build the full Module 23 (Audit): no export logging, no report-view logging, no vendor session log, no retention/legal-hold policy, no redesign of the audit table, no coverage audit of actions outside this prompt's own delete/restore/discard/cleanup actions. Section 7's viewer is read-only and scoped to what already exists in the audit table plus what this prompt adds.
- Do not touch `performing_role` normalization, the 671 unmapped-room tests, the urgent-fee floor/cap rule, the master-discount behaviour (A3), the doctor sign-off screen, or the reduced-motion control. These remain open owner decisions from earlier prompts.
- Do not start Module 14, 15, or 16, or any other module work. This prompt is infrastructure only (delete/discard/restore/confirm-dialog/audit-viewer) layered on M1, M4, M5 and M6.
- Do not modify `medscope_dcms` test/catalog/user data beyond what the owner's own use of the new delete/restore features would do; do not pre-emptively soft-delete anything in the dev DB yourself.
- Do not create, change, or print any password, secret, or connection string.
- Do not commit, push, stash, or reset. Do not restore, delete, or move the 13 tracked-but-deleted files. Do not edit past reports or the master context file.
- Do not start the next prompt or module.

*End of Prompt 11.*
