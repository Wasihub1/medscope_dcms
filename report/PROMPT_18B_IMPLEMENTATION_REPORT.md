# Prompt 18B Implementation Report: Fixes from the Module 21/22 Verification

**Date:** 2026-11-14. No browser testing. Nothing committed, pushed, stashed or reset (git unchanged: same 2 commits). Master context file not edited. **No schema change, no migration** (`alembic heads` = `f9a2c4d6e8b1` before and after; `medscope_dcms` was not touched, so no `pg_dump` was needed). The verification suite `tests/test_prompt18_verification.py` **is in the repo and still passes**; I kept it as instructed and made one edit to it (see Finding 4). Please confirm you want it kept.

## Finding 1 (HIGH): money accepted on a closed / reopened day. **Fixed at the root**
- **Cause confirmed:** payment and bill confirmation looked up the OPEN day and treated "none" as "no day tracking", which skipped the closed-day check.
- **Decision:** a cash-affecting action requires an OPEN day. New `accounting_service.require_open_day` is the single lookup: **409** when the latest day is CLOSED or REOPENED, **400** when no day was ever opened. `accounting_service.post` is unchanged. Used by: payment / settle due (`payment_service.py`), bill confirmation incl. finalize (`invoice_service.py`), and **refund payout** (`refund_service.disburse_refund`; same bypass: cash paid out with no day). This is consistent with the existing intent that money belongs to a day.
- **Call sites re-examined:** the only remaining postings with `business_day_id = NULL` are **due write-off and line cancellation**, which move no cash; kept deliberately and documented (ADL-078). A refund *owed* is posted at cancellation (no cash); the cash leaves at disbursement, which now needs a day.
- **Test:** `test_finding1_money_is_refused_on_a_closed_or_reopened_day`: payment on an OPEN day 201; after close, payment and bill confirmation both 409; after reopen, both 409; no payment row with a NULL day.

## Finding 2 (MEDIUM): bank deposit for Admin. **Kept, documented**
No code change. Corrected: `docs/SCOPE.md` §13 Movements bullet (dated 2026-11-14: owner withdrawal Owner only; bank deposit and expense Admin or Owner), `docs/API.md` §13 movements row, `docs/WORKFLOWS.md` §16 step 2. Checked and already consistent / no change: `docs/DESIGN.md` (UI only offers the withdrawal option to Owner), `docs/ARCHITECTURE.md` ADL-077 (states withdrawal Owner only, deposit not restricted), `docs/DATABASE.md`, `docs/TESTING.md` A-3. The existing Prompt 18 tests already assert Admin 201 on a deposit.

## Finding 3 (design gap): new day while REOPENED. **Fixed**
`open_business_day` now refuses (400, same status as the existing OPEN check) when a day is OPEN **or REOPENED**, with a message saying the reopened day must be closed again first. The earlier SCOPE statement that other days could be opened meanwhile was removed. Test: `test_finding3_new_day_blocked_while_open_or_reopened` (open while OPEN 400 unchanged; reopen then open 400; re-close then open 201).

## Finding 4 (observation): adjusting entries and expected cash. **Fixed, no schema change**
`compute_summary` now adds, per channel, the net debit - credit of **adjusting entries** (`is_adjustment`) on that channel's account for the day, as an explicit extra term (`adjusting_entries` in the day screen's `cash`, `adjustments` in each channel line, and a labelled line on the day panel when non-zero). Entries that also touch Cash variance are excluded: they are the count mechanism already handled by the variance logic (so no double counting). The formula stays source-table based, so days that predate the journal still compute correctly; a reversal of a deposit / expense / payment correctly moves expected cash back. Test: `test_finding4_adjusting_cash_entry_flows_into_expected_cash` (a manual Cash credit of 7 lowers expected cash by 7, and counting that figure gives variance 0). One edit to the verification suite: its D45 identity assertion (`test_c1`) now includes the new adjusting-entries term.

## Files changed
Backend: `services/accounting_service.py` (`require_open_day`), `payment_service.py`, `invoice_service.py`, `refund_service.py`, `business_day_service.py`, `day_close_service.py`.
Frontend: `features/business_day/DayClosePanel.tsx`, `types/index.ts` (adjusting-entries line/type).
Tests: new `tests/test_prompt18b_fixes.py` (3 tests); edited `tests/conftest.py`, `test_prompt18_verification.py` (identity term), `test_prompt10e_rooms_roles_worklist.py`.
Docs: SCOPE, API, WORKFLOWS, ARCHITECTURE (ADL-078), TESTING (§22), README, project-context. **No substantive change needed:** DESIGN.md (the panel's extra line is minor and the existing description stays true), DATABASE.md (no schema change).

## Test-suite consequences you should know about
- Requiring an open day made ~20 older tests fail, because they implicitly relied on whatever day state earlier tests left. A `conftest.py` autouse fixture now starts every test with one OPEN day, and puts days an earlier test left REOPENED back to CLOSED (asserts the database is `medscope_test`). The tests of the closed / reopened rules set their own state.
- Two pre-existing worklist tests (`test_prompt10e_rooms_roles_worklist.py`) failed because `medscope_test` has accumulated more than 200 urgent orders, so the 200-row cap hid the new order (same class of problem Prompt 17 hit). They now find the order by bill number.
- The test database was also missing the provisioned technicians `tech_micro` and `tech_usg` (removed at some point, not by this prompt's code); I re-ran the existing `provision_prompt10d_users.py --apply` against **`medscope_test` only** (target printed first). I did not touch `medscope_dcms`.

## Results
| Check | Result |
|---|---|
| `pytest` (`medscope_test` only) | before 18B changes: 248 passed (Prompt 18 report). After: **281 passed, 0 failed** (248 + the verification suite's tests + 3 new) |
| `tsc -b` / `vite build` | 0 errors / succeeds |
| `oxlint` | exit 0 |
| `alembic heads` | `f9a2c4d6e8b1` (single, unchanged); `alembic check` not needed (no model or migration change) |

Docs corrected: SCOPE §13 (three dated clarifications: movements, open-day rule, one active day, adjusting entries), API §13 (movements row, 18B behavior note), WORKFLOWS §16, ARCHITECTURE ADL-078, TESTING §22 and counts, README and project-context counts.
