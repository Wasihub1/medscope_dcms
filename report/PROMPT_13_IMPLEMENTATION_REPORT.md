# Prompt 13 Implementation Report: Pre-Lock Line Cancellation Fix

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset.

## 1. What I found first (before changing anything)

| Item | Finding |
|---|---|
| Git state | Not committed: 2 commits only (`a6c0243` latest), ~150 modified/untracked paths. Prompts 10D to 12 are still uncommitted in the working tree. |
| Alembic | single head `a4d8c2e6f1b7`; baseline `pytest` 141 passed. |
| Did a pre-lock path exist? | **Yes in the backend, partly wired.** `POST /refunds/request` -> `initiate_refund_request` (`request_type` `PRE_SAMPLE_CANCELLATION`, `refund.request`, already in the Receptionist and Cashier defaults) -> approve -> disburse, all in the one D15 pipeline. It was not missing, but: (a) the only UI entry was one invoice-level "Request Pre-Sample Refund" button at the bottom of the detail modal with an "Entire Invoice" option that made the server pick an arbitrary line; (b) the modal had an **editable amount defaulting to the paid total** (the server ignored it, so the modal and the stored result disagreed); (c) a locked line gave a generic 400; a second request gave a generic 400; (d) the generic endpoint silently delegated rejected/spoiled specimens to the D15 handler (a **third path**, which let a front-desk user start D15 without `refund.request_d15`); (e) the client could send `request_type`; (f) approval needed no reason. |
| Duplicate math | `compute_invoice_refund_status` in `invoices.py` duplicated `recompute_invoice_refund_status`. The cancellation arithmetic itself already lived only in `compute_cancellation_outcome`. |
| "Stuck on Awaiting Collection" | Two causes: the sample column rendered only `sample_status` and never looked at the line's cancellation/refund state; and the invoice detail built `{r.invoice_line_id: r for r in newest_first_list}`, which keeps the **oldest** request per line, so a rejected-then-resubmitted line showed a stale status. |

## 2. Done

- **Single calculation:** `compute_cancellation_outcome` now also returns the read-only breakdown (`invoice_total, paid_total, line_price, retained_amount, refund_amount, due_after, net_after`). Used by the preview endpoint, the approval breakdown, the stored request amount and the invoice figures at approval. Editable amount removed; client `amount`/`request_type` are accepted but ignored.
- **Request Cancellation per line** on the invoice detail (`can_request_cancellation` from the server, gated by `refund.request`). Old invoice-level button and "Entire Invoice" option removed.
- **Lock boundary:** one check (`line_lock_blocker`) shared by eligibility, request and approval; request takes a row lock; 409 with `{code, message}` (`SAMPLE_ALREADY_TAKEN`, `REQUEST_PENDING`, `ALREADY_CANCELLED`); "Sample already taken" dialog in the UI. Approval of a pre-lock request whose sample was taken afterwards is refused (409).
- **Third path removed:** the silent D15 delegation and the whole-invoice fallback. Exactly two paths remain: pre-lock (this) and D15 (unchanged).
- **Approval:** reason mandatory for pre-lock requests (400); live breakdown shown beside the request-time snapshot with a "differs" flag (`GET /refunds/requests/{id}/breakdown`).
- **Line states (derived, no column):** `NONE`, `CANCELLATION_REQUESTED`, `CANCELLED_REFUND_PENDING`, `CANCELLED`, `CANCELLED_REFUNDED`; `display_status` makes them win over the sample label; newest request per line now used.
- **Duplicate removed:** `compute_invoice_refund_status` deleted from `invoices.py`; both callers use the pure `derive_invoice_refund_status`.
- **Refresh:** request, approve and disburse call `announceInvoiceChange()`, an alias of the existing Prompt 12 `medscope:sample-changed` event (no second mechanism).
- **Atomic:** request, approval and disbursement each commit once (status, audit, ledger/commission effect together); a forced audit failure on request leaves no row (tested).
- **Docs:** all nine updated (below).

### Worked example (owner case: invoice 9000, paid 3000, cancel the 5000 line)

| | Before (modal) | After (modal = approval view = grid) |
|---|---|---|
| Invoice total / paid / line | not shown | 9000 / 3000 / 5000 |
| Amount retained | not shown | 3000 |
| Refund | defaulted to **3000** (editable; server stored 0) | **0** |
| New net / new due | not shown | 4000 / 1000 |

The "before" row is from reading the code (modal default `inv.paid_amount`, server recomputes), not from a live reproduction.

