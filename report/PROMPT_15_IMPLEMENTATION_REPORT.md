# Prompt 15 Implementation Report: Doctor Sign-off Screen (Per-Test Approval, D22)

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset. The master context file was not edited. Module 14 (Draft to Final, `report_versions`, QR, SMS) was not started; no reject / send-back path was built.

## 1. What I found first

| Item | Finding |
|---|---|
| Git state | Unchanged in substance since the Prompt 14 report: 2 commits (latest `a6c0243`), the Prompt 10D to 14 work is still uncommitted. Some old prompt/report files show as deleted in the working tree; that was already the case and is not from this prompt. |
| DOCTOR role | **Exists** (sixth role in `ROLES` since Prompt 10E, money-restricted). Default permissions already include `result.complete_doctor_routed`, `worklist.doctor_queue`, `worklist.view`, `worklist.update`, `result.enter`, `profile.manage`. Nothing had to be created. |
| DOCTOR user in `medscope_dcms` | **Yes, one:** `doc` ("Arif Zawad", DOCTOR, active, not deleted). It is **not linked to any doctor profile** (the link did not exist before this prompt), so it cannot approve anything until the owner links it. I did not create or change any user in `medscope_dcms`. |
| DOCTOR user in `medscope_test` | **None** existed. I seeded one, `doctor_rahim` (token in `tests/conftest.py`), linked to a seed Consultant that has a registration number. Test DB only. |
| Doctor profiles | A "doctor profile" is a `referrers` row (name, `registration_no`). Dev DB: 16 referrers, 10 with a registration number and 6 without (the 4 plain "Doctor" rows, one Other, one Agent). Test DB: 10 seed referrers, all with one. |
| Test orders needing approval | `medscope_dcms`: test catalog has 4 `DOCTOR_REQUIRED` and 1 `BOTH_SIGNATURES` tests. Orders: 1 `AWAITING_DOCTOR` (no result yet), 1 `ASSIGNED` both-signature (no result), the rest cancelled/rejected/completed without a result. **No result is waiting for approval right now.** `medscope_test`: 28 AWAITING_DOCTOR + ENTERED and 28 IN_PROGRESS + ENTERED probe orders from earlier tests. |
| Existing approval mechanism | **None.** `approval_rule` was stored on tests and orders but drove nothing. A doctor-routed ENTERED result sets the order to `AWAITING_DOCTOR`; a both-signature ENTERED result leaves it `IN_PROGRESS`; the doctor "completed" through the generic status action with no record. |
| "Assigned to the doctor" | **Did not exist.** There was no link from a DOCTOR login to a doctor profile, and no assigned doctor on a test order (the old doctor queue is shared by all DOCTOR users). Both had to be added to satisfy "DOCTOR sees only their own assigned orders". |
| Alembic head before | `b7e3d91c5a24` (single). |

## 2. Done / Partial / Blocked / Deferred

### Item 1: DOCTOR role/user: **Done**
Role existed, no change to the role. Seed DOCTOR user added in `medscope_test` only. `medscope_dcms`: user `doc` exists, needs to be linked to a doctor profile by the owner (User Management now has a **Doctor profile** select).

### Item 2: approval queue: **Done**
`GET /doctor-approvals/queue` and the **Doctor Sign-off** page. Pending = test rule `DOCTOR_REQUIRED` or `BOTH_SIGNATURES`, result `ENTERED`, no approval, order not cancelled / rejected / spoiled / not performed. DOCTOR sees only orders whose `assigned_doctor_id` is their own profile (the filter cannot widen this); Admin/Owner see all and can filter by doctor, and can **assign** an order to a doctor (new, audited; needed so a DOCTOR login ever has something in its queue). Reuses the Ready Results list look (search, refresh, table); the shared list component does not exist as a reusable piece, so I matched its markup instead of building a new design.

### Item 3: approval action: **Done**
- The review modal shows the saved result read-only using the **same result body** as the report preview (I extracted `ResultPreviewBody` from `ResultReportPreviewModal` so it is one component, not a copy), including the reference range stored at entry (D24 snapshot), the approval rule, the technician's sign-off and the doctor's name and registration number.
- **Path A (Admin/Owner):** doctor search-by-name picker (same `GET /referrers` source), mandatory attestation checkbox ("I confirm Dr. X has reviewed and approved this result, and I am recording the approval on their behalf."), optional notes, Confirm.
- **Path B (DOCTOR):** one Approve action, no picker, no tick; the doctor is always the login's own linked profile (body `doctor_id` / `attestation` are ignored).
- **Record:** new table `doctor_approvals` (`approved_by_user_id`, `doctor_id`, `is_attestation`, `approved_at`, `notes`, plus doctor name and registration snapshots, approval rule, result id). One per test order, append-only.
- **Audit:** same transaction, `DOCTOR_APPROVED_OWN_RESULT` ("Dr. X approved own result, logged in as X") versus `DOCTOR_APPROVAL_RECORDED_BY_STAFF` ("Staff Y (ADMIN) recorded approval on behalf of Dr. X ..."), entity `TEST_ORDER`, actor = who clicked. Verified through the Prompt 11 audit viewer API (action list and filter). A lifecycle event is written too.
- **both-signature:** the technician's sign-off stays on `results.entered_by_id` / `entered_at` (verified unchanged by test); the approval is stored in its own row. Both are one-to-one from the test order (`order.result` and `order.doctor_approval`), and the detail endpoint / review screen show both.
- **Status chosen:** the **existing `COMPLETED`** status. `AWAITING_DOCTOR` (doctor-required) or `IN_PROGRESS` (both-signature) moves to `COMPLETED` through the existing completion step (line lock for no-sample tests included); culture tests stay open until the culture stage is FINAL. No `doctor_approved_at` / `doctor_approved_by_id` columns were added because the status plus the approval row already carry that. Approving also makes the result "Ready" by the shared 10F definition (it was excluded only while `AWAITING_DOCTOR`).
- Also covered: older doctor-routed orders that were completed through the status action before this screen existed (COMPLETED, result ENTERED, no approval) are listed as pending, because they genuinely have no doctor signature; approving them records the row and leaves the status.

