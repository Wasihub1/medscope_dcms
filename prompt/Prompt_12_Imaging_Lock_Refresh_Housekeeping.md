# Prompt 12: Invoice Auto-Refresh + Imaging Lock Simplification + Test-Infra Housekeeping

**Project:** MedScope DCMS. **Prompt id:** `12` (follows Prompt 11; 10D/10E/10F/11 are all reported Done but still uncommitted — do not commit, push, stash or reset).
**Prompt file:** `prompt/Prompt_12_Imaging_Lock_Refresh_Housekeeping.md`. **Report file:** `report/PROMPT_12_IMPLEMENTATION_REPORT.md`.

You are the coding agent with repository access. This prompt is self-contained. Work carefully and completely; do not shortcut any item. The real repository and the nine docs are the source of truth, not any report or this prompt's guesses about it.

---

## 0. Why this prompt exists

Three small fixes the owner decided during browser acceptance of 10D–11, plus test-infrastructure housekeeping the owner asked for after Prompt 11's cleanup turned up far more stray data than expected. Nothing else.

Current baseline (reported, verify against the repo): Alembic head `a4d8c2e6f1b7` (single head), 135 pytest tests passing (122 pre-Prompt-11 + 13 new), `tsc -b`, oxlint and `vite build` clean, OpenAPI 96 paths / 110 operations, permission keys at 38 (money keys 21, including `audit.view`). Base git commit `a6c0243`; 10D, 10E, 10F and 11 are all uncommitted.

## 1. Read first (mandatory, before any change)

1. The nine docs, the ADL list (up to ADL-055), `report/PROMPT_11_IMPLEMENTATION_REPORT.md`.
2. The real code for: the Invoice View page and whatever currently requires a manual reload to show updated sample status after Sample Taken (query client setup — React Query or equivalent — cache invalidation, focus-refetch config, polling); the imaging lifecycle code (`IMAGING_PERFORMED` status, wherever the lock event and stock deduction currently fire for imaging test orders, the Prompt 06/07 imaging extension, D13/D14 as implemented, the cancel/refund path for imaging lines); `conftest.py` and every test fixture/factory that creates a `Staff`/`User` row (search for patterns that generate a random suffix, e.g. an 8-hex-character username, and for any fixture-level user/referrer factory) to find every place that creates rows without a teardown; `docs/API.md` and `docs/SCOPE.md`'s current text on the `audit.view` permission and its default.
3. `git status` and `alembic heads` / `alembic current` so you know the real starting state. Connect to `medscope_test` and get an actual count of stray fixture-created `Staff` rows by role (do not assume the 98/receptionist numbers from the Prompt 11 report are still current; recount).

Write down in the report what you found for each item before changing it.

## 2. Standing rules (all apply)

