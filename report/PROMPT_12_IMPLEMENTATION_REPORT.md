# Prompt 12 Implementation Report — Invoice Auto-Refresh, Imaging Lock, Fixture Housekeeping

Date: 2026-11-13. Written for: the project owner (acceptance and decisions).
Nothing committed, pushed, stashed or reset; the 13 tracked-but-deleted files untouched; no browser testing; `medscope_dcms` not connected to or modified.

## 0. What I found before changing anything

| Item | Finding |
|---|---|
| Start state | Alembic head `a4d8c2e6f1b7` (single, dev DB at head). Baseline 135 tests. |
| Invoice refresh | `InvoicesPage` fetched list/detail only on mount and filter change. No React Query, no focus refetch, no polling on that page. |
| Imaging lock code | `record_imaging_performed` set `is_locked` itself; `refund_service` and the invoice detail had imaging-specific cancel blocks for `COMPLETED`/`AWAITING_DOCTOR`/`PERFORMED`. |
| **Premise mismatch 1** | The prompt says no-sample tests "already lock at result completion". They do not: the only lock points were Sample Taken, spoil/reject, and `IMAGING_PERFORMED`. No no-sample test locked at completion. |
| **Premise mismatch 2** | The prompt says the D14 owner same-day unlock "stays". No line-level unlock existed in the code (only account unlock). Docs had no D13/D14 text either. |
| Stock | `trigger_specimen_stock_deduction` is only called from Sample Taken; never wired to imaging. Nothing to move. |
| Stray fixture staff (recount) | 408 fixture rows by role: ADMIN 6, CASHIER 18, DOCTOR 35, LAB_TECH 108 (98 already soft-deleted in Prompt 11), OWNER 20, RECEPTIONIST 179 (366), plus 42 older auth-test users (ids 7–48). 8 named seeds. `tech_micro`/`tech_usg` do not exist in `medscope_test`. |
| Fixture sources | Random-suffix usernames from `test_prompt09_auth.py` (`lockout_`, `locked_victim_`, `pw_change_`), `test_prompt10d` (`_uname`), 10E/10F/11 user-creation helpers. All create through the API and commit. |
| `audit.view` docs | Code and docs agreed (Owner default, Admin grantable); the docs just did not say it plainly. Not a bug. |

## Done

### 1. Invoice auto-refresh
**Root cause:** the Invoices list and detail were fetched only on mount and on filter change, so a Sample Taken done elsewhere was never refetched. The backend was not stale (it recomputes `sample_status` on every request).
**Fix (cache-invalidation style, no polling dependency):** `recordSampleTaken` and `rejectSample` announce a `medscope:sample-changed` window event (`utils/sampleChangeEvents.ts`); `InvoicesPage` refetches the list and the open detail on that event, on window focus (existing `useRefetchOnFocus`), and as a fallback every **30 s only while an invoice detail is open and the tab is visible** (one small GET per 30 s, so no real load). The sample-status mapping, the lock event and who can take a sample are unchanged.
**Test:** the project has no frontend test runner, so this is verified by code review only (stated plainly in `docs/TESTING.md` §15.1).

