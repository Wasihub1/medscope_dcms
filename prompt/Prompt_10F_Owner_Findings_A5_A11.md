# Prompt 10F: Owner Browser Findings (#1, #2, #3) + A5 Sample Rule + A11 Empty Room

**Project:** MedScope DCMS. **Prompt id:** `10F` (follows 10E; Prompt 11 = soft delete is reserved and must NOT be started).
**Prompt file:** `prompt/Prompt_10F_Owner_Findings_A5_A11.md`. **Report file:** `report/PROMPT_10F_IMPLEMENTATION_REPORT.md`.

You are the coding agent with repository access. This prompt is self-contained. Work carefully and completely; do not shortcut any item. The code in the real repository is the source of truth, not any report or this prompt's guesses about it.

---

## 0. Why this prompt exists

The owner started browser testing of Prompts 10D/10E and found three problems. He also made two decisions about known risks. This prompt implements exactly those five items, plus the documentation and schema discipline that goes with every change. Nothing else.

Current baseline (reported, verify against the repo): Alembic head `f3c9a1d7e5b2` (single head), 110 pytest tests passing, `tsc -b`, oxlint (0 errors, 120 warnings baseline) and `vite build` clean. Base git commit `a6c0243`; the 10D and 10E work is **uncommitted**, so `git status` is large. Do not commit, push, stash or reset anything.

## 1. Read first (mandatory, before any change)

1. The nine docs: `README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`, plus the ADL list (up to ADL-047) and `report/PROMPT_10E_IMPLEMENTATION_REPORT.md`.
2. The real code for: `backend/app/core/permissions.py`; the worklist/test-order service and router (room routing, `reassign`, release of unassigned orders, `requires_sample()`, summary counts); result entry and result templates; the invoice/sample status code; the `/reports` endpoint and its frontend page; the sidebar and route definitions; the Assign Tests page; the Lab "My Work" page (grid, Bento tiles, Ready Reports tab, Preview Report); user management (deactivate, change room, change role).
3. `git status` and `alembic heads` / `alembic current` so you know the real starting state.

Write down (in the report) what you found before changing anything for each item below.

## 2. Standing rules (all apply)

