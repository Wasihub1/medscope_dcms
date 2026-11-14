# Prompt 13: Pre-Lock Line Cancellation Workflow Fix (Receptionist Request → Admin/Owner Approval → Atomic Refund)

**Project:** MedScope DCMS. **Prompt id:** `13` (follows Prompt 12; 10D/10E/10F/11/12 are all reported Done; the owner is handling commit/push himself and may have already done so — check `git status` and `git log` at the start and report the real state, do not assume uncommitted).
**Prompt file:** `prompt/Prompt_13_PreLock_Cancellation_Refund_Fix.md`. **Report file:** `report/PROMPT_13_IMPLEMENTATION_REPORT.md`.

You are the coding agent with repository access. This prompt is self-contained. Work carefully and completely; do not shortcut any item. The real repository and the nine docs are the source of truth, not any report or this prompt's guesses about it. This is a **money-correctness and workflow-integrity fix** — treat it with the same care as the D15 refund rule.

---

## 0. Why this prompt exists

During browser acceptance of Prompt 12, the owner found that cancelling an unlocked (pre-sample) test line is effectively broken on the Receptionist side: there is no findable action to request cancellation of an unlocked line, the refund amount shown in the approval modal is manually editable (inviting mismatch with the system's own calculation), and the invoice's per-line status can get stuck showing "Awaiting Collection" instead of reflecting a cancellation/refund in progress. The owner has also decided the permission matrix needs a small, deliberate change: Receptionist gets a narrow **"Request Line Cancellation"** capability on unlocked lines (not general invoice editing). This prompt fixes all of that as one coherent workflow.

Current baseline (reported, verify against the repo): Alembic head `a4d8c2e6f1b7` (single head, no schema change from Prompt 12), 141 pytest tests passing, OpenAPI 97/111, 39 permission keys (21 money).

## 1. Read first (mandatory, before any change)

1. The nine docs, the ADL list (up to ADL-057), `report/PROMPT_12_IMPLEMENTATION_REPORT.md` and `report/PROMPT_11_IMPLEMENTATION_REPORT.md`.
2. The real code for: the existing D15 "Not Performed" two-stage refund flow built in Prompt 07 and extended in 10D/10E/10F/12 (`refund_service.py`, the refund request endpoints, the disbursement endpoint, the refund-eligibility checks, `line_lock_service.py` from Prompt 12, `requires_sample()` from Prompt 10F) — this is the **one existing refund pipeline**; any pre-lock cancellation path you build must flow into it, not duplicate it. Also read the Invoice View / Invoices grid frontend code (where a line's status/action buttons are rendered, and wherever "Awaiting Collection" or similar sample-status labels are computed, per Prompt 07 Fix 3 and the Prompt 12 auto-refresh work), the existing refund approval screen/modal ("Pre-Sample Refund Requests"), and `core/permissions.py`.
3. `git status`, `git log --oneline -20`, and `alembic heads` / `alembic current` to establish the real current state (the owner may have committed since Prompt 12; do not assume the working tree is still dirty — report what you actually find).
4. Confirm precisely, by reading the real refund calculation code, what the **current pre-lock cancellation path actually does today** (if anything) versus what the D15 post-lock path does. State in the report whether a pre-lock cancel/refund-request path exists at all right now, is partially wired, or is entirely missing — the owner's observation ("couldn't find the cancel option") suggests it may be missing or only reachable through a path that does not render for Receptionist.

Write down in the report what you found for each item before changing it.

## 2. Standing rules (all apply)

- **No browser testing of any kind** (no Playwright runs, Selenium, Cypress, Puppeteer, no opening the app). The owner does browser acceptance. Never claim browser acceptance.
- Allowed checks: `pytest` (only against `medscope_test`, hard guard stays), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`, static analysis, read-only DB inspection.
- Money is whole-taka integers. Financial, audit and event data is append-only. Never print or repeat any password, secret or connection string.
- Every authorization decision goes through the central permission module; backend enforcement is mandatory, UI hiding alone is never enough.
- Audit rows are written in the **same DB transaction** as the action that triggers them.
- Do not restore, delete or move any tracked-but-deleted files the owner intentionally removed. Do not edit past reports.
- **Never edit the master context file (`master_context_all_harness.md`).** The owner's permission-matrix decision in this prompt is recorded in `docs/SCOPE.md` (the living, owner-decision-driven doc), exactly as every other post-launch decision has been. Section 8 below says exactly what to write and where.

## 3. The permission-matrix decision (owner-confirmed, document in `docs/SCOPE.md` only)

The owner has decided to narrow what Receptionist can do on a **Confirmed, unlocked** invoice line, beyond what the original matrix in the master context allowed:

- **New capability: "Request Line Cancellation."** Receptionist (and Cashier, if the existing Request-vs-Approve split already includes Cashier for this kind of action — check the existing matrix cells for "Cancel/amend unlocked line" and mirror them) can submit a request to cancel one unlocked test line on a Confirmed invoice, with a reason.
- **This is not general invoice editing.** Receptionist must not gain the ability to change price, discount, payment, add lines, or edit anything else about a Confirmed invoice. Do not build a generic "Edit Invoice" capability. If the frontend needs a new button/action on the invoice grid, call it something scoped like "Request Cancellation" or "Cancel Line (request)", not "Edit".
- **Admin/Owner approve.** Approval is required exactly as the existing matrix already requires for "Cancel/amend unlocked line" (Admin/Owner). Do not change who approves.
- Record this narrowly-scoped addition in `docs/SCOPE.md`'s permission matrix section as an explicit, dated owner decision, quoting that it supersedes the original matrix cell for this one capability, with a one-line note on why (pre-lock cancellation needed a reachable, correctly-calculated request path). Do not touch the master context file.

## 4. Scope item 1: find/restore a reachable pre-lock cancellation request action

1. Based on what you found in Section 1.4, either restore a broken/hidden path or build the missing one — do not build a second, parallel cancellation mechanism if a Prompt 04/06/07-era one already exists in the backend and is just not rendered or not permissioned correctly for Receptionist.
2. The action is available only on a Confirmed invoice's line that is **not locked** (`requires_sample()`/`line_lock_service` from 10F/12 say whether the line is currently lock-eligible — use that existing check, do not write a new one) and not already cancelled/refund-pending.
3. Clicking it opens the refund/cancellation modal from Section 5. Submitting creates a **cancellation request** (reuse the existing `refund_requests`-style table/flow from D15 if the schema already generalizes to a pre-lock request type; if it does not, add a new `request_type` value such as `PRE_LOCK_CANCELLATION` rather than a new table — state your choice and why).
4. If the line is actually locked by the time the request is submitted (a race: sample was taken between page load and submit), refuse with a clear message and redirect the user to the existing D15 "Not Performed" flow instead — do not silently process a pre-lock cancellation on a now-locked line. This is also Section 6 below; implement them together.

## 5. Scope item 2: refund amount in the modal must be system-calculated, read-only, and shown as a breakdown

1. **Remove the editable amount input.** The person submitting a cancellation/refund request never types an amount. The modal always shows the system's own calculation.
2. **One calculation function, reused everywhere.** Find or create a single backend function that computes, for a given invoice and line: the line's price, the invoice's paid-to-date amount, the amount to be retained, the refund amount, and the resulting new due. This must be the exact same function/logic the invoice grid itself already uses to display its own numbers (the owner specifically flagged that the grid's own displayed math was correct, but the modal disagreed — so whatever the grid calls, the modal must call the same thing, not a second implementation of the same arithmetic). If two separate implementations currently exist, consolidate to one and delete the other; do not leave both alive.
3. **Modal breakdown (read-only fields):** invoice total, paid so far, this line's price, amount retained, **refund amount**, new due after this line is removed. Label each clearly. The reason field remains the only editable input (free text, required for Admin/Owner's approval step per the existing D15 pattern; decide and state whether the Receptionist's initial request also needs a reason — the owner's instructions do not say either way for the request step, so default to **optional at request, mandatory at approval**, matching the existing D15 convention, and flag this as an assumption for the owner to confirm).
4. **Recompute at approval time, not just at request time.** Between the Receptionist's request and the Admin/Owner's approval, payments could change (unlikely but possible) or other lines could be cancelled first. The Admin/Owner's approval screen must show the breakdown recalculated against the invoice's live state at the moment of approval, using the same single function, not a stale snapshot taken at request time — unless the existing D15 pattern already deliberately snapshots at request time for audit-trail reasons, in which case preserve that pattern and instead show both the snapshot-at-request and a live recalculation side by side, clearly labelled, so the approver sees if they differ. State which approach the existing code already takes and which you implemented.

## 6. Scope item 3: sample-taken lock must be enforced throughout, with a clear redirect to the existing approval workflow

1. **Backend gate (primary):** the cancellation-request endpoint must re-check, at submission time, that the line is still unlocked, using the same `requires_sample()`/`line_lock_service` check as Section 4.2. If the line has become locked (sample taken) between page render and submission, refuse with a clear 4xx and a message identifying this as a "sample already taken" case.
2. **Frontend dialog:** when the Receptionist clicks the cancellation action on a line that is already locked (or becomes locked in the response from step 1), show a dialog stating plainly that the sample has already been taken and that cancellation now requires the existing Admin/Owner approval path (D15 "Not Performed"), and — if the Receptionist's role allows initiating that flow at all per the existing matrix — guide them to it, or otherwise tell them to inform Admin/Owner. Do not let the pre-lock request silently proceed on a locked line, and do not duplicate D15's own approval logic here; this is routing/messaging only.
3. **One workflow, not two parallel ones:** after this prompt, there must be exactly one path for "cancel before lock" (Section 4, new) and exactly one for "refund after lock / Not Performed" (existing D15), with a correctly-enforced boundary between them at the lock event, and no third ad-hoc cancellation code path left anywhere in the codebase. If you find a third one during your Section 1 reading, remove it (reusing its logic into the two canonical paths if it did anything correct) and say so in the report.

## 7. Scope item 4: atomic transaction and line/invoice status correctness

1. **One DB transaction per cancellation action.** Whether at request, approval, or disbursement (mirror whichever stage(s) the existing D15 flow already splits this into — request / approve / disburse — for consistency; do not collapse D15's existing stages if the owner has not asked for that), the status changes, the audit row, and any ledger/commission-reversal effect for that stage must commit together or not at all.
2. **Explicit line status, not a bare boolean.** The invoice line (and/or its associated test order) must expose a clear status value through this lifecycle — at minimum: unlocked/normal → cancellation requested (pending approval) → cancelled (and, once refunded, a distinguishable refunded state) — rather than only a `refunded: true/false` flag. If the schema already has a richer status enum used by D15, extend/reuse it for the pre-lock path rather than inventing a second status field. State the exact states you ended up with.
3. **Fix the "stuck on Awaiting Collection" display bug.** Once a line has a pending cancellation request, is cancelled, or is refunded, the Invoice View must show that status instead of continuing to show the old sample-status label (e.g. "Awaiting Collection"). Find exactly why the current sample-status mapping (Prompt 07 Fix 3 / Prompt 12 auto-refresh) does not account for the cancellation/refund states and fix the mapping so cancellation/refund states take precedence over a stale sample-status label for display purposes. Confirm with a test that covers this precedence explicitly.
4. **Everything stays under one invoice.** The cancellation request, its approval, its audit rows, and the resulting line/invoice state must all be queryable and visible from the single Confirmed invoice's own ID — do not create a detached record that requires looking elsewhere to reconstruct what happened to that invoice.
5. **Double-request guard:** a line that already has a pending cancellation request cannot have a second one submitted; the UI action is disabled/hidden and the backend refuses with a clear 409.
6. **Invoice total/due recompute correctly** after approval and after disbursement, using the Section 5.2 shared calculation function, and reflect immediately in the Invoice View (reuse the Prompt 12 auto-refresh mechanism — the cancellation/approval/disbursement actions should also fire the existing `medscope:sample-changed`-style event or an equivalently named one, so the Invoice View refreshes without a manual reload; do not build a second refresh mechanism, extend the existing one).

## 8. Documentation (mandatory, with this prompt)

Update **all nine docs**. If a doc has no substantive change, verify that and record "reviewed, no change" in the report; do not invent content.

- `docs/SCOPE.md`: the Section 3 permission-matrix decision, quoted and dated, as an explicit supersession of the original matrix cell for "Request Line Cancellation" only; the corrected pre-lock cancellation workflow description (request → approve → disburse, who does each); the explicit boundary with the existing D15 "Not Performed" path.
- `docs/ARCHITECTURE.md`: new ADL(s) (continue from ADL-057) covering: the single shared refund-calculation function (consolidating any duplicate math found); the explicit line-status model; the one-path-per-lock-state design (no third ad-hoc cancellation path); the display-precedence fix for cancellation/refund over stale sample-status.
- `docs/API.md`: every new/changed endpoint (request, approve, disburse if changed, any status-read endpoints), the new/extended permission key(s), real counts (update from 39/21).
- `docs/WORKFLOWS.md`: the full pre-lock cancellation workflow end to end, explicitly diagrammed or described alongside the existing D15 workflow so the two are easy to tell apart; the "sample already taken" redirect dialog's place in the flow.
- `docs/DESIGN.md`: the refund modal's read-only breakdown layout; the "Request Cancellation" action's label and placement (explicitly not called "Edit"); the "sample already taken" dialog; the corrected status label shown on the invoice line.
- `docs/DATABASE.md`: any new/extended `request_type` value, any new or extended status enum/column, with the migration chain (see Section 9).
- `docs/TESTING.md`: new non-browser evidence; a corrected owner-acceptance checklist covering exactly the three problems the owner found (cancel option reachable for Receptionist on an unlocked line; refund modal shows the same numbers as the grid, read-only; invoice line status updates correctly instead of sticking on "Awaiting Collection") plus the new boundary checks (locked-line redirect, double-request guard, atomic rollback on a forced failure if testable).
- `README.md` and `project-context.md`: current phase, head, updated counts.
- **Docs rule from the owner:** this entire prompt is itself a "decided, now implemented" item — make sure nothing in the docs is left describing the old broken/missing behavior as current.

## 9. Schema and DDL discipline

A schema change is plausible here (new `request_type` enum value, a richer line-status column/enum, possibly a snapshot-vs-live calculation marker). Treat it as expected, not exceptional:

1. If a schema change is needed: create an Alembic migration with a correct `down_revision` (current head — confirm the real one per Section 1.3), review every autogenerated operation by hand, end with a **single head**. All new/changed columns nullable or safely defaulted; never wipe or reset existing data. Take a fresh `pg_dump` into the git-ignored `backups/` folder before applying anything to `medscope_dcms`. Never print or repeat the connection string.
2. Run `alembic heads`, then `alembic upgrade head` against the dev DB, then `alembic check` (must come back clean). Report the exact head hash before and after.
3. If no schema change is needed (e.g. the existing D15 status/request-type columns are already generic enough to extend in code only), prove it with `alembic heads` and `alembic check` and explain exactly why.
4. Update `docs/DATABASE.md` and add the ADL entry per Section 8.

## 10. Tests and validation (real results only)

Add backend tests for at least:
- A Receptionist can submit a pre-lock cancellation request on a Confirmed, unlocked line; the request is **not** processed with a client-supplied amount (confirm the endpoint ignores or rejects any amount field if one is even accepted, and always computes server-side).
- The refund breakdown returned to the request/approval screens matches, field for field, the invoice grid's own displayed totals for the same invoice/line (write this as a direct equality assertion between the two code paths' outputs, using the owner's real numbers as a regression case: invoice total 9000, advance paid 3000, cancelling a 5000 line — assert the exact retained/refund/new-due figures this produces and that both the grid and the modal would show the same numbers).
- Submitting a request on a line that is actually locked is refused with a clear error, distinguishable from a generic 400 (so the frontend can show the specific "sample already taken" dialog).
- A second request on a line that already has one pending is refused (409).
- Approval requires Admin/Owner (403 otherwise) and a reason (400 otherwise, confirming the chosen default from Section 5.3).
- After approval/disbursement, the line's status is no longer "Awaiting Collection"-equivalent and correctly reflects cancelled/refunded; the invoice total/due recomputes correctly.
- Everything (request, approval, audit rows, final state) is retrievable from the one invoice's id.
- Regression: the existing D15 "Not Performed" flow is completely unaffected — run its existing tests and confirm unchanged behavior.

Run and report the actual results: `pytest` (against `medscope_test` only), `tsc -b`, oxlint, `vite build`, `alembic heads`, `alembic check`. Do not run Playwright; the owner does browser acceptance.

## 11. Report: `report/PROMPT_13_IMPLEMENTATION_REPORT.md`

Sections: Done / Partial / Blocked / Deferred (real results only). Include: what you actually found in Section 1.4 (did a pre-lock path exist at all before this prompt); a worked numeric example using the owner's real case (9000 / 3000 paid / 5000 cancelled) showing the before-fix (if reproducible) and after-fix numbers side by side; the exact line-status states implemented; which calculation function is now the single source of truth and what, if anything, was deleted as a duplicate; an **Assumptions table** (at minimum: optional-vs-mandatory reason at request time; snapshot-at-request vs live-recalculation-at-approval choice; which permission key was extended vs newly added for "Request Line Cancellation"; whether Cashier also got this capability); files changed; migration/head before and after (or proof none was needed); docs updated per file; validation command results with real numbers; anything doubtful noticed but not fixed.

## 12. Must NOT do

- No browser testing, no Playwright run, no app opened in a browser.
- Do not give Receptionist (or Cashier) any invoice-editing capability beyond the narrow "Request Line Cancellation" action defined in Section 3 — no price edits, no discount edits, no payment edits, no adding/removing lines other than through this one request flow.
- Do not build a second refund/cancellation pipeline alongside the existing D15 flow — consolidate into exactly two clearly-bounded paths (pre-lock request→approve, and the existing post-lock D15 Not-Performed flow), per Section 6.3.
- Do not edit the master context file under any circumstance — the permission-matrix decision goes in `docs/SCOPE.md` only, per Section 3.
- Do not touch `performing_role` normalization, the 671 unmapped-room tests, the urgent-fee floor/cap rule, the master-discount behaviour (A3), the doctor sign-off screen, the reduced-motion control, or M11.4 barcode (still deferred).
- Do not start Module 14, 15, or 16.
- Do not modify `medscope_dcms` test/catalog/user data beyond what this fix's own migration (if any) requires; do not pre-emptively cancel/refund anything in the dev DB yourself.
- Do not create, change, or print any password, secret, or connection string.
- Do not commit, push, stash, or reset (the owner is handling git himself — check state, do not assume, but do not act on it either).
- Do not start the next prompt or module.

*End of Prompt 13.*