### 2. Imaging lock at result completion
- **Before:** `imaging-performed` locked the line immediately and routed to `AWAITING_DOCTOR`; cancel was separately blocked for imaging orders in several states.
- **After:** `imaging-performed` no longer locks (event, audit row, order to `AWAITING_DOCTOR`, "PERFORMED" label kept). A new `services/line_lock_service.py` locks the line of any test that does not need a sample when its order becomes `COMPLETED`, from both completion paths (technician-final result save in `result_service`, and `POST /worklist/{id}/status` = COMPLETED). Sample tests still lock at Sample Taken.
- Removed the imaging-specific cancel blocks (`refund_service` eligibility; the `PERFORMED` exclusion in the invoice detail). Before completion an imaging line is an ordinary unlocked line; after, it is locked like any other.
- **D14 unlock (did not exist, built once for all test types):** `POST /invoices/lines/{id}/unlock` with new permission `invoice.line_unlock` (OWNER only), reason required (400), must be locked (409), same business day only (409, `locked_at` not before the open day's `opened_at`), audit `INVOICE_LINE_UNLOCKED` same transaction. Frontend: Owner sees **Unlock (same day)** on a locked line, using the shared ConfirmDialog.
- `IMAGING_PERFORMED` was **kept as a non-locking status label** because the workflow still needs to show that the scan happened before a result exists.
- **Tests (6, `tests/test_prompt12_imaging_lock.py`):** not locked at PERFORMED, locked at completion; pre-completion cancel eligible (before and after PERFORMED), refused after completion; owner unlock identical on imaging and a non-imaging no-sample test (Admin/Receptionist 403, no reason 400, repeat 409, audit row); unlock refused for a lock from an earlier business day; unlock key is Owner-only and `audit.view` default unchanged; fixture-helper guard.

### 3. M11.4 barcode direct open
Nothing implemented (see Deferred).

### 4. One-time stray-fixture cleanup (`medscope_test` only)
Hard delete of 366 + 42 = 408 generated-name staff (pattern `_[0-9a-f]{6,8}$`, never the named seeds), cross-checked against the fixture code listed above. The helper asserts `current_database() == 'medscope_test'` first. References were handled generically: cascade tables deleted, nullable references set NULL, NOT NULL references re-pointed at `owner_tariq`, audit rows about the purged users deleted. Also removed 1,563 orphaned audit rows about staff ids that no longer exist. Result: 8 staff left (the seeds). `medscope_dcms` was neither connected to nor inspected (all scripts use `TEST_DATABASE_URL` and assert the name).

### 5. Fixture teardown (root cause)
**Mechanism chosen: an autouse session-fixture teardown purge** (`tests/fixture_cleanup.py`, called after `yield test_engine` in `conftest.py`). Reason: the tests create users through the API and commit, so a per-test rollback or per-fixture delete would not cover them; `conftest.py` had no per-test transaction pattern to extend. Hard guard untouched; the helper re-asserts the DB name.
Two problems found and fixed while proving it: (a) `conftest.py` reset `staff_id_seq` to `MAX(id)` at session start, which re-used ids after a purge and collided with stale audit rows → changed to `GREATEST(last_value, MAX(id))`; (b) audit rows about purged users are now removed with them.

| Moment | Fixture staff | Total staff |
|---|---|---|
| Before cleanup (recount) | 408 | 456 |
| After one-time cleanup | 0 | 8 |
| After full-suite run 1 | **0** | **8** |
| After full-suite run 2 | **0** | **8** |

Not growing. Other tables (patients, invoices, tests, audit rows) still grow per run; only Staff was in scope.

### 6. `audit.view` documentation
Stated explicitly in `docs/API.md`, `docs/SCOPE.md` and `docs/TESTING.md` (P11-11 is now an explicit PASS condition: "Admin does not see Audit Log by default — this is correct"). No code or default changed. As expected it was a documentation gap, not a bug.

## Assumptions table

| # | Assumption | Notes |
|---|---|---|
| A1 | `IMAGING_PERFORMED` kept as a non-locking status label, not removed. | The UI/workflow still needs "performed". |
| A2 | The completion lock applies to every no-sample test (imaging and explicit no-sample markers), not only imaging. | The prompt said they already did; they did not, so this is the fix it described. Easy to narrow to imaging if you prefer. |
| A3 | D14 unlock did not exist, so I built one generic path with a **new permission key `invoice.line_unlock`** (Owner only, not a money key). | Counts: permissions 38 → 39. I had to update two prior test expectations that listed Owner's exact defaults/total keys (`test_prompt10d` ADMIN∪{…}==OWNER, `test_prompt11` key count 38→39). Behavior assertions unchanged. |
| A4 | "Same business day" = lock happened at or after the currently OPEN business day's `opened_at` (no business day open ⇒ refused). | No day link exists on invoice lines. |
| A5 | Unlock does not touch the order, result or sample status; it only clears the line lock. | |
| A6 | No imaging-specific code for the removed "started, not completed" approval/wastage exception existed beyond the cancel blocks I removed. | |
| A7 | Fixture cleanup mechanism: end-of-session purge. | See §5. |
| A8 | Re-pointing NOT NULL references at `owner_tariq` and deleting audit rows about purged users is acceptable in the disposable test DB. | Never applied to `medscope_dcms`. |

## Deferred
- **M11.4 barcode scan-to-task-open:** deferred to the product-finishing phase **by explicit owner decision** (not blocked, not forgotten). Recorded in `docs/TESTING.md` §15.3 and `docs/SCOPE.md` §7. Nothing implemented or stubbed.

## Partial / Blocked
None. Not run: browser acceptance (owner does it, `docs/TESTING.md` §15.2); no automated frontend test for the auto-refresh (no frontend test runner).

## Migration / head
No schema change. `alembic heads` = `a4d8c2e6f1b7` before and after; `alembic current` (dev DB) same; `alembic check` = "No new upgrade operations detected." Existing `is_locked/locked_at/locked_reason` columns represent the new lock.

## Validation (real results)
| Command | Result |
|---|---|
| `python -m pytest` (`medscope_test`) | **141 passed**, 0 failed, run **twice in a row** (135 + 6 new) |
| `alembic heads` / `current` / `check` | `a4d8c2e6f1b7` / at head / clean |
| `tsc -b` | 0 errors |
| `oxlint` | 0 errors, warnings only (existing style) |
| `vite build` | succeeds |
| OpenAPI | 97 paths / 111 operations (was 96 / 110); 39 permission keys, 21 money (was 38) |

Regression: all Prompt 04–11 tests pass unchanged in behavior (apart from the two key-count/default expectation edits in A3). Two intermediate failures during development (reused staff ids vs. stale audit rows, and my probe tests' "None" sample type tripping an older migration check) were root-caused and fixed rather than loosened.

## Docs updated (all nine plus README/project-context)
ARCHITECTURE (ADL-056 imaging lock, ADL-057 fixture cleanup), SCOPE (§4.10 corrected, new §7 incl. `audit.view` default and M11.4 deferral), API (imaging behavior, `audit.view` default, unlock endpoint, counts 97/111, 39/21), WORKFLOWS (imaging flow corrected, §10 auto-refresh/unlock), DESIGN (§15 locked-note timing, Unlock link), DATABASE ("reviewed, no change" with proof), TESTING (§15 evidence, fixture before/after counts, P11-11 PASS condition, P12 checklist, M11.4 note, line-lock evidence line corrected), README, project-context. Past reports and the master context file untouched.

## Doubtful, noticed but not fixed
1. Test-created patients, invoices, tests and audit rows still accumulate in `medscope_test` on every run (only Staff was in scope).
2. The older docs never described D13/D14 explicitly, so the "old behavior" in the ADL is derived from the code and the SCOPE/API text.
3. A completed imaging order that was completed before this change has no completion lock (it kept its `IMAGING_PERFORMED` lock if it was performed earlier). Existing dev data was not migrated or touched.

## Files changed
Backend: `services/line_lock_service.py` (new), `services/worklist_service.py`, `services/result_service.py`, `services/refund_service.py`, `api/v1/endpoints/invoices.py`, `core/permissions.py`.
Frontend: `utils/sampleChangeEvents.ts` (new), `api/client.ts`, `features/invoices/InvoicesPage.tsx`.
Tests: `tests/test_prompt12_imaging_lock.py` (new), `tests/fixture_cleanup.py` (new), `tests/conftest.py`, `tests/test_prompt10d_roles_permissions.py`, `tests/test_prompt11_soft_delete.py` (count/default expectations only).
Docs: nine docs, README, project-context, this report.
