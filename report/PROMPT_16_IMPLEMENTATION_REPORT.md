# Prompt 16 Implementation Report: Module 14, Draft to Final Report

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset. The master context file was not edited. Module 15 (corrections) was not started. **No real SMS, WhatsApp, QR, PDF/print or signature-image upload work was attempted, and no message was sent.**

## 1. What I found first (the premises that were wrong or incomplete)

| Question | Finding |
|---|---|
| Does `report_versions` exist? | **Yes.** The prompt assumed a new table. It already existed (seeded, status `FINAL_AUTHORIZED`, `authorized`, `report_no`, `version`, `issued_at`, `issued_by_id`, deliveries). Six seeded rows in both DBs; delivery (`report_deliveries`), the due-hold rule, printable preview, dashboard and search already read it. I **extended** it instead of creating a second table. The Final state is therefore the existing value `FINAL_AUTHORIZED` (renaming it would touch many call sites). |
| Was the Issued Reports tab empty? | **No.** It lists the six seeded reports (and works with delivery). It only never received reports from real results. |
| Is `COMPLETED` treated as "the report is final"? | **No.** `COMPLETED` is purely operational: set by a technician-final result submit, by the generic status action, and (Prompt 15) by a doctor approval. Nothing created a report from it. Side effect worth knowing: a technician-final result was already COMPLETED and locked at submit, so its result could not be re-saved even though no Final report existed. |
| Culture stage vs report Final | Not confused anywhere: stage `FINAL` only gates the status action and the result submit status; it never created a report. It is now one condition of finalization. Recording stage FINAL does not by itself finalize a technician-final culture. |
| `doctor_approvals` | Approval moved the order to COMPLETED and nothing else; no consumer. |
| Existing concurrency guard | **None.** Two people could overwrite each other's draft silently. |
| Auto-save | **Does not exist.** The result modal only has a Save Draft button. (The prompt says to confirm it still works: there is nothing to disturb.) I did not build it. |
| Cancellation after Final | A COMPLETED result locks its line, so ordinary cancellation is refused; the owner same-day unlock (D14) only unlocks the line and does not touch order, result or report; `list_deliverable_reports` already hides reports whose line is CANCELLED. Left as is, no report-cancellation mechanism built (Module 15 / 29). |
| Existing "Finalize" permission | None. The permission matrix had no "finalize report" key. |
| Real-data state | `medscope_dcms` already has 2 approvals recorded by the DOCTOR user `doc` after Prompt 15 (orders 78 and 287, both COMPLETED, results ENTERED) that have no Final report. I did not fabricate reports for them: they show in Ready Results with Finalize enabled, and finalizing creates real reports. |
| Alembic head before | `c9a4e7b2d815` (single). Git: unchanged (2 commits, work uncommitted). |

## 2. Done / Partial / Blocked / Deferred

