# Prompt 18: Module 21 (Accounting) + Module 22 (Day Open/Close)

## Context — read first
Inspect the real repository, the real database, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the Prompt 17 report; do not assume the working tree matches it.

**Backup rule, repeated because it matters:** before applying any migration to `medscope_dcms`, take the `pg_dump` into `backups/` **first**, then migrate. State the exact command sequence you ran against `medscope_dcms`, in order (as the Prompt 17 report did).

**Scope note for this prompt specifically — implementation first, keep it lean.** This project has grown large and token cost now matters. For this prompt:
- Focus on **writing the code, the migration, and the documentation** correctly. Do not write a large new automated test suite mirroring the exhaustive per-item pytest coverage of earlier prompts (Prompts 13–17 each added 12–23 new tests; do not repeat that pattern here).
- You must still run the existing checks to prove you have not broken anything: `pytest` (full existing suite, `medscope_test` only — just confirm it still passes; add at most a small handful of new tests only where genuinely necessary to prove a non-destructiveness/correctness property that cannot be checked any other way, such as "a journal entry's debit always equals its credit" or "day close is blocked while any device has unsynced items would be, but there are none, so it is never blocked for a reason that doesn't exist yet"), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`.
- A **separate, later prompt will cover thorough testing and verification** for this module, run by a different agent (Gemini/Antigravity) — you do not need to anticipate or build that coverage now. Keep your own report proportionate: a clear Done/Partial/Blocked per item, the migration details, and the doc updates, without an exhaustive assumptions-and-edge-case catalogue unless something is genuinely ambiguous and needs the owner's decision.

**Investigate before building.** As in Prompts 16 and 17, check what already exists before assuming you're building from nothing — there is already some drawer/ledger integration from earlier prompts (cash drawer effects of cancellations/refunds/disbursements, the existing `/business-day/state` endpoint from Prompt 13B). Report what you find and build only the real gap.

## Background (master scope, for reference)

### Module 21 — Accounting (B8, D44, D49, D50)
- V1 reports: cash book, daily income & expense, dues, cost by referrer. P&L / balance sheet / cash flow are **not required now** — just keep the data model able to support them later (don't build the reports themselves beyond the four listed).
- Double-entry: every event posts equal debits and credits, per the posting-rules table in the master scope (Bill confirmed, Payment received, Line cancelled/refunded, Refund paid, Commission accrued/reversed/paid, Visit fee handed over, Consultant fee earned, Outside-lab cost incurred, Expense paid, Due written off, Cash variance, Bank deposit/owner withdrawal). Entries are never deleted; mistakes are fixed with a reverse entry.
- Only post what this project's data actually supports today: bill confirmation, payment, cancellation/refund (existing), write-off (Prompt 17, existing), cash variance and bank deposit/owner withdrawal (new, this prompt, tied to day close). **Commission accrued/reversed/paid, visit-fee handover, consultant fee, and outside-lab cost have no real data source yet** (Modules 19/20/28 are not built) — do not invent postings for events that cannot actually happen in the system yet; note this gap in the report rather than fabricating entries.
- No fiscal year; flexible date-range filtering. Export to Excel for the four V1 reports (reuse whatever export mechanism already exists elsewhere in the app, if one does, rather than building a new one).

### Module 22 — Day Open/Close (B8, D45–D48)
- Business day: Open (with opening cash) → Closed (counted cash, no unsynced items — there are none, since offline sync is not built; this check should simply always pass, not be invented as a real blocker) → Reopened (Owner only, with reason, adjusting entries only).
- **Expected cash formula (D45):** opening cash + cash collections − cash refunds − all cash paid out (write-offs are not cash and must not appear in this formula; commission/visit-fee/consultant/outside-lab payouts have no data source yet, so they contribute 0 for now — note this, don't fabricate).
- Wallet/bank channels checked on their own lines, separately from cash.
- Counted cash entry → variance (counted − expected); reason required above the owner's configured tolerance (use the `tenant_settings` mechanism built in Prompt 17 for this tolerance value, rather than adding a second settings mechanism).
- Closed day cannot be edited/backdated; Owner can reopen with a reason, and only adjusting entries follow — no silent edits to already-closed figures.
- Day close is **Admin/Owner only** per the existing, already-recorded dated supersession in `docs/SCOPE.md` (from Prompt 04) — do not change this; the permission matrix's "Cashier can close" line is historical and already correctly superseded in the docs.
- Bank deposits, owner withdrawals, and small expenses are entered from the day screen.

## Item 1 — Journal/ledger data model
- `accounts` (chart of accounts — the minimal set implied by the posting-rules table: cash, wallet/bank channels already in use, patient receivable, discount given, test revenue, doctor-fee liability, bad debt, cash variance, bank, owner drawings — only what's actually needed by Item 2's real postings), `journal_entries` + `journal_lines` (append-only; every entry's lines must sum to zero debit-credit).
- A reversal is a new entry referencing the original, never an edit.

## Item 2 — Real postings only
- Wire up journal postings for: bill confirmation (patient receivable net / discount given / test revenue, visit-fee liability if a visit fee line exists), payment received, line cancelled/refunded (existing cancellation flow — add the journal effect, do not change the cancellation logic itself), due write-off (existing Prompt 17 mechanism — add the journal effect, do not change the write-off logic), cash variance and bank deposit/owner withdrawal (new, from day close in Item 4).
- Do not post anything for commission, visit-fee handover, consultant fee, or outside-lab cost — say explicitly in the report that these are deferred because Modules 19/20/28 don't exist yet.

## Item 3 — V1 accounting reports
- Cash book, daily income & expense, dues (reuse Prompt 17's existing dues data, don't rebuild it), cost by referrer (likely mostly empty/zero right now since commission isn't built — report this honestly rather than faking figures). Flexible date range. Excel export if an existing export mechanism is reusable; if none exists anywhere in the app, a simple CSV/Excel generation is fine — don't over-build this.

## Item 4 — Day open/close screen
- Open with opening cash (if this doesn't already exist from earlier prompts' drawer work, build it; if it does, reuse it).
- Close: show expected cash per the D45 formula (using only the real postings from Item 2 — cash collections and cash refunds are real; other payout categories are 0 for now and the screen should make that legible, not misleading), take counted cash, compute variance, require a reason above the configured tolerance setting.
- Reopen: Owner only, reason required, and whatever "adjusting entries only" means in practice for this system — investigate what closed-day edit protection already exists (if any) and extend it, don't rebuild from scratch if something like it exists.
- Bank deposit / owner withdrawal / small expense entry from this screen, each posting the correct journal lines per Item 2.
- The existing `/business-day/state` endpoint (Prompt 13B) stays as is for the money-free status used elsewhere (e.g. Lab Tech's header) — this screen is additive, not a replacement.

## Must NOT do
- Do not build Module 19 (Commission) or Module 20 (Payouts) — no commission calculation, no payout book.
- Do not build Module 23 (full Audit Trail) beyond what already exists from Prompt 11's small viewer.
- Do not build P&L, balance sheet, or cash flow reports.
- Do not build offline sync — the "no unsynced items" day-close condition must simply always be true, not a real check against a sync queue that doesn't exist.
- Do not change who can close a day (stays Admin/Owner only, per the existing recorded supersession).
- Do not rebuild the existing dues data, cancellation/refund logic, or write-off logic — only add their journal-posting side effect.
- Do not write a large new automated test suite — see the scope note above.
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not start any other module.
- Do not commit, push, stash, or reset anything.
- Do not add a new permission key unless genuinely required — check existing keys first.

## Schema change requirement
This prompt changes the schema (`accounts`, `journal_entries`, `journal_lines`, possibly a day-close/variance table if one doesn't already exist). This **requires a correct Alembic migration with a correct `down_revision`, resulting in a single head** — report `alembic heads` before and after. Review autogenerated operations by hand. Take the `pg_dump` into `backups/` **before** applying anything to `medscope_dcms` — state the exact command order.

## Documentation requirement
Update all nine canonical docs with current-state-only content, per the owner's standing rule — no superseded/historical sections left anywhere you touch. If a doc has no substantive change, say so explicitly. This is mandatory, not optional.

## Required checks (non-browser)
`pytest` (existing suite against `medscope_test`, confirm it still passes; add only the few tests genuinely needed per the scope note), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`.

## Required report
`report/PROMPT_18_IMPLEMENTATION_REPORT.md` — keep it proportionate per the scope note: what you found first (existing drawer/ledger integration, what Item 1–4 actually needed to add versus reuse); Done/Partial/Blocked/Deferred per item; files changed; migration details including the exact `pg_dump`-then-migrate command sequence against `medscope_dcms`; API path/operation counts before/after; actual validation results; confirmation of which doc sections now describe only current truth.
