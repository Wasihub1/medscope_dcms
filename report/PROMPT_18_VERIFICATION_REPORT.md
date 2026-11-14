# Verification Report: Module 21 (Accounting) + Module 22 (Day Open/Close)

**Date:** 2026-11-14  
**Evaluator:** Antigravity / Gemini Agent (Independent Verification)  
**Target Environment:** Isolated PostgreSQL database `medscope_test` (Strict conftest guard; zero mutations on `medscope_dcms`)  
**Scope Covered:** Automated code, schema, and API verification of Module 21 (Double-Entry Journal & Reports) and Module 22 (Day Open/Close, Movements, Reopen). Zero browser testing performed (per explicit project owner instructions).  
**Master Context Status:** Untouched (per non-goals).  
**Repository State:** No commits, pushes, stashes, or resets performed.  

---

## 1. Executive Summary

| Metric | Result |
|---|---|
| **Baseline Tests (Pre-Verification)** | 248 passed, 0 failed |
| **New Verification Suite** | `tests/test_prompt18_verification.py` (30 new tests) |
| **New Verification Pass Count** | **30 passed, 0 failed (100% pass rate)** |
| **Overall Pytest Suite** | 278 collected (276 passed, 2 pre-existing worklist tests failed due to DB pagination limit) |
| **Database Triggers & Constraints** | 100% verified (Append-only triggers on entries/lines; deferred constraint balance trigger; reversal uniqueness) |
| **Unbuilt Modules Postings** | 100% verified (0 accounts and 0 postings for commission, visit-fee, consultant, or outside lab) |
| **Integer / Whole-Taka Money** | 100% verified (Zero cents, zero float drift across all new tables and columns) |
| **Critical Findings Identified** | **4 Findings** (1 High severity, 1 Medium severity, 2 Design/Ambiguity observations) |

---

## 2. Area-by-Area Verification Results

