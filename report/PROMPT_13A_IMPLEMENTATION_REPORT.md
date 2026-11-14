# Prompt 13A Implementation Report: Pre-Lock Cancellation Refinements

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset. `medscope_dcms` data was not touched.

## 1. What I found first

| Item | Finding |
|---|---|
| Git state | Same as the Prompt 13 report: 2 commits only (latest `a6c0243`), 154 modified/untracked paths. The owner has **not** committed Prompts 10D to 13 since. |
| Test failures at start | **1** (`test_p04_01_...`), 152 passed of 153. |
| Referrer rows in `medscope_test` | **203** (193 fixture rows, 10 seed rows ids 1-10). 54 `Partner Agent N`, 54 `Dr. Prescriber N`, 46 `Dr. E2E Test N`, plus `Dr Probe`/`Probe Clinic`/`Dr Audit` hex-suffixed rows from the Prompt 11 tests (the clinics were referenced by test invoices; the Audit doctors were soft-deleted). |
| Premise check | **One detail of the prompt was wrong, and one was imprecise.** (1) The prompt says approval is a separate step to remove; in the code the pre-lock request, approval and disbursement were three calls in one pipeline, so removing approval meant making the cancellation take effect inside the request itself (the review code is still needed for D15). (2) "Restore the whole-invoice action": Prompt 13 had only removed the *UI option* and the server's arbitrary-line fallback; the M29 whole-bill rule had no implementation at all, so this is a new action, not a restore of code. The failing test's cause was exactly as stated (default `limit=100`). |
| Permission keys | `refund.request` and `refund.disburse` are both already in the front-desk set (Receptionist, Cashier, Admin, Owner). Lab Tech and Doctor hold neither. |

## 2. Done / Partial / Blocked / Deferred per item

### Item 1: test flake and referrer purge: **Done**
- `test_p04_01` now filters by a unique term (`?type=Doctor&q=<ts>`) instead of relying on the first 100 rows (no limit bump).
- `purge_fixture_referrers` / `count_fixture_referrers` added to the same `tests/fixture_cleanup.py` and called from the same session teardown as staff (no second mechanism). Name patterns match fixture rows only; invoices pointing at a purged referrer get the column set to NULL, audit rows about them are deleted, and the database name is asserted as `medscope_test` first.
- One-time purge: **193 deleted, 10 remain** (the seed set).
- Full suite run **twice**: 164 passed both times, referrers **10** after each run (no regrowth).

### Item 2: whole-invoice cancel: **Done**
- `cancel_invoice_now` + `GET /refunds/preview-invoice/{id}` + `POST /refunds/cancel-invoice`. Cancels every remaining line together; refused with 409 (and nothing changes) if any remaining line is locked (`SAMPLE_ALREADY_TAKEN`), pending (`REQUEST_PENDING`) or nothing is left (`ALREADY_CANCELLED`). Row locks on all lines.
- Reuses `compute_cancellation_outcome` per line, in id order, each line seeing the refunds of the previous ones (a read-only stand-in invoice for the preview, the real invoice for execution: same function, no second formula). Totals: refund = sum; retained, new due, new total = the last step's.
- UI: **Cancel Whole Invoice** link above the test table (only when every remaining line is cancellable); the shared modal shows per-line refunds and totals.
- Owner case, 9000 invoice (5000 + 4000), 3000 paid: one line (5000): refund 0, retained 3000, due 1000; **whole invoice: refund 3000, retained 0, due 0** (tested).

### Item 3: no approval for pre-lock only: **Done**
- Per-line (`POST /refunds/request`) and whole-invoice cancellations take effect at once through one internal step (`_cancel_line_now`): line `CANCELLED`, test order cancelled with an event, invoice net/due/refund_due/payment status updated, the `RefundRequest` row kept as the record (`APPROVED` when a refund is due, `COMPLETED` when 0), `PRE_LOCK_CANCELLATION` audit row. All in the caller's single transaction.
- "Request and disburse in one flow": an optional `disbursement_method` (+ reference) pays the refund out in the same transaction through the existing `disburse_refund` (original-channel and reference rules unchanged). A rejected payout rolls the cancellation back (tested). Without a channel the refund stays "refund pending payout" and anyone with `refund.disburse` pays it later.
- **Not touched:** D15 (still `PENDING_ADMIN_APPROVAL`, tested that nothing is cancelled until approved and that Receptionist gets 403), imaging-started cancellation, owner same-day unlock. `admin_review_refund_request` is unchanged so any request left pending by the Prompt 13 flow can still be resolved; the API can no longer create one.
- Matrix change recorded as a dated supersession in `docs/SCOPE.md` §9 with the owner's reasoning; master context file not edited.

## 3. Assumptions