### Item 1: report version model and Final state: **Done**
- `report_versions` extended (all nullable): `result_id`, `approval_rule`, `doctor_approval_id`, `content_snapshot` (JSON), `signatures` (JSON). Finalization time and user reuse `issued_at` / `issued_by_id`; `version` is always 1; `status = FINAL_AUTHORIZED` is Final. Draft stays `results.status = DRAFT` (no row).
- Snapshot content: the existing result preview (built from the result items' own D24 range snapshots, flags, findings), made money-free and stored once. Nothing is duplicated into new item tables.
- **Immutability:** ORM `before_update` guard + a **database trigger** `trg_report_versions_immutable` rejecting any change to `test_order_id`, `report_no`, `version`, `findings_summary`, `issued_at`, `issued_by_id`, `result_id`, `approval_rule`, `doctor_approval_id`, `content_snapshot`, `signatures`, for any writer. `status` / `authorized` stay changeable for Module 15. One Final per order by a partial unique index. The result of an order with a Final report (or a doctor approval) can no longer be saved. **Design note:** if the underlying result, test or ranges ever change, the report row does not; there is no correction path (Module 15).

### Item 2: who finalizes: **Done**
- **technician-final:** explicit **Finalize report** (new endpoint `POST /worklist/{id}/finalize-report`, key `result.enter` + the existing room/doctor-queue access check). Distinct from submitting the result.
- **doctor-required and both-signature: automatic, in the same transaction as the doctor approval.** Reasons: the approval *is* the scope's approval step; a second click only creates a half-approved state; one transaction means the approval and the report exist together or not at all; and it is the same rule for both types (consistency). Implemented once in `report_finalization_service.finalize_blocker`, used by the explicit endpoint, the approval and the culture step.
- **both-signature:** blocked until both exist: the technician sign-off (a submitted ENTERED result, unchanged) and the doctor approval (unchanged). Tested: blocked with "Waiting for the doctor's approval", created with the approval.
- **cultures:** wait for stage FINAL. A doctor approval given earlier finalizes automatically when the stage reaches FINAL (hook in the culture-stage step); a technician-final culture needs the explicit click after FINAL.
- **Blocked states:** cancelled, rejected, spoiled, Not Performed outcome, cancelled line, rejected/spoiled sample, missing or draft result, missing approval, culture not FINAL, already Final. The existing status checks were *not* enough on their own (no code path checked these for finalization), so the check is in the finalization service; tested for all four dead states.
- After finalizing, an order still IN_PROGRESS / AWAITING_DOCTOR becomes COMPLETED (line locked) so Final reports never sit on an open order.

### Item 3: concurrency and auto-save: **Done (guard added); auto-save not present**
- No guard existed. Added a simple optimistic check: `results.updated_by_id` + optional `expected_updated_at` on result save; a mismatch returns 409 "changed by X at HH:MM after you opened it". The result modal sends the stamp it loaded; API callers that omit it behave as before. Not a lock, not collaborative editing.
- Auto-save does not exist (see section 1); not built, reported.

### Item 4: signatures: **Done (text only)**
`signatures` stores technician name, role and sign time (the last saver, via `updated_by_id`; falls back to the first saver) and, for doctor rules, doctor name, registration number, approval time, who recorded it and `is_attestation`. **Not built:** signature image / seal upload (stated limitation; belongs with print/PDF).

### Item 5: report-ready SMS hook: **Done (placeholder only)**
New table `notification_log` (`REPORT_READY_SMS`, `PENDING_INTEGRATION`, report id, patient id, note; no phone number, no message text) plus audit rows `REPORT_FINALIZED` and `REPORT_READY_NOTIFICATION_DUE`. **No SMS was sent or attempted; no gateway code exists.** Tested that only `PENDING_INTEGRATION` rows exist and the table has no phone/message column.

### Item 6: Issued Reports tab: **Done**
- The existing tab (search, due filter, delivery) now also lists every Final report. A **View result** button opens a modal showing the stored snapshot with the shared `ResultPreviewBody` (reused, not duplicated). New `GET /reports/{id}/snapshot` (`report.view`). Seeded older reports have no snapshot and say so.
- A Final report leaves Ready in every list (the Ready definition now excludes orders with a Final report, the hook the Prompt 10F comment reserved).
- The Preview Report modal (used by the Lab Ready tab and sidebar Ready Results) gained the Finalize area and a Final banner with signatures.

### Partial / Blocked / Deferred
- Deferred by instruction: Module 15, SMS/QR/PDF, signature uploads.
- Observed, unchanged: a both-signature result is still listed as Ready before the doctor signs (cannot be finalized until then).
- **Process deviation (disclosed):** the migration was applied to `medscope_dcms` **before** I took the `pg_dump` (a shell command ran `alembic upgrade head` without the test-DB override). The prompt required the dump first. Impact check: the migration is additive; I re-counted afterwards and nothing changed (6 report versions, 4 deliveries, 22 results, 69 test orders; 2 doctor approvals made by the owner's own testing). The only dump taken is post-migration: `backups/medscope_dcms_prompt16_taken_after_migration.dump` (renamed so its name does not claim to be a pre-migration backup). The closest pre-migration backup is `medscope_dcms_pre_prompt15.dump` (older data). Rollback is the tested downgrade (it drops only what this prompt added; new Final reports would be lost).

## 3. Assumptions

| Assumption | Choice |
|---|---|
| Auto-finalize vs separate click for doctor rules | **Automatic with the approval, same transaction** (reasons in Item 2). Technician-final is the only explicit click. |
| Table | Extend the existing `report_versions`, not a new table; `FINAL_AUTHORIZED` is the Final value; `issued_at`/`issued_by_id` are finalized_at/by. |
| Concurrency guard | Optimistic `expected_updated_at` check + "last saved by"; no locking, no heartbeat. |
| Immutability | ORM guard + DB trigger on content columns; status/authorized excluded. |
| Who may click Finalize | `result.enter` plus the existing room / doctor-queue access ("whoever can currently complete that order"). Front desk roles (no `result.enter`) cannot. |
| Permission key | **No new key.** Existing keys already fit (`result.enter`, `report.view`); counts stay 39 / 21. |
| Technician signature | The last saver of the result (`updated_by_id`), since a re-saved draft is signed by whoever submits. |
| Orders approved before this prompt | Not back-filled (no fabricated history); the explicit Finalize works for them. |
| Order status on Final | COMPLETED (line locked) for IN_PROGRESS / AWAITING_DOCTOR orders. |
| Tests | Probe catalog tests / orders / reports created in `medscope_test` (not purged), like earlier prompts; fixture cleanup now also removes Final reports tied to throwaway doctors. |

## 4. Files changed

Backend: new `app/services/report_finalization_service.py`, migration `alembic/versions/d2b6f8a1c439_prompt16_final_reports.py`; edited `app/models/report.py` (columns, guard, `NotificationLog`), `app/models/result.py`, `app/models/__init__.py`, `app/schemas/report.py`, `app/schemas/result.py`, `app/services/result_service.py`, `app/services/doctor_approval_service.py`, `app/services/worklist_service.py` (culture FINAL hook), `app/services/ready_report_service.py`, `app/services/report_service.py`, `app/api/v1/endpoints/results.py`, `app/api/v1/endpoints/reports.py`.
Frontend: `components/common/ResultReportPreviewModal.tsx`, `components/common/ResultEntryModal.tsx`, `features/reports/ReportsPage.tsx`, `features/reports/ReadyResultsPanel.tsx`, `features/worklist/TechnicianWorklistPage.tsx`, `api/client.ts`, `types/index.ts`.
Tests: new `tests/test_prompt16_final_reports.py` (20 tests), `tests/fixture_cleanup.py`.
Docs: all nine (section 7). Backup (git-ignored): `backups/medscope_dcms_prompt16_taken_after_migration.dump`.

## 5. Migration details

| | |
|---|---|
| Revision / `down_revision` | `d2b6f8a1c439` / `c9a4e7b2d815` |
| `alembic heads` before / after | `c9a4e7b2d815` / `d2b6f8a1c439` (single both times) |
| `alembic check` after | "No new upgrade operations detected." |
| Autogenerate review | Generated: `notification_log` (+2 indexes), five columns on `report_versions`, partial unique index, `results.updated_by_id`, three foreign keys. By hand: the three unnamed foreign keys were named (`fk_report_versions_result`, `fk_report_versions_doctor_approval`, `fk_results_updated_by`) because the generated downgrade (`drop_constraint(None, ...)`) would have failed; the immutability **trigger and function were added by hand** (autogenerate cannot express them) with a matching downgrade. Purely additive, seeded rows keep NULL. |
| Round trip | `downgrade c9a4e7b2d815` then `upgrade head` on `medscope_test`: both succeed. |
| `pg_dump` | See the disclosed deviation in section 2: taken after the migration. |
| Applied to | `medscope_test` (session + manual) and `medscope_dcms` (head `d2b6f8a1c439`). |

## 6. API path / operation counts

| | Before (Prompt 15) | After |
|---|---|---|
| Paths | 110 | **112** |
| Operations | 124 | **126** |
| Permission keys / money | 39 / 21 | 39 / 21 (no new key) |
| Tables in `medscope_dcms` | 31 | 32 |

New: `POST /worklist/{id}/finalize-report`, `GET /reports/{id}/snapshot`. Changed: `GET /reports/ready`, both preview endpoints (new fields), `POST /worklist/{id}/result` (optional `expected_updated_at`, new 409s), `GET /reports` items (`has_snapshot`, `approval_rule`).

## 7. Validation results (non-browser, actually run)

| Check | Result |
|---|---|
| `pytest` (`medscope_test` only) | **222 passed, 0 failed** (202 before + 20 new) |
| `tsc -b` | 0 errors |
| `oxlint` | 0 errors; same warning baseline as before (122 lines); no new warning class in the changed files |
| `vite build` | succeeds |
| `alembic heads` / `check` | `d2b6f8a1c439` single / no new operations |

**Non-destructiveness test** (`test_final_report_content_cannot_be_altered_by_later_changes`, plus `test_stored_range_snapshot_survives_a_range_change` in the Prompt 14 style): after Finalize the result is changed directly in the database and the API refuses a re-save with 409; the snapshot returned is identical; an ORM change to `content_snapshot` or `findings_summary` raises; raw SQL updates of four content columns are refused by the database trigger; a new version of the reference range afterwards leaves the stored range text and value unchanged. Also covered: COMPLETED-is-not-Final, explicit Finalize, all blocked states, doctor-required / both-signature / DOCTOR-login finalization, both culture variants, one-Final-per-order index, result lock after approval, edit conflict, Ready to Issued move, Issued list and snapshot, 403 / 404, placeholder-only notifications.

**Not done:** no browser test, no Playwright, no claim of browser acceptance (owner checklist: `docs/TESTING.md` §19.2).

## 8. Documentation: all nine files, current truth only

| Doc | What changed |
|---|---|
| `README.md` | Counts (112/126, 32 tables, head `d2b6f8a1c439`), current phase and test results replaced with Prompt 16. |
| `project-context.md` | New Prompt 16 section; stale "Module 14 not built / report_versions never created" statements and the "current phase" sentences of earlier prompts corrected. |
| `docs/SCOPE.md` | Module 14 boundary and Ready definition lines corrected; new section 11 (states, who finalizes, blocked states, immutability, signatures, SMS placeholder). |
| `docs/ARCHITECTURE.md` | ADL-070 (Final model, auto-finalize decision, findings of the investigation) and ADL-071 (placeholder SMS, edit conflict); outdated "Module 14 deferred" bullets and counts fixed. |
| `docs/DESIGN.md` | Preview note text and Issued empty state corrected; new section 19 (Finalize area, Final note, View result). |
| `docs/API.md` | Counts, deliverable-list note, new section 11 (endpoints, changed fields, audit actions). |
| `docs/WORKFLOWS.md` | Seed-only statements corrected; Doctor Sign-off steps updated; new section 14. |
| `docs/DATABASE.md` | Head, table count (32 / 31 domain), catalog entries 20 and 31, migration row, new Final Reports section. |
| `docs/TESTING.md` | New section 19 (evidence, owner checklist, known not done); outdated open-item lines corrected. |
