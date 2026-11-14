# Prompt 18B: Fixes from Module 21/22 Verification (Antigravity/Gemini Findings 1–4)

## Context — read first
Inspect the real repository, the real database, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the Prompt 18 report; do not assume the working tree matches it. This is a **targeted fix prompt**, not a new module. It addresses four findings from an independent verification pass (Antigravity/Gemini) run against Prompt 18's accounting/day-close implementation. Do not touch anything outside the four items below.

**Backup rule, repeated because it matters:** before applying any migration to `medscope_dcms`, take the `pg_dump` into `backups/` **first**, then migrate. State the exact command sequence you ran against `medscope_dcms`, in order.

**Scope note — keep it lean, but this time tests matter.** Unlike Prompt 18, these are bug fixes responding to specific verification findings — each fix needs a regression test proving the specific bug is closed, so it can't silently reappear. You do not need to rebuild the kind of exhaustive 30-test suite the verification pass wrote; add only the tests that directly prove each of the four fixes below, plus re-run the full existing suite (Prompt 18's own tests and the verification suite `tests/test_prompt18_verification.py`, if it was kept in the repo — confirm whether the owner wants that file kept; if present, it must still pass).

## Finding 1 — HIGH: closed/reopened-day bypass via `business_day_id = None` [MUST FIX]

**Root cause (per verification report):** `payment_service.py` (`settle_due`) and `invoice_service.py` (`confirm_invoice`) look up the active day as `where(BusinessDay.status == "OPEN")`. When no day is `OPEN` (because it's `CLOSED` or `REOPENED`), this lookup returns `None` — and `None` is treated identically to "there is deliberately no day-tracking for this action," which is exactly the value that skips the closed/reopened-day check inside `accounting_service.post`. The result: payments and bill confirmations taken while the day is closed or reopened succeed silently (201) with `business_day_id = None`, and that money is never attributed to any day's drawer reconciliation, ever.

**Required fix:** the lookup and the downstream check must distinguish two genuinely different cases:
1. **No business day exists in `OPEN` state, and none should be required for this action to be rejected or allowed** — this case should not exist for cash-affecting actions; if the system has no open day at all, cash-affecting actions (payments, bill confirmation with a payment) must be rejected, not silently allowed with no day attribution. Decide (and state in the report) whether bill/payment actions should simply require an open day to proceed at all when they affect cash/drawer accounting — if that's already the intended rule elsewhere in the app, make this consistent with it.
2. **A business day was found but is `CLOSED` or `REOPENED`** — this must raise the existing 409, exactly as it already does for the paths that don't hit this `None`-bypass.
Fix this at the root (the active-day lookup / the call sites in `payment_service.py` and `invoice_service.py`), not by patching `accounting_service.post` to guess at intent from a `None`. Every call site that currently passes `business_day_id=None` to `accounting_service.post` needs to be re-examined — confirm there is no other legitimate reason for `business_day_id` to be `None` on a cash-affecting posting, and if there is, document it explicitly; if there isn't, the lookup itself should raise 409 (closed/reopened) or 400 (no day open at all) before ever reaching `accounting_service.post`.

**Required regression test:** attempt a payment and an invoice confirmation while the day is `CLOSED`, and again while it is `REOPENED`, and confirm both are rejected with 409 (not silently accepted with `business_day_id = None`). Confirm a normal payment on an `OPEN` day still succeeds exactly as before (no regression).

## Finding 2 — MEDIUM: `BANK_DEPOSIT` allowed for Admin [KEEP AS-IS, DOCUMENT]

**Owner's decision:** Admin is allowed to record bank deposits (not Owner-only). This was already the implemented behavior and Claude Code's own test already asserts it — **no code change needed here.**

**Required doc fix:** `docs/SCOPE.md`, `docs/API.md`, `docs/WORKFLOWS.md` (and any other doc that states or implies bank-deposit movements are Owner-only) must be corrected to explicitly state: **owner-withdrawal is Owner-only; bank-deposit and expense movements are Admin or Owner.** Record this as a dated clarification/supersession in `docs/SCOPE.md` per the project's standing rule (current-truth-only, no historical "used to say X" sections — just correct the statement and note the date). Confirm in the report which doc sections were corrected.

## Finding 3 — DESIGN GAP: a new day can be opened while a prior day is still `REOPENED` [MUST FIX]

**Owner's decision:** only one business day may be open (in `OPEN` or `REOPENED` status) per tenant at any time. A new day cannot be opened until the previous day is fully closed (status `CLOSED`) — whether that previous day is still `OPEN` (existing behavior — confirm it already blocks this) or currently `REOPENED` (the gap found by verification — currently not blocked).

**Required fix:** `open_business_day` (`business_day_service.py`) must check for **any** existing day in `OPEN` **or** `REOPENED` status for the tenant, not just `OPEN`, and reject opening a new day (400/409, your call on status code — be consistent with how the existing OPEN-day check already signals this) until that day is re-closed to `CLOSED`.

**Required regression test:** reopen a closed day, then attempt to open a new day — confirm it is rejected. Re-close the reopened day, then attempt to open a new day — confirm it now succeeds. Also confirm the pre-existing "can't open while already OPEN" behavior still works unchanged.

## Finding 4 — OBSERVATION: adjusting entries touching Cash on a reopened day don't flow into expected-cash [FIX IF POSSIBLE, ELSE REPORT ALTERNATIVES]

**Scenario confirmed by verification:** `compute_summary`'s expected-cash figure is computed from source tables (`Payment`, `RefundRequest`, `DayMovement`), not from the journal. When an Owner posts a manual adjusting journal entry on a reopened day that touches the Cash account (e.g. correcting a prior misposting), that adjustment changes the journal's Cash balance but has no effect on the day-screen's expected-cash number — so the Owner's own correction can produce a *new*, confusing variance instead of resolving the one it was meant to fix.

**Investigate and decide:**
- Determine whether `compute_summary`'s expected-cash calculation can be made to also account for adjusting entries that touch a Cash/channel asset account on a reopened day, **without** switching the whole formula over to being journal-derived (which Prompt 18's own design deliberately avoided, so that days predating the journal still compute correctly). A likely approach: when computing expected cash for a day that has one or more adjusting entries posted against it, add each adjusting entry's net effect on the relevant cash/channel account into the expected-cash figure for that day, on top of the existing source-table calculation — treating "adjustments posted during reopen" as a distinct, explicit input to the formula rather than trying to derive everything from the journal.
- **If a correct, scoped fix is possible within this prompt's time/complexity budget:** implement it, and add a regression test: reopen a day, post a manual adjusting entry that credits/debits Cash, recompute expected cash, and confirm the adjustment is now reflected (no artificial variance from the Owner's own correction).
- **If no clean fix is possible without a larger redesign** (e.g. it would require reworking how source-table data and journal data relate more broadly): do not attempt a partial/risky change. Instead, report clearly: (a) why a full fix isn't safe to do within this prompt, (b) a concrete recommended alternative for the owner to choose from — for example: (i) restrict adjusting entries on a reopened day to **non-cash accounts only** (so this divergence can never occur, at the cost of not being able to correct a cash misposting via an adjustment), or (ii) require the Owner to also record a matching cash-count correction via the existing counted-cash mechanism whenever an adjustment touches Cash (a procedural rule rather than a code fix), or (iii) a specific, scoped follow-up prompt that would implement the real fix properly later. State your own recommendation among these (or another you identify) and why.