- **No browser testing of any kind** (no Playwright runs, Selenium, Cypress, Puppeteer, no opening the app). The owner does browser acceptance. Never claim browser acceptance.
- Allowed checks: `pytest` (only against `medscope_test`, hard guard stays), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`, static analysis, read-only DB inspection.
- Money is whole-taka integers. Financial, audit and event data is append-only. Technicians and doctors never see money. Never print or repeat any password, secret or connection string.
- Every authorization decision goes through the central permission module. Backend enforcement is mandatory; UI hiding alone is never enough.
- Audit rows are written in the **same DB transaction** as the action (the 10E lost-audit-row bug must not recur).
- Do not restore, delete or move the 13 tracked-but-deleted files in `git status`. Do not edit past reports or the master context file.

## 3. Scope: the five items

### F1. Assigned Tests view (owner finding #1)

**Owner's words:** the assigned-test UI is missing. Receptionist = view only. Admin/Owner = can reassign to a different room. The reassign option must remain available until the test is COMPLETED.

**Do:**
1. Find where this view belongs by inspecting the sidebar "Assign Tests" page and the `/worklist` page for non-technician roles. Reuse and repair the existing page if it is the natural home; do not create a duplicate page. Record your decision and reason in the report.
2. Deliver one **Assigned Tests** list that shows every test order with: invoice number, patient name, test name, room (lab section), the active technician name(s) of that room or the explicit state UNASSIGNED, status, urgent flag, and created time. Filters by room and status, plus search. **No money fields anywhere in this view or its API payload.**
3. Role behaviour:
   - RECEPTIONIST: view only. No reassign control rendered, and the backend refuses a reassign call (verify, with a test).
   - ADMIN and OWNER (and any user who holds `worklist.reassign` through the permission layer): a **Reassign Room** action on each row that is not COMPLETED, not cancelled, not NOT_PERFORMED. The user picks a different room from the list of existing rooms. Reuse the existing 10E reassign endpoint and its rules (reason, append-only assignment history, audit row); do not write a second reassign path.
   - The control is hidden or disabled with a short reason once the order is COMPLETED. The backend must reject reassign for COMPLETED orders with a clear 4xx (verify; add a test if missing).
   - LAB_TECH and DOCTOR do not get this view (money-free dashboard rules stay).
4. If a new view permission key is needed, add it to `permissions.py` with sensible role defaults (RECEPTIONIST, ADMIN, OWNER), keep the "money keys never reach LAB_TECH/DOCTOR" safety rule, and document it in `docs/API.md` and the permission table (count rises from 35). If an existing key already fits, reuse it and say so.
5. After a reassign the list and the receiving room's worklist must reflect the change without a manual page reload (query invalidation/refetch).

### F2. Preview Report appears after saving a result (owner finding #2)

**Owner's words:** in My Work (Lab), after entering a report and saving, there is no Report Preview option in the grid.

**Do:**
1. Find the root cause first (is the grid not refetched after save? is the preview action gated on a status that the save does not reach, for example COMPLETED or result `ENTERED` only?). Put the confirmed cause in the report.
2. Fix it so that **any order with a saved result (DRAFT or ENTERED)** shows the Preview Report action in the grid immediately after save, with no manual reload.
3. A preview of a DRAFT result must be visibly marked as a draft (for example a "DRAFT, not a final report" banner). Preview uses the stored result snapshots (component name, unit, reference range, critical limits as saved). It is read-only and money-free.
4. This is a preview only. No print button, no finalize, no signature, no QR, no SMS, no `report_versions` row. That is Module 14 and is out of scope.

### F3. Ready Reports must actually fill (owner finding #3)

**Owner's words:** the "Ready Reports" tag in the Work queue is interactive but clicking it does not show the ready reports. Separately, the sidebar has a "Ready Reports" option for Receptionist/Admin/Owner, and newly ready reports do not appear there.

**Do, in this order:**
1. **Diagnose both with the real code and the real data.** Likely causes to check (confirm or reject each, do not assume): the 10E definition of Ready is "order COMPLETED and result ENTERED", but saving a result only moves the order to IN_PROGRESS/AWAITING_DOCTOR and "Complete" is a separate technician action, so a freshly saved result never matches; the Ready tile count and the Ready list may use different filters; the sidebar `/reports` list reads only `report_versions`, which nothing creates yet (Module 14 is not built), so it is always empty.
2. **Definition to implement (owner expectation, recorded as an assumption in the report):** a result is **Ready** when its status is `ENTERED` (submitted, not merely DRAFT) and the order is not cancelled, not NOT_PERFORMED, not rejected/spoiled and not AWAITING_DOCTOR. Completing the order operationally is **not** required for Ready. Use one single shared backend definition (one function or query) for the Lab tile count, the Lab Ready tab list and the sidebar list so they can never disagree.
3. **Lab "Ready Reports" tile/tab:** clicking it filters the grid to exactly the Ready orders of that technician's room; the tile count equals the number of rows; clicking again clears the filter; Preview Report is available on each row.
4. **Sidebar Ready Reports (`/reports`) for RECEPTIONIST, ADMIN, OWNER (use the existing permission):** list every Ready order (all rooms) with patient, invoice number, test, room, result-entered time, and a payment-due indicator (the due indicator may only be returned to roles that are allowed to see money, via the existing money-permission check), with a Preview Report action. Newly saved results must appear after a refetch (on navigation and on window focus at minimum). Search and a room filter are welcome but keep the change small.
5. Do **not** create `report_versions` rows and do not implement finalize, release, handover logging, signatures, QR or SMS. Write the query so Module 14 can later exclude orders that already have a Final report version; add a short code comment saying so.
6. Update the empty-state text on `/reports` so it is accurate (no more "nothing is issued" when ready results exist).

### F4. A5 sample rule (owner decision: he will fill catalog `sample_type` himself later)

**Problem:** 1,224 catalog tests have no `sample_type`, and 10E treats NULL/"None"/"N/A" as "no sample needed". Result: a CBC can get a result and be completed without Sample Taken, so the line never locks and future stock deduction would never trigger.

**Do:**
1. Replace the rule in the single `requires_sample()` helper (and delete any duplicated copies so there is exactly one source of truth):
   - Imaging tests never need a sample. Define "imaging" in exactly one place, using what the repo already has (the imaging lifecycle type, department and lab section such as Ultrasonography and X-ray). Report the exact definition you used.
   - An **explicit** no-sample marker (`None`, `N/A`, `NA`, `No sample`, case-insensitive, trimmed) means no sample needed.
   - **NULL or empty `sample_type` on a non-imaging test means unknown and therefore a sample IS required.**
2. Enforce it at every gate, backend first: saving a result (draft and submit), operational Complete, line lock, invoice sample-status mapping, worklist actions. If the repo had fewer gates than that, add the missing ones and list them in the report. The rejection must be a clear 4xx with a plain message; the UI must show that message (for example "Take the sample before entering results").
3. **Do not change any catalog data.** Do not backfill, guess or seed `sample_type`. The owner will complete it in the database. Do not alter existing orders, results or locks.
4. Document in `docs/TESTING.md` a "data readiness" note: until the owner fills `sample_type`, non-imaging tests with NULL require a sample, which is the safe direction.

### F5. A11 empty room demotes assigned orders to UNASSIGNED (owner decision: "Unassigned thakbe")

**Rule:** when a room loses its last active technician, the room's orders that are only assigned (not yet worked on) become **UNASSIGNED** and stay visible to Admin/Owner.

**Do:**
1. Find every path that can empty a room: deactivating a technician, changing a technician's room, changing a technician's role away from LAB_TECH, and any other path you find. Apply the rule in all of them through one shared function, in the same transaction as the user change.
2. Inspect whether the order `status` field mixes assignment state with progress state. Demote only orders that are in the assigned-only state (ASSIGNED). Do **not** wipe progress: orders already collected, in progress, with a saved result, completed, cancelled or not performed keep their state. List in the report exactly which states were demoted and which were left, and why.
3. Write an audit row per demoted order (for example `ORDER_UNASSIGNED_ROOM_EMPTY`) plus the existing user-action audit, in the same transaction. If assignment history is append-only in the repo, add a history entry too.
4. Verify the existing "add a technician to a room releases its UNASSIGNED orders" path still works and does not re-release anything it should not. Add tests for the full cycle: room with one technician, deactivate, orders become UNASSIGNED, Admin sees them, add a technician, orders are released.

## 4. Schema and DDL discipline (applies if any item needs a schema change)

No schema change is expected. If you find one is genuinely required, you must:
1. Create an Alembic migration with a correct `down_revision` (current head `f3c9a1d7e5b2`), review every autogenerated operation, and keep a **single head**.
2. Never wipe or reset data. Take a fresh `pg_dump` into the git-ignored `backups/` folder before applying anything to `medscope_dcms`. Do not print connection strings.
3. Make the migration reversible where practical and safe on existing rows (nullable or defaulted columns, backfill inside the migration if needed).
4. Run `alembic heads`, `alembic upgrade head` on the dev DB, then `alembic check` (must be clean).
5. Update `docs/DATABASE.md` (tables, columns, constraints, indexes, migration chain, DDL summary) and the ADL.
6. If no schema change is needed, state that explicitly in the report, prove it with `alembic heads` and `alembic check`, and record in `docs/DATABASE.md` that 10F was reviewed with no schema change.

Permission keys, role defaults and the sample/ready/imaging rules live in code, not in the schema; do not move them into the database.

## 5. Documentation (mandatory, with this prompt)

Update **all nine docs** in this same change. If a doc has no substantive change, verify that and record "reviewed, no change" in the report. Do not invent content.

- `docs/ARCHITECTURE.md`: new ADLs (continue from ADL-047) for: the Assigned Tests view and its permissions; the single shared Ready definition and why completion is not required; the new `requires_sample()` rule (imaging, explicit marker, NULL = unknown = required); the empty-room demotion rule and its scope.
- `docs/SCOPE.md`: the owner decisions above, the corrected Ready definition, the sample rule, role behaviour for reassign/view-only.
- `docs/API.md`: every new or changed endpoint, payload, permission key, error code (including the new 4xx rejections). Update endpoint and permission counts only to the real numbers.
- `docs/WORKFLOWS.md`: the corrected technician flow (save, preview, ready), the reassign flow until COMPLETED, the empty-room flow, the sample-gate flow.
- `docs/DESIGN.md`: the Assigned Tests view, the draft-preview banner, the Ready tile/tab behaviour, empty states.
- `docs/DATABASE.md`: per Section 4.
- `docs/TESTING.md`: new non-browser evidence, a **10F manual acceptance checklist for the owner** (one click path and one expected result each, for F1 to F5), the data-readiness note, and the known-not-done list kept intact. Keep the pre-go-live list (Section 12) intact.
- `README.md` and `project-context.md`: current phase = 10F done (reported), next step = owner acceptance, then the next fix/Prompt 11; counts and head.
- **Docs rule from the owner:** any item recorded in the docs as "Decided, not yet implemented" that this prompt implements must be updated from "decided" to "implemented" in the docs now. Search the docs for such entries (room routing leftovers, Ready/Preview, sample rule, empty room) and update them. Items still open (listed in Must NOT do) stay recorded as open.

## 6. Tests and validation (real results only)

Add backend tests for at least:
- F1: RECEPTIONIST cannot reassign (4xx); ADMIN and OWNER can reassign before COMPLETED; reassign refused when COMPLETED; the assigned-tests payload contains no money fields; LAB_TECH and DOCTOR cannot use the view.
- F2/F3: a saved DRAFT result is previewable; a submitted (ENTERED) result is Ready without operational Complete; DRAFT, cancelled, NOT_PERFORMED, rejected and AWAITING_DOCTOR orders are not Ready; the tile count, the Lab Ready list and the sidebar list agree (one shared definition); money fields only for money-permitted roles.
- F4: non-imaging NULL `sample_type` requires a sample (result save and Complete rejected before Sample Taken); explicit "None"/"N/A" does not; imaging with NULL does not; the helper has one definition; existing locked/completed orders are unaffected.
- F5: demotion on technician deactivate, on room change and on role change; progress states untouched; audit rows written in the same transaction; release on adding a technician.

Run and report the actual results: `pytest` (against `medscope_test` only), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`. Update the two Playwright specs under `frontend/e2e/` only if the changed UI makes their selectors stale; **do not run them** (the password env var is not available to you, and browser testing is banned for you). State that plainly in the report.

