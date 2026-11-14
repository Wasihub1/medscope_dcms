# Prompt 10F — Owner Browser Findings (#1, #2, #3) + A5 Sample Rule + A11 Empty Room: Report

- **Date:** 2026-11-13. Uncommitted working tree on `main` (on top of the uncommitted 10D/10E work). Nothing was committed, pushed, stashed or reset.
- **Dev DB:** `medscope_dcms` — **read-only inspection only** (`SET TRANSACTION READ ONLY`); nothing was written, so no new backup was needed. **No schema change** (proof in §5).
- **Tests:** `pytest` ran only against `medscope_test`; the conftest safety guard is unchanged.
- **Browser:** not used. Playwright was **not run** (`MEDSCOPE_E2E_PASSWORD` is not set in this environment, and browser testing is banned for the agent; it is the owner's acceptance step).
- **Secrets:** no password, token or connection string was written or printed. Test users get passwords generated at runtime.
- **Catalog data:** `tests.sample_type` was **not** touched — no backfill, no guess, no seed. Existing orders, results and locks were not altered.

## 1. Summary

| Item | Status | Note |
|---|---|---|
| F1 Assigned Tests view | **Done** | New tab on the existing Assign Tests page; `GET /assignments/orders`; reuses the 10E reassign endpoint; view-only for front desk. |
| F2 Preview after save | **Done** | New read-only preview endpoint for DRAFT and ENTERED; DRAFT banner; "just saved" strip; no print/finalize (Module 14 untouched). |
| F3 Ready Reports fill | **Done** | One shared `ready_clause()` for tile count, Lab tab and the new sidebar `GET /reports/ready`; `/reports` gained a Ready Results tab. |
| F4 A5 sample rule | **Done** | NULL/empty = sample required; explicit markers = no sample; imaging redefined; gates on save/complete/culture/outsourced; catalog untouched. |
| F5 A11 empty room | **Done** | One shared routine on every path (deactivate, room change, role change, CLI); only assigned-only orders demoted; audited in the same transaction. |
| Schema | **Done (none)** | No migration. `alembic heads` single head `f3c9a1d7e5b2`, `alembic check` clean; recorded in `docs/DATABASE.md`. |
| Docs | **Done** | All nine updated; ADL-048 to ADL-051; "decided → implemented" labels flipped (details §7). |
| Tests / validation | **Done** | 122 passed (was 110); `tsc -b`, oxlint (0 errors / 120 warnings baseline), `vite build`, alembic all clean. |

## 2. What I found before changing anything (Section 1 reading)

- **Baseline verified:** head `f3c9a1d7e5b2` (single), `alembic check` clean, pytest **110 passed**, `git status` large with the uncommitted 10D/10E work and the 13 tracked-but-deleted files (untouched).
- **F1:** there was **no** "every order" view. `/assignments` (Assign Tests, `assignment.manage`) listed only `UNASSIGNED` orders; `/worklist` for Admin/Owner shows all orders but is a technician workbench (and is not visible to Receptionist at all). The 10E reassign endpoint `POST /worklist/{id}/reassign` (`worklist.reassign`, ADMIN/OWNER default) already existed with reason + append-only `assignment_history` + audit, and returned 409 for COMPLETED/cancelled — but nothing for REJECTED/SPOILED (outcome NOT_PERFORMED), which were reassignable.
- **F2:** `ResultReportPreviewModal` existed (10E) and the API did return `has_result` for saved rows. Root cause confirmed in §3. The 10E preview read `GET /worklist/{id}/result` = the **result template endpoint**, whose guards (sample collected, not REJECTED) also block previewing — e.g. a rejected order's saved draft (dev order 89) could not be previewed.
- **F3:** confirmed all three suspected causes (§3). Dev DB read-only check: orders with results were 89 (REJECTED, DRAFT), 176 (AWAITING_DOCTOR, DRAFT), 30 + 269 (COMPLETED, ENTERED), 31 (AWAITING_DOCTOR, ENTERED, USG). `report_versions` = 6 rows, all from seed. `/reports` read only `report_versions` → always "empty" for new work.
- **F4:** `requires_sample` (10E) treated NULL/empty/"None"/"N/A" as "no sample"; `is_imaging_test` counted `requires_doctor`/role DOCTOR as imaging. Catalog: 1,228 of 1,250 tests have NULL `sample_type` (the 10E migration normalized 4 "None" strings). Gates present in 10E: result template, result save, Complete, invoice sample status, imaging lock. **Missing gates:** culture stage and outsourced dispatch could run with no sample. Exactly one helper existed (no duplicates) — kept that way.
- **F5:** room-emptying paths found: `set_user_active(False)`, `update_user` (lab_section change), `set_user_role` (away from LAB_TECH), and the CLI `manage_users.py assign-role`. None demoted anything (10E assumption A11: orders stayed ASSIGNED). The release path (`release_unassigned_orders_for_section`) ran on the join side only. **Also found:** `revoke_all_user_sessions` issued its own `db.commit()`, so deactivate/role-change committed the staff row **before** the audit row — the same class of bug as the 10E lost-audit-row fix (fixed, §4-F5).
- **Status field:** `test_orders.status` mixes assignment state (UNASSIGNED/ASSIGNED) with progress (SAMPLE_PENDING/IN_PROGRESS/AWAITING_DOCTOR/PENDING/COMPLETED/CANCELLED/REJECTED/SPOILED). An ASSIGNED order can still carry work (a DRAFT result saved on a no-sample test under the 10E rule keeps status ASSIGNED) — which shaped the demotion predicate (§4-F5).

## 3. Root causes (F2 and F3)

**F2 — no Preview after saving a result.**
1. *(primary)* In `TechnicianWorklistPage.tsx` the whole standard action block was gated on `order.status !== 'COMPLETED'`, and for a `TECHNICIAN_FINAL` test submitting a result sets the order to COMPLETED — so right after "Submit Results" the row lost its action area. The 10E Preview button itself was outside that gate, **but** the row usually *disappears from the active tab* after save (e.g. the user works in "Sample Pending" or "In Progress"; the saved order no longer matches the filter), so the owner saw no Preview anywhere. The grid did refetch (`onSuccess={fetchData}`), so staleness was not the cause.
2. *(secondary)* The preview fetched the result-template endpoint, whose entry guards (REJECTED/SPOILED block, sample-collected check) also refuse legitimate previews of already-saved results.

**Fix:** a dedicated read-only `GET /worklist/{id}/result-preview` with no result-entry guards (404 only when no result is saved), plus a "Result saved … — Preview Report" strip above the grid that survives the row leaving the active filter, and the row button for DRAFT and ENTERED.

**F3 — Ready never fills.**
1. *(confirmed)* The 10E Lab definition was "order COMPLETED **and** result ENTERED". Saving ENTERED only completes `TECHNICIAN_FINAL` non-culture tests; `BOTH_SIGNATURES` tests and cultures before stage FINAL stay IN_PROGRESS, doctor-routed go to AWAITING_DOCTOR — those never matched. (On the owner's machine the clicked tile could legitimately show 0 while results existed.)
2. *(confirmed)* Tile count and list used **two different computations** (Python count over up-to-1000 loaded items vs. the SQL filter) — same intent, but duplicated and divergence-prone; the sidebar was a third, different source.
3. *(confirmed)* The sidebar `/reports` read only `report_versions` with `authorized = true`; nothing creates report versions (Module 14 not built; only seed rows exist), so newly ready results could never appear and the empty text ("No deliverable reports found") was misleading.

**Fix:** one `ready_clause()` in the new `ready_report_service.py` used by the tile count (SQL, same visibility base statement), the Lab `status=READY` list, the row flag `report_ready`, and the new `GET /reports/ready` — they cannot disagree. Definition per the owner's expectation (assumption table §8): **ENTERED result; order not cancelled, not Not Performed, not AWAITING_DOCTOR; Complete not required.** `/reports` now opens on a "Ready Results" tab; "Issued Reports" keeps the `report_versions` list with an honest empty text.

## 4. Implementation details

### F1 — Assigned Tests view
- **Home:** the existing **Assign Tests** page (`/assignments`) — it is the sidebar's assignment surface for exactly the right roles (`assignment.manage`: RECEPTIONIST, CASHIER, ADMIN, OWNER; never LAB_TECH/DOCTOR), already fetches rooms, and avoids a duplicate page. It now has two tabs: **Unassigned (n)** (the untouched routing table) and **Assigned Tests** (new `AssignedTestsPanel.tsx`).
- **Backend:** `GET /assignments/orders` (`assignment_service.list_assigned_test_orders`): every test order, newest first, with invoice no, patient (+code), test (+code), room, the room's **active technician names** (one query, grouped) or `assignment_state: "UNASSIGNED"` (explicit when the order is UNASSIGNED, has no room, or its room has no active technician), status (CANCELLED when the invoice line is cancelled), urgent, `result_status`, `worked_by_name`, created time; filters `status` (incl. OPEN / NOT_PERFORMED; unknown → 400), `lab_section` (incl. NONE), `q`; `limit ≤ 500`. **No money field** (schema has none; test asserts recursively).
- **Permissions:** existing keys reused — no new key, count stays **35** (20 money). View = `assignment.manage`; move = `worklist.reassign`. The backend computes `can_reassign` + `reassign_block_reason` per row; a Receptionist's reassign call returns 403 (tested).
- **One reassign path:** the panel's Reassign Room modal calls the existing `POST /worklist/{id}/reassign`. New single rule `routing_service.reassign_block_reason(order)` used by the endpoint (`move_order_to_room`), the list and the UI: 409 for COMPLETED ("Completed: a COMPLETED order cannot be moved…"), cancelled, and **Not Performed** (REJECTED/SPOILED or outcome NOT_PERFORMED — new; before 10F those were movable). My Work's Reassign button now hides for Not Performed rows too.
- **Freshness:** after a move the panel refetches and notifies the parent; all three new/changed list pages (Assigned Tests, Ready Results, My Work) refetch on window focus via the new `useRefetchOnFocus` hook (throttled, 2 s) and on navigation (mount).

### F2 / F3 — Preview and Ready
- **New service `backend/app/services/ready_report_service.py`:** `ready_clause()` (with a code comment marking where Module 14 will exclude orders that already have a Final report version), `ready_order_ids` (batch), `list_ready_reports` (sidebar rows; `invoice_due`/`has_due` only via `can_see_money` = not money-restricted **and** `payment.view`, otherwise the keys are omitted — `response_model_exclude_unset`), `build_result_preview` (snapshots only: component name, code, value, unit, reference range, **critical limits as saved**, flag, comment; findings/impression/comments; USG structured data; `is_draft`, `is_ready`).
- **Endpoints:** `GET /worklist/{id}/result-preview` (`worklist.view` + the usual room access) and `GET /reports/ready` + `GET /reports/ready/{id}/preview` (`report.view`). All read-only; 404 with "No result has been saved…" when none.
- **Worklist service:** `status=READY` and the summary `ready_count` now use `ready_clause()` on the same visibility base (`_worklist_base_stmt`, extracted); `report_ready` per row from the same clause (batched). The `IMAGING` filter now uses `imaging_sql_clause` — the same single imaging definition as the sample rule.
- **Frontend:** `ResultReportPreviewModal` rewritten for the new endpoint (`source` 'lab' | 'reports'): dashed amber **"DRAFT, not a final report"** banner for drafts, a quiet "Result submitted and Ready…" note otherwise, a Critical column, structured USG findings, **no print button** (the 10E modal had `window.print()` — removed; preview only). `ResultEntryModal.onSuccess` now reports the saved status; the worklist page shows the dismissible "Result saved… Preview Report" strip. Ready-filter empty state explains Drafts are not Ready. `/reports`: tabs **Ready Results** (default; new `ReadyResultsPanel.tsx` with search, room filter, due badge for money roles, Preview) and **Issued Reports** (existing table; `?id=` deep links open on it); both empty texts corrected.

### F4 — A5 sample rule
- **`backend/app/core/samples.py` rewritten (still the only source of truth; a 10F test asserts exactly one `def requires_sample(` / `def is_imaging_test(` in the backend and that the old `NO_SAMPLE_VALUES` name is gone):**
  - **Imaging definition (exact):** `tests.lab_section == 'ULTRASONOGRAPHY'`, **or** department contains one of `ultrasono, usg, x-ray, xray, radiolog, imaging` (case-insensitive), **or** `report_template == 'NARRATIVE'`. `requires_doctor` / performing-role DOCTOR **no longer** make a test imaging on their own — dev catalog check: TC-410 "Duodenal Tissue (M)" (doctor-read tissue, Clinical Pathology) is now sample-required, while all USG/X-ray tests stay imaging. Dev catalog under the new rule: **51 imaging / 1,199 sample-required / 0 explicit no-sample**.
  - Explicit markers `none, n/a, na, no sample` (trimmed, lower-cased) → no sample. **NULL or empty → unknown → sample required.** Any other value → sample required. FULL route still forces a sample unless imaging.
- **Gates (all 4xx with the plain message "Take the sample before entering results / completing this test / this step: the specimen has not been collected yet. Record 'Sample Taken' first."** — the 07C test's expected substring is preserved): result template 400, result save DRAFT **and** ENTERED 409, operational Complete 400, **new:** culture-stage 400 and outsourced SENT 400. The UI shows backend messages as error toasts (existing pattern) and adds a small "Take the sample before entering results" hint under the Sample Taken button; Enter Results/Complete render only when `canWork` (collected or not required), as before, now with the corrected `requires_sample` flag from the API.
- **Line lock / invoice mapping:** unchanged mechanics — the lock happens at Sample Taken (or imaging Perform Scan), which the new rule now guarantees for non-imaging tests before any result exists. Invoice `sample_status`: "No sample needed" only for explicit markers; a **legacy** order completed without a sample under the 10E rule shows "Completed without sample" (dev DB: exactly one, order 269) instead of the wrong "Awaiting collection". Existing orders, results and locks were not modified.
- **Dev-DB effect (read-only):** 29 of 38 open orders now wait for Sample Taken. Data-readiness note added to `docs/TESTING.md` §13.2.

### F5 — A11 empty room
- **One shared routine:** `routing_service.apply_technician_room_change(old_section, old_counts, new_section, new_counts, …)` — demotes the room left (`demote_assigned_orders_if_room_empty`) and releases the room joined (existing `release_unassigned_orders_for_section`). Called **after the staff change is flushed, in the same transaction**, from: `create_user`, `update_user` (room change), `set_user_role`, `set_user_active` (deactivate **and** reactivate) in `user_admin_service.py` (one wrapper `_apply_room_change`), and from the CLI `manage_users.py assign-role` (acting role `SYSTEM_CLI`, with a `USER_ROLE_CHANGED` audit row the CLI previously never wrote).
- **Demoted = assigned-only:** status `ASSIGNED` **and** no `samples` row **and** no `results` row (not even DRAFT) **and** `culture_stage IS NULL` **and** `outsourced_status IS NULL`, on a non-cancelled line. **Left untouched:** UNASSIGNED (already), SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, PENDING (outsourced), COMPLETED, CANCELLED, REJECTED/SPOILED — and any ASSIGNED order with recorded work. Why: `status` mixes assignment with progress; a sample locks the line, a result (even a draft) is work product, a culture/outsourced step is in flight — demoting those would wipe or orphan progress. `lab_section` is **kept**, so Admin/Owner still see the orders (My Work Unassigned tile, Assign Tests both tabs) and the existing release returns exactly them to ASSIGNED when a technician joins (verified: release touches only UNASSIGNED orders).
- **Per demoted order, same transaction:** audit `ORDER_UNASSIGNED_ROOM_EMPTY`, event `ROOM_EMPTIED`, append-only `assignment_history` row (previous = room name, new = "UNASSIGNED"; skipped for the CLI, which has no staff actor id — `changed_by_id` is NOT NULL). Plus the existing user-action audit.
- **Transaction fix (found while testing):** `auth_service.revoke_all_user_sessions` did `db.commit()` internally, committing the staff change before its audit row and any demotion (a crash in between would have lost them — the 10E lost-audit-row class). It now takes `commit: bool = True`; the three `user_admin_service` call sites pass `commit=False` so everything commits once at the endpoint. Other callers (password change/reset in `auth_service`, CLI) keep the old behaviour. A test deactivates via the service, verifies user change + demotion + both audit rows are pending in one open transaction, then **rolls back** and confirms nothing was half-applied.

## 5. Schema and DDL (none)

No schema change was needed — all 10F rules live in code (permission defaults, Ready definition, sample rule, imaging definition, demotion rule), per the prompt. Proof (real output):
- `alembic heads` → `f3c9a1d7e5b2 (head)` (single head, unchanged)
- `alembic current` (dev DB) → `f3c9a1d7e5b2 (head)`
- `alembic check` → `No new upgrade operations detected.`
- Recorded in `docs/DATABASE.md` (§1 and the migration-history note): "Prompt 10F was reviewed with no schema change". New free-text audit `action` `ORDER_UNASSIGNED_ROOM_EMPTY` and event type `ROOM_EMPTIED` need no DDL. No backup was taken because nothing was applied to `medscope_dcms` (read-only transactions only).

## 6. API and permission changes (real numbers)

- **OpenAPI: 85 paths / 98 operations** (was 81 / 94). Added (all read-only GET): `/assignments/orders`, `/worklist/{id}/result-preview`, `/reports/ready`, `/reports/ready/{id}/preview`.
- **Changed behaviour:** `POST /worklist/{id}/reassign` → 409 also for Not Performed; `POST /worklist/{id}/culture-stage` and `POST /worklist/{id}/outsourced` (SENT) → new 400 sample gate; result save/template/Complete keep their codes with the plain 10F message; `GET /worklist?status=READY`, `summary.ready_count`, `report_ready` → shared Ready definition; `status=IMAGING` → shared imaging definition; invoice line `sample_status` may be "Completed without sample".
- **Permissions: 35 keys, 20 money — unchanged.** Reused: `assignment.manage` (view), `worklist.reassign` (move), `report.view` (ready list/preview), `payment.view` + money-restriction (due visibility). Documented in `docs/API.md` §5.1.

## 7. Documentation (all nine, this change)

| File | What changed |
|---|---|
| `docs/ARCHITECTURE.md` | ADL-048 (Assigned Tests view + permissions), ADL-049 (one Ready definition + why Complete is not required; preview), ADL-050 (sample rule: imaging / explicit marker / NULL = required), ADL-051 (empty-room demotion + scope + transaction fix); ADL-046/047 marked superseded, ADL-041 cross-noted; directory layout (new files); schema-policy line (10F no change). |
| `docs/SCOPE.md` | Matrix rows for the three new capabilities; §4.18 10F invariants; 10E sample bullet marked superseded; owner-decision table rows 8–10 (A5, A11, findings — implemented); §5.1 gap "room left without technicians" flipped to implemented; still-open list kept (671 rooms, urgent-fee rule, A3, doctor sign-off, `performing_role`, reduced motion). |
| `docs/API.md` | Counts 85/98; the 4 new endpoints with full payloads and roles; changed 4xx behaviour per endpoint; Ready/IMAGING filter text; permission note (no new key). |
| `docs/WORKFLOWS.md` | Lifecycle diagram (sample-required note, empty-room branch, Ready note); wiring matrix rows (Assigned Tests, reassign-from-list, preview, Ready tile/tab, Ready Results/Issued tabs); §5.3 empty-room staff note; new §8 (technician save→preview→ready flow, reassign-until-COMPLETED flow, empty-room flow, sample-gate flow); 10E §7.2/§7.6 marked superseded. |
| `docs/DESIGN.md` | New "Prompt 10F Worklist UI" and "Prompt 10F Front-Desk UI" sections (draft banner, just-saved strip, Ready tile/tab behaviour, Assigned Tests table, Ready Results table, empty states, lock reasons); 10E preview/ready lines corrected; new `data-testid` list. |
| `docs/DATABASE.md` | §1 + migration history: 10F reviewed, **no schema change** (with the command results); `tests.sample_type` semantics note (10F reversal, no data change); new audit action/event values. |
| `docs/TESTING.md` | Test module 11 described; run count 122; 10E helper-test updates noted; new §13: real 10F evidence table, **data-readiness note** (§13.2), **owner acceptance checklist F1–F5** (§13.3, one click path + one expected result each), known-not-done list (§13.4); §11 marked superseded; **§12 pre-go-live list untouched**. |
| `README.md` | 10F feature bullet; counts 85/98; head note; current phase = **10F done (reported), next step = owner acceptance**; Playwright not-run note extended. |
| `project-context.md` | New "Prompt 10F" section (current phase + next step, what was done per item, validation numbers, still-open); two historical 10E lines annotated. |

**Decided → implemented labels flipped:** SCOPE §5.1 "room left without technicians" (A11), SCOPE/ARCHITECTURE sample-rule entries (A5), the Ready/Preview behaviour (ADL-047 → ADL-049), and the owner-decision table. Still recorded as open: Prompt 11, doctor sign-off, `performing_role`, 671 unmapped tests, urgent-fee floor/cap (A1), master discount (A3), reduced motion, credential cleanup.

## 8. Assumptions table (for the owner to confirm or reverse)

| # | Assumption / choice | How to reverse |
|---|---|---|
| B1 | **Preview is available for DRAFT and ENTERED** results, for every role that can see the order (technician: own room; front desk: via Ready Reports for Ready ones). DRAFT previews carry a "DRAFT, not a final report" banner. | Gate the row button on `result_status === 'ENTERED'` and restrict `build_result_preview`. |
| B2 | **Ready = ENTERED result** on an order that is not cancelled, not Not Performed and not AWAITING_DOCTOR; **operational Complete is NOT required**. A doctor-routed result becomes Ready when the doctor completes the order. | One place: `ready_clause()` in `ready_report_service.py` (e.g. add `status == COMPLETED` back). |
| B3 | **Imaging =** Ultrasonography room, or department containing ultrasono/usg/x-ray/xray/radiolog/imaging, or NARRATIVE template. `requires_doctor` alone is **not** imaging any more (a doctor-read tissue test needs its specimen). | Edit the constants at the top of `backend/app/core/samples.py`. |
| B4 | **Explicit no-sample markers:** `None`, `N/A`, `NA`, `No sample` (trimmed, any case). `Nil` / `Not applicable` (10E markers) are no longer markers — none exist in the catalog. | Edit `NO_SAMPLE_MARKERS` in `samples.py`. |
| B5 | **Demotion only for assigned-only orders:** status ASSIGNED with no sample, no result (even DRAFT), no culture stage, no outsourced step. Everything else keeps its state. | Edit the predicate in `demote_assigned_orders_if_room_empty`. |
| B6 | **No new permission key:** Assigned Tests reuses `assignment.manage` (so CASHIER also sees it view-only) + `worklist.reassign`; the Ready due indicator uses the existing money check (`payment.view` + role restriction). | Add a key in `permissions.py` and swap the dependencies (would raise the count past 35). |
| B7 | **`/reports` default tab is Ready Results**; Issued Reports (deliveries) is the second tab; `?id=` deep links open Issued. The sidebar label stays "Ready Reports". | One `useState` initial value in `ReportsPage.tsx`. |
| B8 | **Legacy orders completed without a sample** (under the 10E rule) stay COMPLETED and previewable; invoice shows "Completed without sample". Dev DB: order 269. | They could instead be flagged for recollection — manual decision, not automated. |
| B9 | The CLI demotion writes audit rows as `SYSTEM_CLI` with no actor id and **no** assignment-history row (that table requires a staff id). | Give the CLI a real staff actor argument. |

## 9. Files changed

- **New (backend):** `backend/app/services/ready_report_service.py`.
- **New (frontend):** `frontend/src/features/assignments/AssignedTestsPanel.tsx`, `frontend/src/features/reports/ReadyResultsPanel.tsx`, `frontend/src/utils/useRefetchOnFocus.ts`.
- **New (tests):** `tests/test_prompt10f_owner_findings.py` (12 tests). This report.
- **Modified (backend):** `core/samples.py` (rewritten), `services/routing_service.py`, `services/user_admin_service.py`, `services/worklist_service.py`, `services/result_service.py`, `services/assignment_service.py`, `services/auth_service.py` (commit flag), `api/v1/endpoints/worklist.py`, `api/v1/endpoints/reports.py`, `api/v1/endpoints/assignments.py`, `api/v1/endpoints/invoices.py` (sample-status mapping), `schemas/report.py`, `schemas/assignment.py`, `scripts/manage_users.py`.
- **Modified (frontend):** `api/client.ts`, `types/index.ts`, `components/common/ResultReportPreviewModal.tsx` (rewritten), `components/common/ResultEntryModal.tsx` (saved-status callback), `features/worklist/TechnicianWorklistPage.tsx`, `features/assignments/AssignmentsPage.tsx`, `features/reports/ReportsPage.tsx`, `e2e/test_modal_regression.spec.ts` (A5 opens the Issued tab; **not run**).
- **Modified (tests):** `tests/test_prompt10e_invoice_payment_samples.py` (helper test now encodes the 10F rule; migration check ignores 10F probe tests).
- **Modified (docs):** all nine (§7). Past reports, the master context file, the 13 tracked-but-deleted files: untouched.

## 10. Tests and validation (real results, 2026-11-13)

| Command | Result |
|---|---|
| `python -m pytest -q` (`medscope_test` only) | **122 passed, 0 failed** (baseline 110; +12 new; re-run twice — stable against the persistent test DB) |
| `tsc -b` | exit 0 |
| `npm run lint` (oxlint) | exit 0, **0 errors, 120 warning lines** (baseline unchanged; the one new-warning my first hook draft added was removed) |
| `vite build` (output to scratchpad) | built; the usual >500 kB chunk warning |
| `alembic heads` / `alembic current` / `alembic check` | `f3c9a1d7e5b2 (head)` / dev DB at head / `No new upgrade operations detected.` |
| OpenAPI | **85 paths / 98 operations**; permissions **35 keys / 20 money** |
| `npx playwright test --list` | 12 tests in 2 files (specs parse) |
| Playwright run | **Not run** — `MEDSCOPE_E2E_PASSWORD` is not available to the agent and browser testing is banned for it; the owner does browser acceptance (checklist `docs/TESTING.md` §13.3). No browser acceptance is claimed. |

**New test coverage (per the prompt's Section 6 list):** F1 — receptionist 4xx on reassign, view-only flag, Admin+Owner reassign before COMPLETED (audit + history), 409 on COMPLETED and Not Performed, money-free payload, LAB_TECH/DOCTOR 403 on the view, filters, 400 on bad status. F2/F3 — DRAFT previewable + marked + not Ready; ENTERED Ready without Complete (BOTH_SIGNATURES stays IN_PROGRESS); DRAFT/cancelled/NOT_PERFORMED(rejected)/AWAITING_DOCTOR not Ready; tile count = Lab list = sidebar list; money fields only for money roles (override-stripped receptionist gets none; tech/doctor 403); no `report_versions` row; preview 404 without a result; room access on preview. F4 — helper truth table (NULL/empty required, markers not, imaging via room/department/template, doctor-read tissue NOT imaging); single definition asserted by source scan; all five gates blocked before Sample Taken then allowed after, with the line locking at collection; explicit markers and imaging proceed; legacy completed order untouched and labelled. F5 — deactivate/room-change/role-change demote; only the assigned-only order (draft-result, IN_PROGRESS, AWAITING_DOCTOR, COMPLETED siblings untouched); audit + history rows; same-transaction proof by rollback; release cycle returns exactly the demoted order.

## 11. Doubtful things noticed but not fixed

- **An active DOCTOR user exists in the dev DB** (read-only check). Prompt 10E reported none was created and 10F created none; it appeared outside these prompts (presumably the owner). Left as is per the "do not create/change users" rule.
- **Dev data under the new sample rule:** 29 of 38 open orders now require Sample Taken before results (expected and safe, but a real workload change for technicians until `sample_type` is filled — §13.2 of TESTING).
- **Order 269** was completed without a sample under the 10E rule (never locked, never deducted stock). Not altered; labelled "Completed without sample" (assumption B8).
- **`/reports/ready` and the Lab lists cap at their `limit`** (200); the tile count is exact SQL. The agreement tests guard this; with >200 ready results the sidebar list would paginate short. Fine at current volumes.
- **Ready `result_entered_at`** is the submitted result's last-save time (`updated_at`), not first entry — chosen deliberately so re-submitted corrections float up.
- **`tech_micro` and `tech_boss`** both sit in MICROBIOLOGY in the dev DB, so emptying that room needs both deactivated — mentioned so the owner's F5 acceptance test uses a single-technician room (Hematology or Biochemistry or Ultrasonography).
- The three user-management mutation paths (`set_user_role`, `set_user_active`, `reset_user_password`) now pass `commit=False` to `revoke_all_user_sessions`; the two **auth-service** paths (own password change, admin reset inside `auth_service`) keep the old self-committing behaviour to keep 10F small — their only follow-up write is one audit row, so the exposure window is tiny.

*End of Prompt 10F report.*