| Assumption | Choice |
|---|---|
| Whole-invoice scope of "no line locked" | Only the **remaining (not cancelled)** lines are checked. A line already cancelled through D15 (necessarily locked) does not block cancelling what is left. If you want any locked line, even a cancelled one, to block it, say so. |
| Whole-invoice refund order | Per-line in id order with each line seeing earlier refunds; the total refund is independent of order (it works out to paid minus the urgent-fee floor when everything is cancelled). |
| Payout in the same flow | **Optional**, not mandatory: no channel means "cancelled, refund awaiting payout" (so a missing reference never blocks cancelling). The UI always offers the channel when a refund is due. |
| Payout permission | Cancelling needs `refund.request`; paying out inside the call also needs `refund.disburse` (403 otherwise). Defaults give both to all four roles, so this only matters for per-user overrides (no automated test for that case). |
| Approval metadata | Auto-effective rows keep `reviewed_by_id` NULL with `review_notes` = "No approval step: pre-lock cancellation ...". Requester stored as `requested_by_id`. |
| Reason | Optional (blank stored as "(no reason given)"). The Prompt 13 "mandatory at approval" assumption disappears for pre-lock (no approval); it remains for any old pending request. |
| Endpoint names | Kept `POST /refunds/request` for the line (summary text changed; behaviour changed from "request" to "cancel now"). Added `preview-invoice` and `cancel-invoice`. |
| Button wording | "Cancel Test" / "Cancel Whole Invoice" replace "Request Cancellation" because there is no longer a request. |

## 4. Files changed

Backend: `services/refund_service.py`, `api/v1/endpoints/refunds.py`, `schemas/refund.py`. Frontend: `api/client.ts`, `types/index.ts`, `features/invoices/InvoicesPage.tsx`, `features/refunds/RefundsPage.tsx` (intro text only). Tests: `fixture_cleanup.py`, `conftest.py` (teardown call), new `test_prompt13a_whole_invoice_no_approval.py` (12 tests), rewritten `test_prompt13_prelock_cancellation.py` (11 tests), and expectation updates in `test_prompt04_corrections.py` (p04_01 filter, p04_05 lifecycle), `test_prompt10d_refunds.py`, `test_prompt10e_invoice_payment_samples.py`, `test_receptionist_e2e.py` (no approval step any more). Docs: all nine (below).

## 5. Migration / head status

None. `alembic heads` = `a4d8c2e6f1b7` (single), `alembic current` = `a4d8c2e6f1b7`, `alembic check` = "No new upgrade operations detected." Only the status a pre-lock row is created with changed (free `String(50)` column). No `pg_dump` taken because no DDL was applied.

## 6. Permission-key decision

**No new key.** `refund.request` covers the action and `refund.disburse` covers the in-flow payout; both are already held by Receptionist, Cashier, Admin and Owner and by no other role. `refund.approve` and `refund.request_d15` are untouched because D15 keeps its approval. The permission module still shows 39 keys, 21 money. The `refund.request` description text ("Request pre-sample refunds") is now a little dated; I left it unchanged because it is a public label (rename was not requested).

## 7. API counts

| | Before | After |
|---|---|---|
| Paths | 99 | **101** |
| Operations | 113 | **115** |
| Permission keys / money | 39 / 21 | 39 / 21 |

## 8. Docs updated (all nine)

| File | Change |
|---|---|
| `docs/SCOPE.md` | matrix rows (cancel without approval; approve row scoped to D15/pending), §4.3 pre-lock bullet rewritten, new §9 with the dated owner decision and reasoning (supersedes the approval part of §8 only) |
| `docs/ARCHITECTURE.md` | ADL-005 line, new ADL-062 (no approval), ADL-063 (whole invoice), ADL-064 (referrer purge) |
| `docs/API.md` | new §9, header count 101 / 115 |
| `docs/WORKFLOWS.md` | note on §11, new §12 with the flow and owner worked case |
| `docs/DESIGN.md` | new §17 (Cancel Test / Cancel Whole Invoice modal) |
| `docs/DATABASE.md` | "no schema change" section |
| `docs/TESTING.md` | new §17 with evidence and checklist P13A-1 to P13A-8 |
| `README.md`, `project-context.md` | phase, counts, summary |

## 9. Validation (real results)

| Command | Result |
|---|---|
| `pytest` (`medscope_test`, guard unchanged), run twice | **164 passed, 0 failed** (both runs); referrer rows 10 after each |
| `tsc -b` | 0 errors |
| `oxlint src` | 0 errors, 122 warning lines (same count as after Prompt 13) |
| `vite build` | succeeds |
| `alembic heads` / `current` / `check` | `a4d8c2e6f1b7` / `a4d8c2e6f1b7` / clean |
| OpenAPI | 101 paths / 115 operations |

## 10. Noticed, not fixed

- Test-suite note: in the first full run after the change one old test (`test_p04_05`) failed because it expected the pending status; updated, not a product bug.
- Behaviour that changed on purpose and that older docs or reports may still describe: pre-lock refund requests no longer appear in the Refunds page as "Pending"; they show as Approved/Disbursed/Completed. Past reports were not edited.
- The Refunds list "Amount" column still shows the stored amount (the figure fixed at cancellation); correct now, since nothing waits for approval.
- The role-permission screen text for `refund.request` ("Request pre-sample refunds") is slightly stale (see §6).
- Frontend behaviour is checked by `tsc`/`vite build` and code review only (no frontend test runner, no browser).