### Item 4: permissions: **Done, no new key**
See assumption table. Receptionist, Cashier and Lab Tech get 403 on all four endpoints (tested).

### Partial / Blocked / Deferred
- **Deferred by instruction:** reject / send back; Draft to Final report mechanism (Module 14).
- **Observed, not changed:** a both-signature result is still listed as "Ready" before the doctor signs, because the Prompt 10F Ready definition only excludes `AWAITING_DOCTOR`. I did not touch it (out of scope, and Module 14 decides finalization from the approval record); flagged in SCOPE §10 and TESTING §18.3 for the owner.
- **Owner action:** link `doc` to a doctor profile that has a registration number in `medscope_dcms` (User Management > edit user).

## 3. Assumptions

| Assumption | Choice |
|---|---|
| Attestation wording | "I confirm Dr. X has reviewed and approved this result, and I am recording the approval on their behalf." (Dr. X is replaced by the picked doctor's name.) |
| Target status / flag | Existing `COMPLETED`; no new status, no new flag columns. Reason: `COMPLETED` is the existing "done" state that the Ready definition, the line lock and Module 14 already key on; the `doctor_approvals` row records the approval. |
| Permission key | **No new key.** `result.complete_doctor_routed` (Admin, Owner, Doctor by default; not money) matches the required holders exactly; Receptionist, Cashier and Lab Tech do not hold it. Its label now also says it covers doctor sign-off. The service additionally restricts Path A to ADMIN/OWNER (and Path B to DOCTOR), so a per-user grant to another role cannot be used to attest for a doctor (tested; verified the test fails if the guard is weakened). Counts stay 39 keys / 21 money. |
| "Assigned to them" | New nullable `test_orders.assigned_doctor_id` (FK `referrers`), set by Admin/Owner (or filled from the doctor chosen at approval); a DOCTOR sees only orders assigned to their own profile. Unassigned orders are visible to Admin/Owner only. |
| Doctor identity | A doctor profile is a `referrers` row. New nullable `staff.doctor_profile_id` links a DOCTOR login to it, editable in User Management (DOCTOR users only; cleared when the role changes away from DOCTOR; audited). |
| Doctor must have a registration number | Approval (and assignment) is refused for a doctor without one, since the report must print it. Agent / Clinic / Institution / Other / Third Party referrer types cannot approve. |
| Doctor-required with a still-AWAITING_DOCTOR order and no assignment | Appears for Admin/Owner only. |
| `medscope_dcms` migration | Applied (the app's ORM would otherwise fail on the new columns), after a fresh dump, as in Prompt 14. |
| Table counts in docs | The previous docs said 29 tables (28 domain). A real count from `information_schema` is 31 now (30 domain + `alembic_version`); the old figure was already one short (the Prompt 14 table was not counted). Docs now state 31 / 30. |

## 4. Files changed

Backend: new `app/models/doctor_approval.py`, `app/schemas/doctor_approval.py`, `app/services/doctor_approval_service.py`, `app/api/v1/endpoints/doctor_approvals.py`; edited `app/models/test_order.py`, `app/models/user.py`, `app/models/__init__.py`, `app/api/v1/router.py`, `app/core/permissions.py` (description text only), `app/schemas/user_admin.py`, `app/services/user_admin_service.py`; new migration `alembic/versions/c9a4e7b2d815_prompt15_doctor_approvals.py`.
Frontend: new `features/doctor/DoctorApprovalsPage.tsx`; edited `components/common/ResultReportPreviewModal.tsx` (extracted `ResultPreviewBody`), `features/users/UserManagementPage.tsx`, `components/layout/Sidebar.tsx`, `App.tsx`, `api/client.ts`, `types/index.ts`.
Tests: new `tests/test_prompt15_doctor_signoff.py` (22 tests); `tests/conftest.py` (seed `doctor_rahim`, token, headers, profile link); `tests/fixture_cleanup.py` (`doctor_rahim` is a seed user).
Docs: all nine (section 7). Backup (git-ignored): `backups/medscope_dcms_pre_prompt15.dump`.

## 5. Migration details

| | |
|---|---|
| Revision / `down_revision` | `c9a4e7b2d815` / `b7e3d91c5a24` |
| `alembic heads` before / after | `b7e3d91c5a24` / `c9a4e7b2d815` (single both times) |
| `alembic check` after | "No new upgrade operations detected." (on `medscope_test` and `medscope_dcms`) |
| Autogenerate review | Operations were exactly: create `doctor_approvals` (+ unique `uq_doctor_approvals_test_order_id`, 4 indexes), add `staff.doctor_profile_id`, add `test_orders.assigned_doctor_id` (+ index), two foreign keys. By hand: the two unnamed foreign keys got names (`fk_staff_doctor_profile`, `fk_test_orders_assigned_doctor`) because the generated downgrade (`drop_constraint(None, ...)`) would have failed. Purely additive, no data step needed. |
| `pg_dump` | Taken before applying to `medscope_dcms`: `backups/medscope_dcms_pre_prompt15.dump` (custom format, ~198 KB; confirmed git-ignored with `git check-ignore`). |
| Applied to | `medscope_test` (by the test session) and `medscope_dcms` (head `c9a4e7b2d815`, `doctor_approvals` has 0 rows, no existing row changed). |
| Round trip | `downgrade b7e3d91c5a24` then `upgrade head` on `medscope_test`: both succeed. |

## 6. API path / operation counts

| | Before | After |
|---|---|---|
| Paths | 106 | **110** |
| Operations | 120 | **124** |
| Permission keys / money | 39 / 21 | 39 / 21 (no new key) |

New: `GET /doctor-approvals/queue`, `GET /doctor-approvals/{id}`, `POST /doctor-approvals/{id}/approve`, `POST /doctor-approvals/{id}/assign-doctor`. Existing `POST /users` and `PATCH /users/{id}` gained an optional `doctor_profile_id`.

## 7. Validation results (non-browser, actually run)

| Check | Result |
|---|---|
| `pytest` (`medscope_test` only) | **202 passed, 0 failed** (180 before + 22 new) |
| `tsc -b` | 0 errors |
| `oxlint` | 0 errors; 122 warning lines, the same baseline as Prompt 14; none in the new files |
| `vite build` | succeeds (chunk-size warning only, pre-existing) |
| `alembic heads` | `c9a4e7b2d815` (single) |
| `alembic check` | "No new upgrade operations detected." |

New tests cover: permission matrix and 403 for Receptionist / Cashier / Lab Tech on every endpoint; role guard against a granted key; queue contents (ENTERED + rule + not approved; DRAFT, no result and technician-final excluded; money-free); Admin filter by doctor; DOCTOR scoping and no widening; detail contents; Path A validation (attestation, doctor, registration number, non-doctor type, 404); Path A success (row, status, line lock, audit, leaves queue, no duplicate); Owner path; draft not approvable; both-signature technician sign-off untouched; snapshot survives a profile edit; Path B success and refusal for other doctors' / unassigned orders; same doctor identity on both paths; DOCTOR without a profile; audit viewer lists both actions; user-to-doctor-profile link rules.

**Not done:** no browser test, no Playwright, no claim of browser acceptance (owner checklist: `docs/TESTING.md` §18.2).

## 8. Documentation: all nine files, current truth only

| Doc | What changed |
|---|---|
| `README.md` | Counts (110/124, 17 modules, 31 tables, head `c9a4e7b2d815`), current phase and test results replaced with Prompt 15 (the old Prompt 14 phase line was removed, not kept). |
| `project-context.md` | New Prompt 15 section; the stale "Current phase: Prompt 14" sentence removed; the open-items line no longer lists the sign-off screen as open (now lists the undecided reject path). |
| `docs/SCOPE.md` | Doctor role row, Module 14 exclusion line and the "sign-off screen not built" bullets rewritten to current truth; new section 10 (rules, both paths, not built). |
| `docs/ARCHITECTURE.md` | New ADL-069; stale head/table count in the overview corrected; DOCTOR role decision no longer says "no sign-off screen". |
| `docs/DESIGN.md` | New section 18 (sidebar item, queue page, review modal, User Management doctor-profile select). |
| `docs/API.md` | Counts, permission-table note, new section 10 for the four endpoints, audit actions and the `doctor_profile_id` user fields. |
| `docs/WORKFLOWS.md` | Radiology/doctor line, DOCTOR role line and Ready rule updated; new section 13. |
| `docs/DATABASE.md` | Head, real table count (31/30), migration history row, catalog entries 29 and 30, new Doctor Approvals section. |
| `docs/TESTING.md` | New section 18 (evidence, owner checklist, known not done); the open-items line corrected. |

All historical Prompt 14 sections that are still true (Reference range sections, §16.2/§17.2 acceptance) were left as they are.