- **No browser testing of any kind** (no Playwright runs, Selenium, Cypress, Puppeteer, no opening the app). The owner does browser acceptance. Never claim browser acceptance.
- Allowed checks: `pytest` (only against `medscope_test`, hard guard stays), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`, static analysis, read-only DB inspection.
- Money is whole-taka integers. Financial, audit and event data is append-only. Never print or repeat any password, secret or connection string.
- Every authorization decision goes through the central permission module; backend enforcement is mandatory, UI hiding alone is never enough.
- Audit rows are written in the **same DB transaction** as the action that triggers them.
- Do not restore, delete or move the 13 tracked-but-deleted files in `git status`. Do not edit past reports or the master context file.

## 3. Scope item 1: Invoice view auto-refresh after Sample Taken

1. **Diagnose first.** Confirm in the real code whether the Invoice View's sample-status field is simply not refetched after the Sample Taken mutation succeeds elsewhere (worklist/technician screens), or whether the backend response itself is stale. State the real cause in the report.
2. **Fix:** when a Sample Taken action succeeds anywhere in the app, the Invoice View (if open, or the next time it is opened/focused) must show the updated sample status (COLLECTED / REJECTED / SPOILED / PERFORMED / AWAITING COLLECTION, per the existing mapping from Prompt 07 Fix 3) without a manual page reload. Use the project's existing data-fetching pattern: cache invalidation on the mutation that performs Sample Taken is preferred over polling; if a light poll is added as a fallback, keep the interval long enough not to add real load (state the interval and why).
3. Do not change the sample-status mapping itself, the lock event, or anything about who can take a sample. This is a refresh-timing fix only.
4. Add a test (unit/integration, non-browser) proving the invoice query is invalidated or refetched when the Sample Taken mutation succeeds. If the project has no frontend test runner, verify by code review and state that plainly.

## 4. Scope item 2: Imaging lock simplified to result completion (owner decision, replaces the IMAGING_PERFORMED lock step)

**Owner's decision:** remove the separate `IMAGING_PERFORMED` lock step. An imaging test order locks (and stock deducts, if and when stock deduction is actually wired for imaging — check the real code; Section 7 of the Prompt 11 report and earlier reports say stock is boundary-only, so this may be a no-op for stock today, which is fine) at the **same lock event every other no-sample test already uses: result completion**, per D13 exactly as it already applies to X-ray/ultrasound-type tests elsewhere in the codebase. This removes the previously-planned separate "imaging started but not completed → admin/owner approval + wastage" exception, because there is no longer an earlier lock point to roll back from — an imaging line that has not yet had its result completed is simply an unlocked line, cancelled through the ordinary pre-lock cancel path (no special approval needed beyond whatever the ordinary unlocked-line cancel already requires).

1. Find every place `IMAGING_PERFORMED` currently triggers lock behavior (test-line lock flag, stock deduction trigger, cancel/refund eligibility, any UI badge such as "Line Locked" from Prompt 07 Fix 1, worklist status transitions) and change the lock trigger to the existing result-completion event used by other no-sample tests. Reuse the existing `requires_sample()`/lock logic from 10F rather than writing a second lock mechanism; imaging tests already return "no sample needed" from that helper, so they should already follow the same no-sample lock path as X-ray-type entries — if they do not currently, this is the actual bug to fix.
2. `IMAGING_PERFORMED` may remain as a **status label** in the imaging workflow (Performed, Awaiting doctor, per the existing department extensions in D19) if the UI/workflow still needs to show that imaging has physically happened before a result is entered — but it must no longer be the lock trigger. State clearly in the report whether you kept `IMAGING_PERFORMED` as a non-locking intermediate status or removed it outright, and why.
3. **Owner same-day unlock (D14) stays, unchanged in its own right, and now applies uniformly:** once any test line (imaging included) is locked at result completion, the existing owner-only, reason-required, same-business-day unlock exception applies exactly as it already does for other test types. Do not build a second, imaging-specific unlock path; confirm the existing one already covers imaging lines once they share the same lock event, and fix it if it does not.
4. Cancelling an imaging line **before** result completion now goes through the ordinary pre-lock cancel/refund path (admin/owner approval per the existing unlocked-line rule), with no separate wastage-logging requirement specific to "started but not completed" — remove any code that still branches on that now-removed intermediate state, if it exists.
5. This is a real behavior change, not a pure bug fix: write a migration-adjacent note (even if no schema changes) in the ADL explaining the old vs new imaging lock trigger, and update every doc section that described the old `IMAGING_PERFORMED`-triggers-lock behavior or the "imaging started, not completed" approval exception (this includes the matrix cells and conflict notes in the master-context-derived docs if the nine docs repeat them — update the nine docs, never the master context file itself).
6. Add tests: an imaging order's line is NOT locked at `IMAGING_PERFORMED` (if that status still exists) and IS locked once its result is completed; cancel before result completion follows the ordinary unlocked-line path; the owner same-day unlock works on a locked imaging line exactly as on a locked non-imaging line.

## 5. Scope item 3: deferred — barcode direct open (M11.4)

**Do nothing for this item.** The owner has deferred barcode scan-to-task-open to the product-finishing phase. Do not implement, stub, or partially wire it. Record in `docs/TESTING.md`'s known-not-done list (keep the existing wording if it is already there; if not, add it) that M11.4 remains deferred by explicit owner decision, not forgotten.

## 6. Scope item 4: stray test-fixture user cleanup (one-time, `medscope_test` only)

1. Connect only to `medscope_test` (assert the database name before doing anything, exactly as the Prompt 11 cleanup script did) and get the real current count of fixture-created `Staff`/`User` rows by role (the Prompt 11 report's 98 LAB_TECH / ~170 receptionist figures are from that point in time; recount now, since more pytest runs have happened since).
2. **Hard-delete** (not soft-delete — these are disposable test fixtures with no audit/business meaning, unlike Prompt 11's soft-delete feature which is for real data) every such fixture row that is not one of the project's named seed accounts (`reception_fatima`, `cashier_fatima`, `admin_tariq`, `owner_tariq`, `tech_kamal`, `tech_nasrin`, `tech_micro`, `tech_usg`, and any other account you confirm is an intentional named seed rather than an auto-generated fixture). Identify fixture rows by the pattern the Prompt 11 report used (random-suffix usernames) and by cross-checking against the actual fixture/factory code found in Section 1 above — do not delete by guesswork.
3. Because these are hard deletes of `Staff` rows, check for and clean up anything that would otherwise leave an orphaned foreign key or constraint violation in `medscope_test` specifically (e.g. audit rows referencing the deleted user, sessions) — in `medscope_test` this is acceptable to hard-delete or cascade, since it is disposable test data, but confirm your deletes do not crash the test suite afterward.
4. Do **not** connect to, inspect, or modify `medscope_dcms` in this step. State explicitly in the report that you verified this.
5. This is a one-time cleanup; the real fix is Section 7.

## 7. Scope item 5: stop the regrowth — fixture teardown (root cause fix)

1. Find every pytest fixture or test-helper factory function that creates a `Staff`/`User` (or other) row without deleting it afterward (the random-suffix username pattern is the signal).
2. Change these fixtures to clean up after themselves using the project's existing test-isolation pattern. Prefer whichever of these the codebase already uses or most naturally supports, and state which you chose and why:
   - a `yield`-based fixture that deletes the row(s) it created in its teardown, or
   - wrapping the test in a transaction that is rolled back at the end (if `conftest.py` already supports a per-test transaction/session pattern, extending it is preferred over adding deletes to every fixture individually), or
   - a session-scoped cleanup fixture that deletes everything created during the test session by a recognizable marker (e.g. a fixed test-run prefix on generated usernames) at the end of the run.
3. Whichever mechanism you choose, it must only ever operate on `medscope_test` — keep the existing hard guard in `conftest.py` intact and do not weaken it.
4. Prove the fix works by running the full suite **twice in a row** and showing the fixture-created row count in `medscope_test` is the same after both runs (not growing). Report the exact before/after counts for both runs.
5. Do not change what the fixtures test or assert — only how they clean up.

## 8. Scope item 6: `audit.view` permission documentation fix (docs only, no code change)

**This is not a bug.** Prompt 11's Assumption A1 was implemented correctly and the owner confirmed it in browser testing: `audit.view` defaults to OWNER only; ADMIN does not have it by default but OWNER can grant it to ADMIN, matching the B11 permission matrix's "Granted" convention for similar keys (e.g. "Pay commission / hand over visit fee"). The problem is purely that the documentation does not say this clearly, so it was briefly mistaken for a bug.

1. Update `docs/API.md` and `docs/SCOPE.md` wherever `audit.view` (or the Audit Log viewer added in Prompt 11) is described: state explicitly that the default is OWNER = yes, ADMIN = no (grantable), everyone else = no, and that this matches the existing permission-matrix convention for owner-controlled, grantable keys.
2. Update `docs/TESTING.md`'s Prompt 11 owner-acceptance checklist entry for the Audit Log so it reads as an explicit PASS condition ("Admin does not see Audit Log by default — this is correct; Owner can grant it") rather than leaving room to read a missing menu item as a defect.
3. No permission default, no code, and no test behavior changes in this section — docs only. If you find the code and the docs already agree once you re-read them carefully and the issue is purely that no one wrote this down anywhere obviously, say so plainly in the report.

## 9. Schema and DDL discipline

No schema change is expected for any of the six items above (the imaging lock change is a logic/trigger change, not a column change, unless you find the existing schema cannot represent "locked at result completion" for imaging without a new column or enum value).

1. If you determine a schema change is genuinely required (e.g. an enum value for test-order status needs to change, or a boolean lock flag needs to move), create an Alembic migration with a correct `down_revision` (current head `a4d8c2e6f1b7`), review every autogenerated operation by hand, and end with a **single head**. All new/changed columns must be nullable or safely defaulted; never wipe or reset existing data. Take a fresh `pg_dump` into the git-ignored `backups/` folder before applying anything to `medscope_dcms`. Never print or repeat the connection string.
2. Run `alembic heads`, then `alembic upgrade head` against the dev DB, then `alembic check` (must come back clean). Report the exact head hash before and after.
3. If no schema change is needed, prove it with `alembic heads` and `alembic check` and state plainly why none was needed.
4. Update `docs/DATABASE.md` either way (new migration details, or "reviewed, no change" with proof) and add an ADL entry (continue numbering from ADL-055) explaining the imaging-lock-trigger change regardless of whether it required a schema change, since it is a behavior change worth recording on its own.

## 10. Documentation (mandatory, with this prompt — do not treat this as optional or light-touch)

Update **all nine docs**. If a doc has no substantive change, verify that and record "reviewed, no change" in the report; do not invent content. Documentation is not a formality here — Section 8 exists specifically because a documentation gap was mistaken for a bug, so be thorough.

- `docs/ARCHITECTURE.md`: new ADL(s) for the imaging lock change (old vs new trigger, why `IMAGING_PERFORMED` is or isn't still a status, how it relates to the existing D13/D14/10F `requires_sample()` logic) and for the test-fixture cleanup mechanism chosen in Section 7.
- `docs/SCOPE.md`: the imaging lock rule corrected to lock at result completion (remove or clearly supersede any text describing the old `IMAGING_PERFORMED`-triggers-lock behavior and the now-removed "imaging started, not completed" approval exception); the `audit.view` default stated explicitly per Section 8; note that M11.4 barcode direct-open is deferred to product-finishing by explicit owner decision (not an oversight).
- `docs/API.md`: any changed endpoint behavior around imaging lock/cancel; the `audit.view` default per Section 8; updated endpoint/permission counts if anything changed (if nothing changed, say so with the same 96/110 and 38 numbers).
- `docs/WORKFLOWS.md`: the corrected imaging workflow (Performed as a status if kept, lock at result completion, ordinary pre-lock cancel for an imaging line not yet completed, owner same-day unlock applying uniformly); the invoice auto-refresh behavior.
- `docs/DESIGN.md`: update if any UI badge/label tied to the old imaging lock point changes (e.g. a "Line Locked" badge timing).
- `docs/DATABASE.md`: per Section 9.
- `docs/TESTING.md`: new non-browser evidence; the Section 7 before/after fixture-count proof; the Section 8 checklist correction; the M11.4-deferred note; a short owner-acceptance checklist for Prompt 12 (one click path + one expected result each, covering: Sample Taken then returning to or refreshing Invoice View without a manual reload; an imaging test's line is NOT shown as locked before its result is completed; cancelling that imaging line before result completion follows the ordinary cancel flow; completing the imaging result locks the line; owner same-day unlock works on a locked imaging line; Admin still correctly does not see Audit Log unless granted, confirmed as expected).
- `README.md` and `project-context.md`: current phase = Prompt 12 done (reported), next step = owner acceptance; updated head and any changed counts.
- **Docs rule from the owner:** flip any line that still describes the old `IMAGING_PERFORMED`-triggers-lock behavior, the removed imaging approval exception, or M11.4 as "pending" without noting it is a deliberate deferral, so the docs match the real, current behavior exactly.

## 11. Tests and validation (real results only)

Add backend tests for at least:
- Invoice auto-refresh: per Section 3.4.
- Imaging lock: per Section 4.6.
- Fixture cleanup: per Section 7.4 (the double-run count proof is itself the test evidence, report it explicitly, do not just say "verified").
- Regression: run the full existing suite and confirm the Prompt 04–11 tests still pass unchanged in behavior (only possibly fewer/cleaner stray rows, never a logic regression).

Run and report the actual results: `pytest` (against `medscope_test` only, run twice per Section 7), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`. Do not run Playwright; state plainly that the owner does browser acceptance for this prompt.

