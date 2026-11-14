# Prompt 13A: Pre-Lock Cancellation Refinements (Whole-Invoice Path + No-Approval, Pre-Lock Only)

## Context — read first
Inspect the real repository and all nine canonical docs before changing anything. Re-check `git status` / `git log` — do not assume the working tree matches `PROMPT_13_IMPLEMENTATION_REPORT.md`; the owner may have committed since. This prompt is a direct, narrow follow-up to Prompt 13 (same area: pre-lock line cancellation, M29 of the master scope). It does **not** touch D15, imaging-started cancellation, owner same-day unlock, payment reversal, or write-off — those keep their existing approval requirements exactly as-is.

Three owner decisions, made explicitly in chat on 2026-11-14, to implement:

## Item 1 — Fix the pre-existing test flake and purge accumulated test referrer rows
- `tests/test_p04_01_...` (referrer list test) currently fails: it calls `GET /referrers` with the default `limit=100`, and `medscope_test` now holds 203+ referrer rows (test-data accumulation, same pattern as the Staff-row issue resolved in Prompt 12), so a newly-created referrer in the test isn't on the first page.
- Fix the test itself (filter by a distinguishing query param, or otherwise make it independent of total referrer count) — do not just raise the limit as a band-aid.
- Purge the accumulated referrer rows in `medscope_test` down to whatever seed set is appropriate, following the exact pattern already built in `tests/fixture_cleanup.py` for Staff rows in Prompt 12 (extend that same teardown mechanism to cover referrers, rather than building a second one).
- Prove no regrowth by running the full suite twice, same as Prompt 12 did for Staff.
- `medscope_dcms` (the owner's main dev DB) must not be touched by this cleanup — test-only, as always.

## Item 2 — Restore a whole-invoice cancel/refund action (distinct from the one removed in Prompt 13)
Prompt 13 removed an *ambiguous* invoice-level "Entire Invoice" option that silently let the server pick an arbitrary single line while labeling it as covering the whole invoice. The owner wants a *different, explicit* whole-invoice action restored:
- Available only when **no line on the invoice is locked** (sample not taken on any line) — matches the existing M29 rule "Whole bill cancelled: only if no line locked."
- When used, it must explicitly cancel **every unlocked line on the invoice together** — not pick one arbitrarily, not partial. If any line is locked, block the whole action (409, clear message) rather than cancelling only the unlocked subset.
- Reuse the same single calculation path (`compute_cancellation_outcome`) per line and sum the breakdown (total refund, total retained, new due) across all lines for the confirmation view — do not write a second calculation function.
- This whole-invoice action is covered by Item 3's no-approval rule below (it is still pre-lock cancellation, just scoped to the whole invoice instead of one line).

## Item 3 — Remove the approval step for pre-lock cancellation ONLY
- For pre-lock cancellation (both the per-line path from Prompt 13 and the whole-invoice path from Item 2 above): remove the separate approval step entirely. Receptionist, Cashier, Admin and Owner can each request **and** disburse in one flow, with no Admin/Owner sign-off required in between, because no money or stock has been consumed yet (sample not taken) — this is the owner's explicit reasoning, record it in the docs as such.
- This change applies **nowhere else**. D15 (post-lock, Not Performed), imaging-started-not-completed cancellation, and owner same-day unlock must keep requiring approval exactly as they do today. Do not touch those code paths, tests, or permission checks.
- Permission matrix change: the "Cancel/amend unlocked line" cell changes from Receptionist/Cashier = Request, Admin/Owner = Approve, to Receptionist/Cashier/Admin/Owner = Yes (request + disburse, no approval gate), for the pre-lock case only. Record this as a dated supersession in `docs/SCOPE.md` — **never edit the master context file.**
- Check whether `refund.request_d15`-style separation needs any adjustment given approval is gone for this one path — if the existing permission key structure needs no new key (likely, per Prompt 13's precedent of reusing `refund.request`), say so explicitly in the report rather than silently adding one.

## Must NOT do
- Do not touch D15 (post-lock Not Performed), imaging-started cancellation, or owner same-day unlock — approval stays required on all three.
- Do not edit the master context file under any circumstance.
- Do not start Module 14 or any other new module.
- Do not do any browser testing (Playwright/Selenium/etc.) or claim browser acceptance — that is the owner's job.
- Do not weaken the `pytest`-against-`medscope_test`-only guard.
- Do not touch `medscope_dcms` data.
- Do not commit, push, stash, or reset anything — the owner handles git himself.
- Do not print or repeat any password or connection string.
- Do not add a new permission key unless Item 3's analysis genuinely requires one — prefer reusing the existing key structure.

## Required checks (non-browser)
`pytest` (against `medscope_test` only, run twice after the referrer-fixture cleanup to prove no regrowth), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`. Report exact, real results — no claimed results that weren't actually observed. If a schema change turns out to be needed (not expected — this is permission/logic/test-cleanup, not a new column), it needs a correct Alembic migration with a single head, and a fresh `pg_dump` into `backups/` before applying anything to `medscope_dcms`.

## Required report
`report/PROMPT_13A_IMPLEMENTATION_REPORT.md` with: what you found first (git state, current test failure count, current referrer row count, whether anything in the stated premise above turns out to be wrong once you inspect the actual code — if so, say so plainly rather than building on a false assumption); Done / Partial / Blocked / Deferred per item; an Assumptions table; files changed; migration/head status; permission-key decision and reasoning; API path/operation counts before and after; actual validation command results. Update all nine canonical docs (README, project-context, SCOPE, ARCHITECTURE, DESIGN, API, WORKFLOWS, DATABASE, TESTING) — if a doc has no substantive change, say so explicitly rather than skipping it silently.