## Must NOT do
- Do not touch any business logic other than the four findings above.
- Do not start any new module or feature.
- Do not rebuild or remove the existing verification test suite (`tests/test_prompt18_verification.py`) — if present, confirm it still passes; if the owner's workflow expects it removed/relocated, ask in the report rather than guessing.
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not commit, push, stash, or reset anything.
- Do not add a new permission key unless Finding 2's doc correction reveals one is actually missing (it shouldn't — this is a doc fix, not a permission change).

## Schema change requirement (if any)
Findings 1, 3, and 4 are expected to be logic-only fixes (no schema change), but if your chosen fix for Finding 4 genuinely requires a schema change (e.g. a new column to mark which entries are "reopened-day adjustments affecting cash" for the formula to pick up), it requires a correct Alembic migration with a correct `down_revision`, a single head (report `alembic heads` before/after), and the `pg_dump`-before-migrate sequence against `medscope_dcms` stated exactly, in order.

## Required checks (non-browser)
`pytest` (full existing suite including Prompt 18's tests and the verification suite if kept, against `medscope_test` only), `tsc -b`, `oxlint`, `vite build`, `alembic heads` / `alembic check` (only if a migration was needed).

## Documentation requirement
Update the relevant doc sections (at minimum `docs/SCOPE.md`, `docs/API.md`, `docs/WORKFLOWS.md` for Finding 2; `docs/DATABASE.md`/`docs/WORKFLOWS.md` if Finding 3 or 4 changes documented behavior) with current-truth-only content, dated supersession in `docs/SCOPE.md` where a prior statement is being corrected. If a doc has no substantive change, say so explicitly.

## Required report
`report/PROMPT_18B_IMPLEMENTATION_REPORT.md`: for each of the four findings — what was changed (or why Finding 4 couldn't be fully fixed, with your recommended alternative), files changed, the new regression test(s) proving each fix, full pytest results (before/after counts), migration details if any (with the exact `pg_dump`-then-migrate sequence against `medscope_dcms`), and confirmation of which doc sections were corrected.
