# Prompt 13B Implementation Report: Separate Disbursement + Business Day Status

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset. `medscope_dcms` data not touched. The two items are reported separately below.

**Git state (re-checked):** unchanged since the 13A report: 2 commits (latest `a6c0243`), working tree ~155 modified/untracked paths; Prompts 10D to 13A are still uncommitted.

---

## ITEM 1: Disbursement is always a separate action

### What I found first
13A had `disbursement_method` / `disbursement_reference` on both cancel schemas and a `_maybe_disburse` step that called `disburse_refund` inside the cancel transaction; the cancel modal had a channel select and reference field. The "no channel given" post-state (refund row `APPROVED`) already existed, so removal meant deleting the combined path, not building a new one.

### Done
- Removed both fields from `RefundRequestCreate` and `InvoiceCancellationCreate`; deleted `_maybe_disburse` and the `actor_permissions` / `disbursement_*` parameters from `initiate_refund_request` and `cancel_invoice_now`; endpoints no longer pass them. A stray field in a body is ignored by the schema, so nothing is paid out (tested).
- Cancellation always ends with the refund row `APPROVED` (refund due) or `COMPLETED` (0). Still no approval step (13A unchanged). `disburse_refund` untouched.
- Frontend: channel and reference fields and their state removed from the cancel modal; when a refund is due it shows a note that cancelling pays nothing. After a successful cancel the toast says the refund is pending payout. A banner on the invoice detail, "Refund of ৳X is pending payout [Disburse now]" (shown with `refund.disburse`), opens the **existing** Disburse modal: a separate second click with its own amount/channel display, never pre-submitted. API client and types trimmed to match.
- D15, imaging-started cancellation and owner same-day unlock untouched.

### Partial / Blocked / Deferred
None.

### Files changed (Item 1)
Backend: `services/refund_service.py`, `api/v1/endpoints/refunds.py`, `schemas/refund.py`. Frontend: `api/client.ts`, `features/invoices/InvoicesPage.tsx`. Tests: `tests/test_prompt13a_whole_invoice_no_approval.py` (two tests rewritten, one new).

### Test evidence (Item 1)
Whole-invoice cancel leaves rows `APPROVED`/`COMPLETED` with refund_due 3000, then a separate `POST /refunds/disburse/{id}` pays out; a channel/reference sent in either cancel body is ignored (status `APPROVED`, `disbursed_at` empty, fields absent from both schemas). The 13A lifecycle tests that already used the separate disburse call stay green.

---

## ITEM 2: Business Day status differs per role

### What I found first (actual root cause)
**Not any of the listed candidates exactly.** The status itself was always right. The header (`Header.tsx`) shows "Business Day Closed" whenever `businessDay` in the auth context is null, and `AuthContext` only fetched the day `if (permissions.includes('business_day.view'))`. **Lab Tech does not hold `business_day.view`** (and must not: `/business-day/status` returns cash, float and channel balances). So for Lab Tech the value was never fetched, stayed null, and the header defaulted to "Closed" while the day was open. (A related latent bug found on the way: when the full status *was* fetched for money roles but the day was closed, the response object was still truthy, so the header would have shown "Day #undefined Open".)

### Done
- New money-free `GET /business-day/state` returning only `{is_open, day_number, business_date}` from the same query as the full status; requires only an authenticated session (`get_current_actor`), no permission key. The full `/status` and `/current` keep `business_day.view` and their money figures (still 403 for Lab Tech).
- `AuthContext` calls it for every role and maps closed to null; the header therefore reads the same fact for everyone and no longer misrenders a closed day.
- Header markup unchanged.

### Partial / Blocked / Deferred
None.

### Files changed (Item 2)
Backend: `schemas/business_day.py`, `services/business_day_service.py`, `api/v1/endpoints/business_day.py`. Frontend: `types/index.ts`, `api/client.ts`, `context/AuthContext.tsx`. Tests: new `tests/test_prompt13b_business_day_state.py` (4 tests).

### Test evidence (Item 2)
Open day: Receptionist, Cashier, Admin, Owner and Lab Tech read identical `is_open`/`day_number`/`business_date`, and it matches the full status's day number. Closed day (forced in `medscope_test`, restored in `finally`): all five read closed. Lab Tech's body keys are exactly the three fields with no money-like key; `/business-day/status` and `/current` still 403 for Lab Tech; no/invalid token gives 401.

---

## Shared

### Schema / migration
None for either item. `alembic heads` = `a4d8c2e6f1b7` (single), `alembic check` = "No new upgrade operations detected." No `pg_dump` (no DDL).

### Permission keys
**No new key for either item.** Item 1 removes behaviour (`refund.request` / `refund.disburse` unchanged). Item 2 uses the authenticated-session dependency only; granting Lab Tech `business_day.view` would have leaked money, so it was not done.

### API counts
| | Before (13A) | After |
|---|---|---|
| Paths | 101 | **102** |
| Operations | 115 | **116** |
| Permission keys / money | 39 / 21 | 39 / 21 |

### Validation (real results)
| Command | Result |
|---|---|
| `pytest` (`medscope_test`) | **168 passed, 0 failed**; referrer rows 10 after |
| `tsc -b` | 0 errors |
| `oxlint src` | 0 errors, 122 warning lines (my first pass added one unused-parameter warning; fixed, back to baseline) |
| `vite build` | succeeds |
| `alembic heads` / `check` | `a4d8c2e6f1b7` / clean |

### Docs (all nine)
| File | Change |
|---|---|
| `docs/SCOPE.md` | §4.3 and §9: combined payout removed (same supersession, owner reasoning), Business Day status fix noted |
| `docs/ARCHITECTURE.md` | ADL-062 marked superseded for payout; new ADL-065 (separate disbursement), ADL-066 (business day state, root cause) |
| `docs/API.md` | header count, new §10 (schema removal, new endpoint) |
| `docs/WORKFLOWS.md` | note on §11/§12, new §13 (cancel then disburse, business-day indicator) |
| `docs/DESIGN.md` | new §18 (modal change, banner placement, header badge) |
| `docs/DATABASE.md` | "no schema change" section |
| `docs/TESTING.md` | new §18 with evidence and checklist P13B-1 to P13B-7 |
| `README.md`, `project-context.md` | phase, counts, summary |

Older 13A sections that describe an in-flow payout (SCOPE/API §9 table row, TESTING §17 checklist P13A-4/P13A-6, DESIGN §17) were left as historical records; the 13B sections above supersede them and the SCOPE/ARCHITECTURE sentences that stated the combined path as current were edited in place.

### Assumptions
| Assumption | Choice |
|---|---|
| "Disburse now" placement | A banner on the invoice detail opening the existing Disburse modal (second click), plus the existing Refund Lifecycle and Refunds page buttons. Not a new screen. |
| Whole invoice with several refund rows | The banner pays them one at a time (the existing modal is per request). |
| Banner visibility | Only with `refund.disburse`; it also appears for any older `APPROVED` refund with an amount, not just right after a cancel. |
| Closed-day mapping | State endpoint always answers 200; the client maps `is_open: false` to null. |
| State endpoint access | Any authenticated tenant user (no permission key), because it carries no financial data. |

### Noticed, not fixed
- Older 13A text in SCOPE §9 history, API §9 and DESIGN §17 still mentions the removed in-flow payout; it is labelled superseded rather than rewritten (see Docs).
- `BusinessDayPage` still uses the full `/status` for its own content; unchanged (Lab Tech cannot open it).
- Frontend behaviour is checked by `tsc`/`vite build` and code review only (no frontend test runner, no browser).