### Area A: Journal Integrity (Highest Priority)
- **A.1 All Posting Paths Balance (Dr == Cr):** Verified across all 14 posting paths (Bill confirmation, Initial payment, Due settlement, Immediate cancellation, Approval cancellation, Refund disbursement, Admin write-off, Owner write-off, Bank deposit, Owner withdrawal, Expense, Cash variance shortage/overage, Reversal, Manual adjustment). A database-wide query `SELECT entry_id FROM journal_lines GROUP BY entry_id HAVING SUM(debit) <> SUM(credit)` returned 0 unbalanced entries.
- **A.2 Database-Level Triggers (Append-Only):** Verified via direct raw SQL execution (bypassing ORM/FastAPI):
  - `UPDATE journal_lines` -> Raised `DBAPIError: journal rows are append-only: UPDATE on journal_lines is not allowed`.
  - `DELETE FROM journal_lines` -> Raised `DBAPIError: journal rows are append-only: DELETE on journal_lines is not allowed`.
  - `UPDATE journal_entries SET memo = ...` -> Raised `DBAPIError: journal rows are append-only: UPDATE on journal_entries is not allowed`.
  - `DELETE FROM journal_entries` -> Raised `DBAPIError: journal rows are append-only: DELETE on journal_entries is not allowed`.
  - `UPDATE journal_entries SET created_by_id = ...` -> Successfully allowed (verifying the migration's intended exception for test fixture cleanup).
- **A.3 Deferred Constraint Balance Trigger:** Attempted to commit a deliberately unbalanced entry via direct SQL `INSERT INTO journal_lines`. At commit, the transaction was refused by PostgreSQL trigger `trg_journal_entry_balanced` (`journal entry X does not balance: debit 999 <> credit 0`).
- **A.4 Reversal Entry Uniqueness:** Verified that creating a second reversal for the same entry is refused both at the application service layer (HTTP 409 Conflict) and at the database schema level (`uq_journal_entry_reverses` unique constraint violation).
- **A.5 Unbuilt Modules Verification:** Directly audited `accounts` and `journal_entries` in the database. Confirmed zero accounts and zero journal events exist for Commission, Visit-fee Handover, Consultant Fees, or Outside Lab Costs.
- **A.6 Expected Cash vs. Journal Cash Divergence Probe:** In an active business day, the journal's net effect on `Cash in hand` (code 1010) matches the day-screen's `expected_cash` formula exactly. However, edge-case divergence was confirmed when payments occur outside an open day or when adjusting entries touch Cash on a reopened day (*see Finding 1 & Finding 4*).

### Area B: Real Postings (Per-Event Correctness & Completeness)
- **B.1 Bill Confirmed:** Verified line split: `Dr Patient receivable (net) + Dr Discount given (discount) == Cr Test revenue (gross) + Cr Urgent fee revenue (urgent_fee)`. Bill-level discount and line-level discount invariance verified.
- **B.2 Payment Received (All Channels):** Verified channel asset accounts mapping: `CASH (1010)`, `BKASH (1020)`, `NAGAD (1030)`, `ROCKET (1040)`, `POS_CARD (1050)`, `BANK_TRANSFER (1060)`. All channels debit their specific asset account and credit `Patient receivable (1200)`.
- **B.3 Line Cancelled:** Verified Prompt 13A owner scenario (Invoice 9000, advance paid 3000, 5000 line cancelled):
  - Invoice net becomes 4000, retained 3000, refund 0, due 1000.
  - Journal entry posts: `Dr Test revenue 5000, Cr Patient receivable 5000`. Net receivable drops to 1000, matching invoice due.
  - Full refund cancellation (Invoice 5000, paid 5000, cancel 5000 line): `Dr Test revenue 5000, Dr Patient receivable 5000, Cr Refunds payable 5000`. Refund owed properly recorded in liability account 2100.
- **B.4 Refund Paid (Disbursement Separation):** Verified that submitting a refund cancellation request does *not* post to the journal or move cash. Posting occurs strictly upon deliberate disbursement by Cashier/Admin: `Dr Refunds payable (2100), Cr Channel Asset`.
- **B.5 Due Written Off (Hard Separation from Discount):** Verified write-off posts: `Dr Bad debt (5100), Cr Patient receivable (1200)`. D11 invariant verified: write-off is never mixed with discount (code 4900 is untouched).
- **B.6 Day Movements & RBAC:** Verified `BANK_DEPOSIT` (`Dr Bank, Cr Cash`), `OWNER_WITHDRAWAL` (`Dr Owner drawings, Cr Cash`), and `EXPENSE` (`Dr Operating expense, Cr Cash`).
  - Receptionist & Cashier: 403 on all movements.
  - Owner: 201 on all movements.
  - Admin: 403 on `OWNER_WITHDRAWAL`, 201 on `EXPENSE`.
  - *Discrepancy observed on Admin Bank Deposit (see Finding 2)*.
- **B.7 Lazy Account Creation:** Tested on a fresh tenant. Exactly 16 chart accounts seeded on first posting; subsequent calls are idempotent (0 duplicate accounts).

### Area C: Day Close / Reopen / Movements
- **C.1 D45 Expected Cash Identity:** Verified formula: `expected_cash == opening_cash + cash_collections - cash_refunds - bank_deposits - owner_withdrawals - expenses`. Integer whole-taka math verified.
- **C.2 Write-Offs Non-Cash:** Verified due write-offs have zero effect on day-screen expected cash.
- **C.3 Per-Channel Independence:** Non-cash collections (e.g. bKash) and cash movements (expenses, drawings) update only their respective channel lines.
- **C.4 Variance Reason Gating & Tolerance:**
  - Tolerance = 0 (default): Any non-zero variance requires a reason (HTTP 400 without, HTTP 200 with).
  - Tolerance = 20: Variance of 15 closes without reason; variance of 25 requires reason.
- **C.5 `business_day.close` Permission:** Admin and Owner succeed (200); Receptionist, Cashier, Lab Tech rejected with HTTP 403.
- **C.6 Closed / Reopened Day Protection:**
  - Day movements against a closed or reopened day return HTTP 409 Conflict.
  - Direct calls to `accounting_service.post` targeting a closed day return HTTP 409 Conflict.
  - *Bypass observed on API invoice billing and payment settlement (see Finding 1)*.
- **C.7 Reopen Behavior:**
  - Reopen is Owner-only (Admin gets 403).
  - Reason required (HTTP 400 on empty reason). Status becomes `REOPENED`.
  - Re-closing preserves the original `closed_at` timestamp.
- **C.8 Reopened Day Adjustments:**
  - Reopened day accepts only adjusting entries (reversals or balanced manual adjustments). Ordinary movements return 409.
  - Unbalanced adjustments return 400; double-reversals return 409.
  - *Multiple open days behavior observed (see Finding 3)*.
- **C.9 Movement Drawer Limit & Expense Note:**
  - Movements exceeding expected drawer cash return HTTP 400 (`Only Tk X of cash should be in the drawer; Tk Y cannot be taken out`).
  - Expense without note returns HTTP 400.
- **C.10 Breaking Contract Change:** Calling `POST /business-day/close` with an empty body returns HTTP 422 (`counted_cash` field required).

### Area D: Reports & CSV Exports
- **D.1 Cash Book & Income-Expense Reports:**
  - Cash book computes opening balance, running balance, total in, total out, and closing balance across date filters.
  - Income-expense computes daily revenue, urgent fees, discount given, operating expenses, bad debt, cash variance, income, expense, and net on a billing basis.
- **D.2 Dues Report:** Date-range filtering verified while preserving Prompt 17 calculations.
- **D.3 Cost-by-Referrer:** Billing per referrer is real and accurate; cost is genuinely 0 with explicit note explaining Module 19 commission is not built.
- **D.4 CSV Export & UTF-8 BOM:** Verified on all 4 accounting reports (`format=csv`). Content-Type is `text/csv; charset=utf-8`. Files begin with UTF-8 BOM (`\ufeff`) for Excel compatibility and parse cleanly.
- **D.5 `accounting.view` RBAC:** Admin and Owner access all 5 accounting endpoints (`cash-book`, `income-expense`, `dues`, `cost-by-referrer`, `journal`). Receptionist, Cashier, and Lab Tech receive HTTP 403.

### Area E: Regression & Invariants
- **E.1 `/business-day/state`:** Unchanged, money-free, accessible to all authenticated roles (including Lab Tech).
- **E.2 Whole-Taka Integers:** Verified schema column types (`integer`, `bigint`) and JSON responses across all new models.

---

## 3. Detailed Findings & Observations

### Finding 1 [HIGH SEVERITY]: Payments and Invoices Silently Succeed When Business Day is Closed or Reopened
- **Files & Lines:**
  - `backend/app/services/payment_service.py:140-158` (in `settle_due`)
  - `backend/app/services/invoice_service.py:326-336, 542-544` (in `confirm_invoice`)
  - `backend/app/services/accounting_service.py:97-102` (in `post`)
- **What Was Expected:**
  Prompt 18 Implementation Report (§2, Item 4) and Testing Prompt (§C, Item 6) specify that a closed or reopened day refuses ordinary journal-posting actions with HTTP 409 Conflict.
- **What Actually Happened:**
  When a business day is `CLOSED` or `REOPENED`:
  1. A receptionist calls `POST /invoices/{iid}/settle-due` or `POST /invoices` with an initial payment.
  2. The endpoint returns **HTTP 201 Created** (silent success).
  3. The payment is persisted with `business_day_id = None`.
  4. The journal entry is posted with `business_day_id = None`.
- **Root Cause Analysis:**
  In `payment_service.py` and `invoice_service.py`, the active business day is looked up via:
  ```python
  active_day = db.execute(select(BusinessDay).where(BusinessDay.tenant_id == tenant_id, BusinessDay.status == "OPEN")).scalars().first()
  ```
  When the day is `CLOSED` or `REOPENED`, `active_day` is `None`. The services assign `pmt.business_day_id = active_day.id if active_day else None` and pass `business_day_id = None` to `accounting_service.post`.
  Inside `accounting_service.post`:
  ```python
  if business_day_id is not None:
      ...
      if day.status == "CLOSED" or (day.status == "REOPENED" and not is_adjustment):
          raise HTTPException(status_code=409, detail="Business Day is closed...")
  ```
  Because `business_day_id` is `None`, the closed/reopened day check is completely bypassed!
- **Operational Impact:**
  Any cash payment taken after day close is completely excluded from drawer reconciliation for all business days (it does not count towards closing cash of the closed day, nor does it carry forward into the next day's opening or collections).

---

### Finding 2 [MEDIUM SEVERITY / AMBIGUITY]: `BANK_DEPOSIT` is Permitted for Admin Role
- **Files & Lines:**
  - `backend/app/api/v1/endpoints/business_day.py:99-103` (`add_movement`)
  - `backend/app/services/day_close_service.py:126-128` (`record_movement`)
- **What Was Expected:**
  Testing Prompt (§B, Item 6) states:
  > "...confirm owner-withdrawal and bank-deposit are Owner-only at the API level (not just hidden in the UI) by calling the endpoint directly with a non-Owner token and confirming 403."
- **What Actually Happened:**
  Calling `POST /business-day/movements` with an Admin token and `{"kind": "BANK_DEPOSIT", "amount": 20}` returns **HTTP 201 Created**.
- **Root Cause Analysis:**
  In `day_close_service.record_movement`:
  ```python
  if kind == "OWNER_WITHDRAWAL" and actor.role != "OWNER":
      raise HTTPException(status_code=403, detail="Only the Owner can record an owner withdrawal.")
  ```
  `BANK_DEPOSIT` has no role restriction check in `record_movement`. At the endpoint level, `/movements` requires `business_day.close`, which both Admin and Owner hold. Furthermore, Claude Code's own test `tests/test_prompt18_accounting_day_close.py` line 92 explicitly asserted that Admin succeeds with 201:
  ```python
  assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "BANK_DEPOSIT", "amount": 20}).status_code == 201
  ```
- **Operational Impact:**
  Admins can record cash deposits to the bank. If business policy strictly requires Owner-only authorization for bank deposits, this check is currently missing in the backend service.

---

### Finding 3 [DESIGN GAP]: Multiple Active Days Can Exist While a Day is Reopened
- **Files & Lines:**
  - `backend/app/services/business_day_service.py:131-146` (`open_business_day`)
  - `backend/app/services/day_close_service.py:41-46` (`_current_day`)
- **What Was Expected:**
  Only one business day session may be active at any given time.
- **What Actually Happened:**
  1. Business Day #1 is closed, then reopened by the Owner (status = `REOPENED`).
  2. A user calls `POST /business-day/open` to open Business Day #2.
  3. Business Day #2 opens successfully because `open_business_day` only checks `where(BusinessDay.status == "OPEN")`.
  4. Now Day #1 is `REOPENED` and Day #2 is `OPEN` simultaneously.
  5. `_current_day` immediately favors Day #2 (the `OPEN` day), stranding Day #1 in `REOPENED` state unless reclosed by explicitly specifying its `day_id`.
- **Operational Impact:**
  Front-desk operations can proceed on a new day while an earlier day remains un-closed in `REOPENED` status.

---

### Finding 4 [OBSERVATION]: Divergence Between Day-Screen Expected Cash and Journal Cash on Reopened Adjustments
- **Files & Lines:**
  - `backend/app/services/day_close_service.py:53-99` (`compute_summary`)
  - `backend/app/services/day_close_service.py:234-269` (`post_adjustment`)
- **Scenario:**
  Owner reopens a day and enters a manual adjusting journal entry touching Cash (e.g. `Dr Cash 500, Cr Test revenue 500`).
- **Behavior:**
  The Journal `Cash in hand` (code 1010) increases by 500.
  However, `compute_summary` calculates expected cash strictly from source tables (`Payment`, `RefundRequest`, `DayMovement`), completely ignoring the journal ledger.
  Therefore, the day-screen `expected_cash` does not change. When the owner counts 500 more cash, a +500 variance is recorded.
- **Conclusion:**
  This confirms the divergence risk highlighted in the prompt review: computing D45 expected cash from source tables rather than the journal ledger means adjustments to cash in the journal will not flow into expected cash calculations on the day screen.

---

### Finding 5 [TEST SUITE OBSERVATION]: Worklist Order Pagination Limit in Pre-Existing Tests
- **Files & Lines:**
  - `tests/test_prompt10e_rooms_roles_worklist.py:120, 145`
  - `backend/app/services/worklist_service.py:305`
- **Issue:**
  In `medscope_test`, cumulative test runs have accumulated 6,917 test orders, including 258 `urgent=True` orders.
  `/worklist` enforces `limit: int = Query(default=100, le=200)` and orders by `desc(TestOrder.urgent), desc(TestOrder.created_at)`.
  Because `test_prompt10e_rooms_roles_worklist.py` asserts that a newly created non-urgent order is in `_ids(client, ADMIN_HEADERS)`, and the first 200 items returned are all pre-existing urgent orders, the non-urgent order is pushed beyond the 200-item page limit, causing pre-existing tests to fail when run against an older test database.

---

## 4. Test Suite Summary

### New Test Suite Details
- **File:** `tests/test_prompt18_verification.py`
- **Test Count:** 30 comprehensive automated tests
- **Execution Command:** `python -m pytest tests/test_prompt18_verification.py -v`
- **Execution Time:** ~7.3 seconds
- **Pass Rate:** **30 passed / 30 tests (100%)**

### Test Inventory
1. `test_a1_every_journal_entry_balances_all_paths` — All 14 posting paths produce balanced entries
2. `test_a2_db_triggers_reject_raw_update_and_delete` — PostgreSQL triggers enforce append-only rules
3. `test_a3_db_deferred_constraint_refuses_unbalanced_entry_at_commit` — Deferred constraint trigger blocks unbalanced commits
4. `test_a4_reversal_uniqueness` — Only one reversal allowed per original entry
5. `test_a5_unbuilt_modules_no_accounts_or_postings` — No accounts/postings for unbuilt modules
6. `test_a6_expected_cash_vs_journal_cash_probe` — Expected cash vs journal cash alignment probe
7. `test_b1_bill_confirmed_split_and_discount_rules` — Bill confirm split across receivable, discount, revenue, urgent fee
8. `test_b2_payment_received_all_channels` — Payments across all 6 payment channels post to correct accounts
9. `test_b3_line_cancelled_immediate_and_approval` — Cancellations post correctly under immediate and approval paths
10. `test_b4_refund_paid_disbursement_separation` — Disbursement is the sole posting event for refunds
11. `test_b5_due_written_off_hard_separation_from_discount` — Write-offs post strictly to bad debt (5100), not discount
12. `test_b6_movements_and_rbac_investigation` — Bank deposit, drawings, expenses and role enforcement
13. `test_b7_lazy_account_creation_fresh_tenant` — 16 accounts seeded idempotently on first event
14. `test_c1_d45_expected_cash_identity_and_integers` — D45 expected cash formula identity and whole-taka math
15. `test_c2_writeoffs_do_not_affect_expected_cash` — Write-offs are non-cash and do not affect drawer
16. `test_c3_per_channel_independence` — Channels operate independently from cash drawer
17. `test_c4_variance_reason_gating_and_tolerance` — Reason required above tolerance; within tolerance allowed
18. `test_c5_business_day_close_rbac` — Day close restricted to Admin and Owner
19. `test_c6_closed_or_reopened_day_refuses_actions` — Movements and direct posts refused on closed day
20. `test_c7_reopen_owner_only_and_preserves_closed_at` — Owner-only reopen; re-close preserves original timestamp
21. `test_c8_reopened_day_accepts_only_adjustments` — Reopened day accepts only valid adjustments
22. `test_c9_movements_cannot_exceed_expected_cash_and_expense_note_required` — Movements bounded by drawer cash
23. `test_c10_close_body_contract_requires_counted_cash` — Close endpoint enforces counted_cash requirement
24. `test_d1_cash_book_and_income_expense_exact_math` — Cash book and Income-Expense reports exact calculations
25. `test_d2_dues_report_date_filtering` — Dues report date filtering preserves underlying metrics
26. `test_d3_cost_by_referrer_billing_real_and_cost_zero` — Cost-by-referrer displays billing and zero cost
27. `test_d4_csv_exports_validity_and_utf8_bom` — CSV exports valid, formatted with UTF-8 BOM
28. `test_d5_accounting_view_permission_matrix` — `accounting.view` RBAC matrix verified
29. `test_e1_business_day_state_endpoint_unchanged` — `/business-day/state` remains money-free for all roles
30. `test_e2_whole_taka_integers_preserved_everywhere` — Schema and payloads enforce whole-taka integer math

