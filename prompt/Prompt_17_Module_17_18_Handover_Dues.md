# Prompt 17: Module 17 (Report Handover) + Module 18 (Dues)

## Context — read first
Inspect the real repository, the real database, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the Prompt 16 report; do not assume the working tree matches it.

**Reminder on the Prompt 16 process deviation:** the migration was applied to `medscope_dcms` before the `pg_dump` was taken (a shell command ran `alembic upgrade head` without the test-DB override). Before applying any migration in this prompt, explicitly confirm which database a command targets, and take the `pg_dump` into `backups/` **first**, then apply. Report the exact sequence of commands you ran against `medscope_dcms`, in order, so this can be verified.

**Investigate before building — this is important here.** Prompt 16's own investigation found that `report_versions`, `report_deliveries`, a "due-hold rule" on reports, a printable preview, and dashboard/search integration **already existed** before any Module 14/17 work was done — more than this project's own tracking (the master context's module dashboard, which lists Module 17 as "Not established") suggested. Before writing any new handover code, inspect `report_deliveries` and whatever currently implements "held while due" / release / print-log behavior, and report in detail what already works versus what is actually missing. Build only the gap — do not rebuild something that already exists correctly.

## Background (master scope, for reference)

### Module 17 — Handover (B7)
- Search by bill no. (final/temporary), patient no., test, mobile, name, to find a report to hand over.
- Due can be paid from this same screen (reuse the existing payment flow — do not build a second payment UI).
- Report is **held** while test charges are due — this is a center setting (on/off); a held report can only be released by Admin/Owner.
- Every handover logs staff + time.
- Third-party collection is allowed without any special record in V1 (no ID capture, no signature-of-recipient — keep this simple, per scope).
- Reprint is logged and marked "Duplicate" (M9's existing reprint rule — confirm it is reused, not reimplemented).
- Online viewing/courier delivery is explicitly **deferred** (M17.4–6, per B14) — do not build those.

### Module 18 — Dues (B7, D43, D11)
- Dues are calculated from bills and payments only (already derived, never typed — existing rule, do not change it).
- **Patient dues and doctor balances are tracked separately.**
- A doctor can hold **two labeled balances** (D43): a wholesale receivable (the doctor owes the center, from wholesale-priced bills the doctor collected on, M28) and a professional-fee payable (the center owes the doctor, from visit fees held pending handover, M20/M28). Confirm how much of this already exists from the existing party-ledger/visit-fee-liability work and build only what's missing.
- Age buckets: 7 / 30 / 90 days, on outstanding patient dues.
- A call list of patients with outstanding dues, for staff follow-up. SMS reminders are explicitly **deferred** (not part of this prompt).
- **Write-off (D11):** Admin can write off within a configured limit; Owner can write off above it (the limit itself is one of the existing owner-editable settings — confirm it exists from earlier prompts, or add it if it genuinely doesn't). A write-off posts to a separate bad-debt record — it must never be mixed with or recorded as a discount.
- Corporate dues are explicitly **deferred** (B14) — do not build a corporate-specific due tracking mechanism.

## Item 1 — Handover screen
- One search box (reuse the existing global/role-aware search patterns already in the app — e.g. the header search or the Reports page's existing search — rather than building a new search component) that finds a confirmed bill/invoice by bill number (final or temporary), patient number, test name, mobile, or patient name, and shows its handover-relevant reports.
- Show each test order's report state (Ready/Issued per the existing definitions from Prompts 10F/16) and whether it is held for due.
- A "held" report shows the amount due and a way to take payment inline (reuse the existing payment-taking flow/component) before releasing, or, for Admin/Owner, a way to release it despite the due (per the center setting).
- Confirming handover writes a log entry: staff, time, which report(s), and (if relevant) that it was released-despite-due by Admin/Owner with a reason.
- Reprint of an already-handed-over report goes through the existing reprint/"Duplicate" mechanism (M9) — confirm it already logs correctly for this screen's context; do not build a parallel reprint path.

## Item 2 — The held-report center setting
- If a global on/off setting for "hold report while due" does not already exist from earlier work, add it as one of the existing owner-editable settings (alongside the other owner-editable numbers already in the system, e.g. role discount maximums) — do not hard-code it.
- When off, reports are never held for due and the due-payment-before-release step in Item 1 simply does not block anything.

## Item 3 — Patient dues view and call list
- A dues list (patient, bill reference, amount outstanding, age bucket 7/30/90) computed from existing bill/payment data — derived, not stored as a separate mutable figure.
- A "call list" view of overdue patients for staff to follow up on, with the ability to record a promised-payment-date note (already in scope as optional, per B6 M7) if that mechanism exists; otherwise keep this to a simple list, do not build a full CRM-style follow-up system.

## Item 4 — Doctor balances (two kinds, D43)
- Investigate what already exists: visit-fee-liability tracking (M20/M28) and any referrer/doctor party-ledger balance (M19/M4) may already cover parts of this.
- Present the two balances clearly separated for each doctor: wholesale receivable (what the doctor owes the center) and professional-fee payable (what the center owes the doctor, pending handover via the payout book in M20 — do not build M20's payout screen here, just the balance figure and its source data).
- Do not merge these two balances into one number anywhere in the UI or the data model — they must stay distinguishable (per the scope's explicit "two labeled balances" requirement).

## Item 5 — Write-off
- A write-off action on a patient due, with a reason, gated by amount: within the existing (or newly added, if missing) Admin limit it completes directly; above it, Owner must approve.
- Posts to a distinct bad-debt record — confirm this does not touch the existing discount data model or any discount-reporting figures (the master scope is explicit that write-offs and discounts must never be mixed).

## Must NOT do
- Do not build Module 19/20 (Commission, Payouts) — the professional-fee-payable balance in Item 4 is a read of existing data, not a new payout mechanism.
- Do not build Module 21/22 (Accounting, Day Close) — dues/write-offs here do not need to post journal entries; if the existing accounting integration (drawer/ledger from earlier prompts) already captures something relevant, confirm and reuse it, do not invent new double-entry postings.
- Do not build online report viewing, courier delivery, or SMS due-reminders (all explicitly deferred).
- Do not build corporate-dues tracking.
- Do not rebuild the existing payment-taking flow, the existing reprint/"Duplicate" mechanism, or the existing Ready/Issued report definitions — reuse them.
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not start any other module.
- Do not commit, push, stash, or reset anything.
- Do not add a new permission key unless genuinely required — check existing keys first and say so in the report either way.

## Schema change requirement (if any)
If a schema change is needed (e.g. a held-report setting row, a write-off/bad-debt table, a handover-log table if one doesn't already exist), it requires a correct Alembic migration with a correct `down_revision` and a single head. Report `alembic heads` before and after. Take the `pg_dump` into `backups/` **before** applying anything to `medscope_dcms` — see the reminder above; state the exact command order you used.

## Required checks (non-browser)
`pytest` (against `medscope_test` only), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`.

## Documentation requirement
Update all nine canonical docs with current-state-only content, per the owner's standing rule — no superseded/historical sections left anywhere you touch. If a doc has no substantive change, say so explicitly. In particular, correct the module-coverage dashboard's Module 17/18 lines, since Prompt 16 already found more pre-existing infrastructure than that dashboard reflected — state plainly what Module 17/18 actually cover now versus what the dashboard said before.

## Required report
`report/PROMPT_17_IMPLEMENTATION_REPORT.md`: what you found first (the real current state of `report_deliveries`, the due-hold rule, any existing doctor-balance/party-ledger data, any existing write-off or settings mechanism — and which of this prompt's items turn out to already be mostly done); Done/Partial/Blocked/Deferred per item; Assumptions table; files changed; migration details including the exact `pg_dump`-then-migrate command sequence against `medscope_dcms`; API path/operation counts before/after; actual validation results; confirmation of which doc sections now describe only current truth.