## 7. Report: `report/PROMPT_10F_IMPLEMENTATION_REPORT.md`

Sections: Done / Partial / Blocked / Deferred (real results only). For F2 and F3 include a **Root cause** subsection. Include: an **Assumptions table** for the owner to confirm or reverse (include at least: Preview available for DRAFT and ENTERED; Ready = ENTERED without operational Complete; imaging definition used; demotion only for assigned-only states; new permission key or reuse), files changed, migration/head (or "no schema change" with proof), API and permission changes with real counts, docs updated per file, validation command results with real numbers, and anything doubtful you noticed but did not fix.

## 8. Must NOT do

- No browser testing, no Playwright run, no app opened in a browser.
- Do not implement Module 14 (no `report_versions`, no finalize, no signatures, no QR, no SMS), Module 15, Module 16, or anything from Prompt 11 (no delete buttons, no soft delete, no draft discard, no confirm-dialog framework).
- Do not touch these open items, which the owner will decide later: the room mapping of the 671 unmapped tests, the urgent-fee floor/cap rule, the master-discount behaviour (A3), the doctor sign-off screen, `performing_role` normalization, the reduced-motion/pause-animations control. Do not change refund, invoice, payment or channel logic.
- Do not modify catalog data, including `sample_type`, and do not seed or backfill any clinical or catalog value.
- Do not create a DOCTOR user, change any password, or print or repeat any password, secret or connection string.
- Do not build the Audit Trail or Accounting modules; only write the audit rows this prompt requires, in the same transaction.
- Do not commit, push, stash or reset. Do not restore, delete or move the 13 tracked-but-deleted files. Do not edit past reports or the master context file.
- Do not start the next prompt or module.

*End of Prompt 10F.*