## 12. Report: `report/PROMPT_12_IMPLEMENTATION_REPORT.md`

Sections: Done / Partial / Blocked / Deferred (real results only; M11.4 belongs under Deferred with the owner's reason, not under Blocked). Include: a **Root cause** subsection for the invoice-refresh fix; a clear **before/after** description of the imaging lock trigger; the exact stray-fixture counts before cleanup, after cleanup, and after each of the two regression pytest runs; an **Assumptions table** (at minimum: whether `IMAGING_PERFORMED` was kept as a non-locking status or removed; which fixture-cleanup mechanism was chosen and why; whether any imaging-specific code path needed removal for the now-gone approval exception); files changed; migration/head before and after (or proof none was needed); docs updated per file; validation command results with real numbers; anything doubtful noticed but not fixed.

## 13. Must NOT do

- No browser testing, no Playwright run, no app opened in a browser.
- Do not implement any part of barcode direct-open (M11.4) — not a stub, not partial wiring. It is deferred, full stop.
- Do not change the `audit.view` permission default or any other permission default — Section 8 is documentation-only.
- Do not touch `performing_role` normalization, the 671 unmapped-room tests, the urgent-fee floor/cap rule, the master-discount behaviour (A3), the doctor sign-off screen, or the reduced-motion control. These remain open owner decisions from earlier prompts.
- Do not start Module 14, 15, or 16, or any other module work.
- Do not soft-delete the stray test fixtures (Section 6 is a hard delete, by design, because these are disposable test rows, not real data) and do not apply the Section 6/7 cleanup logic to `medscope_dcms` under any circumstance.
- Do not weaken, remove, or bypass the existing `medscope_test`-only hard guard in `conftest.py`.
- Do not create, change, or print any password, secret, or connection string.
- Do not commit, push, stash, or reset. Do not restore, delete, or move the 13 tracked-but-deleted files. Do not edit past reports or the master context file.
- Do not start the next prompt or module.

*End of Prompt 12.*
