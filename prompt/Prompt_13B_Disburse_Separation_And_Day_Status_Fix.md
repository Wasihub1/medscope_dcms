# Prompt 13B: Always-Separate Disbursement + Business Day Status Display Bug

## Context — read first
Inspect the real repository and all nine canonical docs before changing anything. Re-check `git status` / `git log` — do not assume the working tree matches `PROMPT_13A_IMPLEMENTATION_REPORT.md`; the owner may have committed since. This prompt has two unrelated items; treat them independently in the report (separate Done/Partial/Blocked, separate files-changed list, separate test evidence) even though they ship in one prompt.

## Item 1 — Disbursement must always be a separate, deliberate action

Prompt 13A built an **optional** combined flow: cancelling a line or a whole invoice could, in the same call, also disburse the refund if a `disbursement_method` was supplied up front. The owner has now reviewed this in the browser: the amount breakdown does display correctly before confirming, but disbursement happening automatically inside the same cancel action feels hazardous — cancelling a record and paying out money are different kinds of action, and the combined one-click path makes a wrong amount or wrong channel harder to catch or walk back.

- **Remove the combined cancel+disburse-in-one-call path entirely.** Cancelling a line (`POST /refunds/request`) or a whole invoice (`POST /refunds/cancel-invoice`) must never accept or act on a `disbursement_method`/reference in the same call — strip that parameter from the request schema (or ignore it server-side and stop advertising it in the API docs/UI), so there is no way to pay money out as a side effect of cancelling.
- **Cancellation always results in the same post-state Prompt 13A already built for the "no channel given" path**: line/invoice cancelled immediately (still no approval step — that stays exactly as 13A left it), `RefundRequest` row left `APPROVED` with a refund due, visible on the Refunds page as a disburse-pending line.
- **Disbursement is always its own explicit step**, through the existing `disburse_refund` call, with its own confirm action and its own amount/channel display — whether that button sits on the Refunds page (as it does today for the no-channel case) or appears immediately after a successful cancel in the UI as a clearly separate second click (not pre-filled and auto-submitted). Either placement is fine; what matters is that disbursing is never silently bundled into the cancel click.
- Update the frontend: the combined "select channel and cancel" UI control from 13A goes away; cancellation UI no longer asks for a channel at all. After a successful cancel, if a refund is due, point the user at the disburse step (e.g. "Refund of ৳X is pending — disburse now" linking to the existing disburse action) without auto-submitting it.
- Do not change anything about D15, imaging-started cancellation, or owner same-day unlock — their approval and disbursement flows are untouched.

## Item 2 — Business Day status shows differently per role (bug)

The owner has found that the same business day, at the same moment, displays as **"Business day closed"** on the Lab Tech's screen while Admin, Owner, Receptionist and Cashier screens all correctly show **"Day Open"**. There is only one open business day at a time in this system (per the existing Business Day rule) — the status must be the same for every role.

- Inspect the real cause before fixing: likely candidates are a role-scoped query that filters business-day status differently for Lab Tech, a stale/cached value on the Lab Tech dashboard that isn't invalidated the same way as other dashboards, a wrong endpoint or wrong permission-gated field being read on the Lab Tech screen, or a front-end component defaulting to "closed" when a field it expects (e.g. a money-permission-gated field) comes back empty/forbidden for Lab Tech.
- Fix the root cause so business day status is read from the same source and reflects the same true state for every role, including Lab Tech. Lab Tech must still not see any money fields (M11.3) — the fix must not leak financial data to Lab Tech while fixing the status display; if the current bug is literally caused by open/close status being bundled with a money-gated response, split the open/closed boolean out as its own non-financial field that every role can read.
- Add a non-browser test (backend or frontend unit, whichever is relevant to the real cause) that asserts Lab Tech and another role see the same business-day status given the same server state, so this can't silently regress.

## Must NOT do
- Do not touch D15 (post-lock Not Performed), imaging-started cancellation, or owner same-day unlock.
- Do not reintroduce an approval step for pre-lock cancellation — that stays removed, per 13A.
- Do not expose any money/financial field to Lab Tech while fixing Item 2.
- Do not edit the master context file.
- Do not start Module 14 or any other new module.
- Do not do any browser testing or claim browser acceptance.
- Do not touch `medscope_dcms` data; do not commit/push/stash/reset.
- Do not add a new permission key for either item unless genuinely required — explain in the report if one turns out to be necessary.

## Required checks (non-browser)
`pytest` (against `medscope_test` only), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`. No schema change is expected for either item; if one turns out to be needed, follow the usual migration + single-head + pre-migration `pg_dump` rule.

## Required report and documentation
`report/PROMPT_13B_IMPLEMENTATION_REPORT.md`, covering both items separately: what you found first for each (including, for Item 2, the actual root cause once inspected — state plainly if it differs from the candidates listed above); Done/Partial/Blocked/Deferred; files changed; any schema/migration impact; API path/operation counts before/after; actual validation results; an Assumptions table for anything not fully specified above (e.g. exact wording/placement of the post-cancel "disburse now" prompt).

**Update all nine canonical docs** — this is mandatory, not optional, per the owner's standing rule: `README.md`, `project-context.md`, `docs/SCOPE.md` (record the removal of the combined cancel+disburse path as part of the same §9 supersession, and note the Business Day status fix), `docs/ARCHITECTURE.md`, `docs/DESIGN.md` (disburse-button placement), `docs/API.md` (schema/parameter removal, updated counts), `docs/WORKFLOWS.md` (cancel → disburse is now always two steps), `docs/DATABASE.md`, `docs/TESTING.md` (new evidence + an owner checklist item for both fixes). If a doc has no substantive change for one of the two items, say so explicitly rather than skipping it silently.
