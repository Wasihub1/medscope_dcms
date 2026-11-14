# Testing & Verification Prompt: Module 21 (Accounting) + Module 22 (Day Open/Close)

## Who this is for and why
This prompt is for a **different coding agent (Gemini / Antigravity)**, not Claude Code. Claude Code just implemented Module 21/22 in Prompt 18 and, per the project owner's explicit instruction, deliberately wrote only 3 new automated tests (to control token cost) rather than the exhaustive suite earlier prompts had. Your job is to backfill that missing thorough verification. You were not involved in building this feature — investigate it fresh, from the actual code and database, not from assuming the report below is complete or correct.

**Do not do any browser testing.** The project owner does all browser-based acceptance testing himself. Your scope is: read the code, read the schema, write and run automated tests (pytest against `medscope_test` only — never `medscope_dcms`), inspect data directly via SQL where useful, and report findings. Do not open a browser, do not simulate clicks, do not claim UI/UX verification.

**Do not fix anything you find wrong unless it is trivial and obviously safe** (e.g. a typo in a test). For anything that looks like a real bug, a missing validation, or a design gap, **report it clearly** (file, function, reproduction steps, what you expected vs what happened) and leave the fix to a separate implementation pass — do not refactor or "improve" production code as a side effect of testing it.

## Context: what was built (per the implementation report — verify, don't just trust it)
- New tables: `accounts`, `journal_entries`, `journal_lines`, `day_movements`; new columns on `business_days` (counted cash, variance, reopen fields).
- Double-entry journal: append-only (DB triggers refuse UPDATE/DELETE on entries/lines, except re-pointing `created_by_id`), and a deferred constraint trigger refuses an unbalanced entry at commit. Corrections are reversal entries (`reverses_entry_id`, unique — one reversal per entry).
- Real postings wired into: bill confirmation, payment received (initial + due settlement), line cancellation (both immediate and approval paths), refund paid, due write-off, cash variance, bank deposit, owner withdrawal, small expense.
- Explicitly **no postings** for: commission, visit-fee handover, consultant fee, outside-lab cost (Modules 19/20/28 don't exist).
- Four V1 reports: cash book, income-expense, dues (reused from Prompt 17 + date range), cost-by-referrer (cost column always 0). CSV export on each.
- Day close rebuilt: requires `counted_cash`; computes expected cash via the D45 formula **from source tables, not the journal**; per-channel (wallet/bank) expected/variance; reason required above `tenant_settings.cash_variance_tolerance` (default 0); reopen is Owner-only with a reason, after which only adjusting entries (reversal or a balanced manual entry) are accepted — not ordinary postings.
- `business_day.close` permission unchanged (Admin/Owner); one new permission key `accounting.view` (Admin/Owner) for the reports/journal endpoints.
- Known, disclosed gaps: no historical backfill (journal starts at deployment); tolerance default is 0; `POST /business-day/close` body contract changed (now requires `counted_cash`, breaking the old bodyless call).

## What to verify — by area

### A. Journal integrity (highest priority)
1. Confirm every journal entry's lines sum to zero debit minus credit, for every posting path listed above — not just the 3 cases the implementation report's own tests covered. Write tests that create entries via each of the 9 posting paths independently and assert balance.
2. Confirm the DB-level triggers actually reject, not just the service layer: attempt a raw UPDATE and a raw DELETE on `journal_entries` and `journal_lines` directly via SQL (bypassing the service/ORM) in a test against `medscope_test`, and confirm both are refused by the database itself, not merely discouraged by application code.
3. Attempt to commit a deliberately unbalanced entry (construct it to bypass the service's own validation if possible, e.g. by inserting lines directly) and confirm the deferred constraint trigger refuses it at commit.
4. Confirm a reversal entry can only be created once per original entry (the `reverses_entry_id` uniqueness) — attempt a second reversal of the same entry and confirm it is rejected.
5. **Cross-check the "no postings for unbuilt modules" claim directly against data**, not just against the report's prose: for every journal entry in a representative test run, confirm its account references never include a commission/visit-fee/consultant-fee/outside-lab-cost account (the report says no such accounts were even created — confirm that's true, and confirm nothing silently created one later).
6. Specifically probe the divergence risk flagged in review: since expected cash (D45) is computed from source tables (payments/refunds/movements) rather than from the journal itself, construct a scenario with cancellations, refunds, and a write-off together, and confirm the journal's net effect on the Cash account and the day-screen's "expected cash" figure **agree** with each other. If they ever disagree, that's a real finding — report it precisely with the scenario that produces the mismatch.

### B. Real postings — per event, correctness and completeness
For each of the following, write/extend tests that create the real event through its existing service (not by hand-inserting journal rows) and assert the resulting journal entry's accounts and amounts are correct:
1. Bill confirmed — correct split across patient receivable / discount given / test revenue (and urgent-fee revenue if applicable); confirm bill-level vs line-level discount (never both, per the existing business rule) is reflected correctly in the posting.
2. Payment received — both the initial payment at billing and a later due-settlement payment; correct channel account (cash/bKash/Nagad/Rocket/Card/Bank/Other).
3. Line cancelled — test **both** the immediate (no-approval, pre-lock) path and the approval-required path from Prompts 13/13A; confirm the refund-owed amount correctly moves to Refunds payable, and confirm retained/due amounts (per the Prompt 13A owner scenario: invoice 9000, paid 3000, cancel a 5000 line → refund 0 / retained 3000 / due 1000) still match on the accounting side.
4. Refund paid — disbursement reduces Refunds payable and the correct cash/channel account; confirm the Prompt 13B "always separate disbursement" rule (disburse is a distinct, deliberate second action) is still respected and that disbursement, not the refund request itself, is what posts the entry.
5. Due written off — posts to Bad debt, confirm it is **never** mixed with or indistinguishable from a discount-given posting (D11's hard separation rule); test both the Admin-within-limit path and the Owner-approval-above-limit path from Prompt 17.
6. Cash variance, bank deposit, owner withdrawal, small expense — each produces a correctly balanced entry against the Cash variance / Bank / Owner drawings / Operating expense accounts respectively; confirm owner-withdrawal and bank-deposit are Owner-only at the API level (not just hidden in the UI) by calling the endpoint directly with a non-Owner token and confirming 403.
7. Confirm accounts are lazily created (16 seeded per tenant "on first posting," per the report) — test that a fresh tenant with no postings yet still works correctly (accounts get created exactly once, no duplicates) when the first real event occurs.

### C. Day close / reopen / movements
1. **D45 expected-cash identity**: opening cash + cash collections − cash refunds − bank deposits − owner withdrawals − small expenses = expected cash. Construct a full-day scenario with several of each and assert the identity holds exactly (whole-taka integers, per the project's money rule — confirm no fractional-taka drift anywhere).
2. Confirm write-offs do **not** appear anywhere in the expected-cash formula (they are correctly non-cash) — construct a day with a write-off and confirm expected cash is unaffected by it.
3. Per-channel (wallet/bank) expected/counted/variance lines are independent of the cash line and of each other.
4. Variance-reason gating: with tolerance at its default (0), confirm **any** non-zero variance requires a reason and is rejected without one; then set a non-zero tolerance via `tenant_settings` and confirm a variance within tolerance closes without a reason while one exceeding it still requires one.
5. Confirm `business_day.close` permission gating is unchanged — Admin/Owner only, every other role gets 403 on `POST /business-day/close`.
6. Confirm a closed (or reopened) day refuses an ordinary journal-posting-triggering action — e.g. attempt a payment or a movement against a closed day and confirm 409, not a silent success.
7. Reopen: confirm Owner-only (Admin gets 403), reason required, status becomes `REOPENED`, and the original close time is preserved on re-close (per the report's claim) — write a test that opens, closes, reopens, posts an adjusting entry, re-closes, and asserts the original `closed_at` timestamp did not change while a new variance reflecting only the adjustment was recorded.
8. Confirm a reopened day accepts **only** adjusting entries (a reversal of one of that day's own entries, or a balanced manual entry) and rejects an attempt to post an unrelated new ordinary transaction type directly as an "adjustment."
9. Movements (bank deposit / owner withdrawal / expense) — confirm each is blocked from exceeding the day's expected cash (per the report's "never above expected cash" claim) and that the "what-for" reason is actually required (not optional) for an expense.
10. Confirm the breaking change is real and intentional, not accidental: call `POST /business-day/close` with no body and confirm 422 (matching the report); then confirm the one updated pre-existing test (`test_prompt09_auth.py`) now sends the new required body correctly and still exercises what it originally tested (not just patched to pass).

### D. Reports
1. Cash book, income-expense: confirm figures over a flexible date range match a hand-computed expectation from a constructed scenario (not just "doesn't crash") — build a known set of bills/payments/cancellations across 2–3 days and assert exact numbers.
2. Dues report: confirm the date-range addition didn't change the underlying Prompt 17 dues logic (same patient/bill/age-bucket results as before, just filterable by date now) — run the old Prompt 17 dues tests' scenarios again and confirm identical results with no date filter applied.
3. Cost-by-referrer: confirm billing-per-referrer is real/correct while cost is genuinely always 0 (not a hidden nonzero value that happens to round to 0, and not silently omitting referrers with activity).
4. CSV export on each report: confirm the file is valid CSV, opens correctly (UTF-8 BOM present, as claimed, so Excel doesn't mangle it), and the exported figures match the JSON/API response for the same query.
5. Confirm `accounting.view` permission gating: Admin/Owner can reach all five `GET /accounting/...` endpoints, every other role gets 403.

### E. Regression — confirm nothing else broke
1. Re-run the full existing pytest suite (`medscope_test` only — never `medscope_dcms`) and confirm the reported 248-passed baseline still holds on your own machine/session before you add anything.
2. Specifically re-verify the business rules this prompt's postings hook into, to confirm the *hooks* didn't change the *underlying* behavior: pre-lock cancellation (Prompt 13A: refund/retained/due split), disbursement-always-separate (Prompt 13B), write-off limit/approval (Prompt 17), payment flows generally. These should behave exactly as before Prompt 18 — only now with an additional journal side effect.
3. Confirm the `/business-day/state` endpoint (Prompt 13B, money-free, every role) is genuinely unchanged — same shape, same permission-free access, still correctly reflects open/closed/reopened status including the new `REOPENED` state if relevant.
4. Confirm whole-taka-integer money is preserved everywhere new (no cents, no float drift) in the new tables/endpoints.

## Explicit non-goals for this prompt
- No browser testing, no UI/UX acceptance — the owner does this himself.
- Do not build Module 19/20/28 (commission/payouts/outside-lab) — their absence is the correct current state; just confirm nothing fabricates data for them.
- Do not build a backfill for pre-Prompt-18 history — confirm its absence is handled gracefully (reports simply show no activity before deployment, not an error) rather than building the backfill itself; that's an owner decision, not yours to make.
- Do not change the `cash_variance_tolerance` default, the `business_day.close` permission, or any other business rule — you are testing the current implementation as built, not revising it.
- Do not edit the master context file.
- Do not commit, push, stash, or reset anything.

## Required output
A test report (`report/PROMPT_18_VERIFICATION_REPORT.md` or similar) structured as: for each area (A–E) above, what you tested, what passed, and — most importantly — **any finding that is wrong, missing, ambiguous, or inconsistent with the Prompt 18 implementation report's own claims**, each with exact reproduction steps, expected vs. actual, and file/line references. Include the full new test suite you wrote (file paths), and the before/after pytest pass counts. If you find nothing wrong in an area, say so plainly rather than padding the report — a short "tested X scenarios, all passed exactly as claimed" is a complete and sufficient result for that area.