## 3. Partial / Blocked / Deferred

- **Partial:** one existing test, `test_p04_01_...` (referrer list), **fails**: it calls `GET /referrers` with the default `limit=100` and `medscope_test` now holds 203 referrers, so the new doctor is not on the first page. It passed at the start of this prompt, is unrelated to refunds, and I did not touch it. A fix is to filter by `q` in the test or purge test referrers like the Prompt 12 staff purge.
- **Blocked:** none. **Deferred:** none of the items in "Must NOT do" were touched.
- Frontend behaviour is checked by `tsc`/`vite build` and code review only (no frontend test runner, no browser).

## 4. Assumptions

| Assumption | Choice |
|---|---|
| Reason at request vs approval | Optional at request, mandatory at approval, enforced for pre-lock requests only (D15 approval note stays optional). **Owner to confirm.** The stored request reason is `(no reason given at request)` when blank. |
| Snapshot vs live | Existing pattern kept: amount saved at request is a snapshot, binding amount recomputed at approval; the approval view shows both and flags a difference. |
| Permission key | **Extended, not added:** `refund.request` reused. No new key (39 keys, 21 money). |
| Cashier | Already held `refund.request` through the front-desk set, so Cashier keeps the capability (matches the existing matrix cell). |
| `request_type` | Kept `PRE_SAMPLE_CANCELLATION`; no `PRE_LOCK_CANCELLATION` added (same meaning, avoids a rename across data and docs). |
| Request without a line | Now 400 (previously the server picked an arbitrary eligible line). |

## 5. Migration

None needed. `alembic heads` before and after: `a4d8c2e6f1b7` (single); `alembic current` (dev DB) `a4d8c2e6f1b7`; `alembic check`: "No new upgrade operations detected." `request_type`/`status` are free `String(50)` and the line state is derived. No `pg_dump` taken because no DDL was applied. `medscope_dcms` data was not touched.

## 6. Files changed

Backend: `services/refund_service.py`, `api/v1/endpoints/refunds.py`, `api/v1/endpoints/invoices.py`, `schemas/refund.py`, `schemas/invoice.py`. Frontend: `api/client.ts`, `types/index.ts`, `utils/sampleChangeEvents.ts`, `features/invoices/InvoicesPage.tsx`, `features/refunds/RefundsPage.tsx`. Tests: new `tests/test_prompt13_prelock_cancellation.py` (12 tests); `tests/test_prompt10e_invoice_payment_samples.py` (approve now passes `review_notes`). Docs: below.

## 7. Docs updated

| File | Change |
|---|---|
| `docs/SCOPE.md` | matrix row renamed; §4.3 rewritten; new §8 with the dated owner decision (supersedes the matrix cell for this one capability only) and the two-path boundary |
| `docs/ARCHITECTURE.md` | ADL-058 to ADL-061; ADL-005 line corrected |
| `docs/API.md` | new §8 (endpoints, 409 codes, counts 99 / 113, 39 / 21); header count |
| `docs/WORKFLOWS.md` | new §11 with pre-lock vs D15 diagram and the dialog; table row corrected |
| `docs/DESIGN.md` | new §16 (modal layout, action label, dialog, status badge) |
| `docs/DATABASE.md` | "no schema change" section; head note |
| `docs/TESTING.md` | new §16 (evidence, owner checklist P13-1 to P13-8) |
| `README.md`, `project-context.md` | phase, counts |

## 8. Validation (real results)

| Command | Result |
|---|---|
| `pytest` (`medscope_test`) | **152 passed, 1 failed** of 153 (see Partial) |
| `tsc -b` | 0 errors |
| `oxlint src` | 0 errors, 122 warning lines (README baseline 120; I did not isolate which 2 differ, the warnings in the touched files are pre-existing unused imports/hook deps) |
| `vite build` | succeeds |
| `alembic heads` / `check` | `a4d8c2e6f1b7` / clean |
| OpenAPI | 99 paths / 113 operations (was 97 / 111) |

## 9. Noticed, not fixed

- The referrer-list test flake above (test data accumulates in `medscope_test`).
- `GET /refunds/eligibility` and the new preview return money fields under `refund.view`/`refund.request`; both are money permissions already denied to Lab Tech, so no leak.
- Disbursement runs under `refund.disburse` for Receptionist/Cashier/Admin/Owner as before; nothing about that was changed.
- The Refunds list "Amount" column still shows the request-time snapshot (the live figure is in the approval modal).
