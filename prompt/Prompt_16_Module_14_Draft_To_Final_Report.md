# Prompt 16: Module 14 — Draft to Final Report

## Context — read first
Inspect the real repository, the real database, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the Prompt 15 report; do not assume the working tree matches it. This is the first prompt for **Module 14** (Draft → Final report), building on top of what already exists: Module 13 result entry (DRAFT/ENTERED result status), the per-test approval rule (`technician-final` / `doctor-required` / `both-signature`), and the Doctor Sign-off mechanism built in Prompt 15 (`doctor_approvals` table, which currently moves a test order to `COMPLETED` on approval).

**Important — investigate before building.** This project's history (Prompts 12, 13, 15) has repeatedly found that an earlier prompt's stated premise about existing behavior was wrong once the agent actually inspected the code. Before writing any new finalization logic, inspect exactly how `TestOrder.COMPLETED`, `results.status` (DRAFT/ENTERED), `doctor_approvals`, and the culture multi-stage lifecycle (`Incubating → Preliminary → Final`) currently relate to each other, and report what you find. In particular: is `COMPLETED` on a test order already being treated as "the report is final" anywhere in the code (it should not be — it is an operational/approval status, not a report-version status), and does a culture test's own stage `FINAL` ever get confused with the report being Final (Prompt 15's report explicitly flagged this as something to watch)?

## Background (master scope, for reference)
- M14 (checklist + D22, D26): Draft can be saved repeatedly; **Final closes the report**. Who finalizes follows the per-test rule: `technician-final` → technician; `doctor-required` → the doctor approval already recorded (per item 3 of the owner's confirmed defaults, built in Prompt 15); `both-signature` → both signatures (technician's existing sign-off from Module 13 + the doctor approval from Prompt 15). Auto-save is on; two people must not be able to open/edit the same draft at once. Signature images/digital seals *can* be uploaded (per scope) but this is secondary — see Item 4 and Must NOT do.
- D26 / M15 (for context, NOT to be built here): each report version has its own ID; a correction creates a new version and marks the old one Superseded. **Module 15 (Corrections) is separate and is not part of this prompt** — for now, each test order's report has exactly one version (version 1) once finalized, and that is as far as this prompt goes.
- D63 / M25 (for context, NOT to be built here): finalizing triggers a report-ready SMS. **No SMS/QR integration exists yet** (confirmed not started per the project's own tracking) — this prompt must not attempt to build real SMS sending. See Item 5 and Must NOT do.
- From Prompt 10F: the `/reports` sidebar already has a "Ready Results" tab (default, working) and an "Issued Reports" tab that has been sitting empty "until Module 14 exists" — this prompt is what fills it.
- B10 (state machine, for reference): Report version: Draft → Final (per-test approval rule) → Superseded (M15, not here) / Cancelled (owner unlock or Not Performed, M29 — already partially implemented in the cancellation flow from Prompts 12/13/13A). If a test order is cancelled or marked Not Performed **after** its report was already finalized, the existing cancellation flow's effect on a Final report needs to be confirmed/handled — investigate and report; do not build a new cancellation mechanism here.

## Item 1 — Report version model and the Final state
- New `report_versions`-style table: one row per finalized report (test order reference, version number — always `1` for now since M15 doesn't exist yet, status `FINAL`, a content snapshot of the result as it was at finalization — reuse the existing result-item snapshot data from Module 13/Prompt 14 rather than duplicating it, `finalized_at`, `finalized_by_user_id`, report id).
- Once a `report_versions` row exists for a test order, that report is **immutable** — no code path may alter its stored content. (There is no correction mechanism yet — that is Module 15. If the underlying result or test order changes after finalization for any reason, the report_version row itself must not change; report this as a design note, don't build a correction path.)
- A still-draft result (per Module 13's existing DRAFT/ENTERED mechanism) has no `report_versions` row yet — unaffected by this prompt.

## Item 2 — Who finalizes, and when (per-test rule)
- **`technician-final` tests:** add an explicit **Finalize** action, available once the result is `ENTERED`, usable by whoever can currently complete that test order (existing permission). Clicking it creates the `report_versions` row and marks the report Final. This is a new, distinct step from "submit result" — investigate whether the existing flow already (incorrectly) treats ENTERED+COMPLETED as final for these tests, and say so if it does.
- **`doctor-required` and `both-signature` tests:** the doctor approval recorded in Prompt 15's flow (`doctor_approvals` row created) is the per-test "approval" the scope calls for. Decide, and justify in the report, whether finalization should happen **automatically in the same transaction as the doctor approval** (simplest, avoids a redundant second click, and matches the scope's description of approval-as-finalization) or as a **separate explicit Finalize step** after approval. Pick one, implement it consistently, and document the choice — do not leave it ambiguous or inconsistent between the two rule types.
- **`both-signature` specifically:** confirm both the technician's existing sign-off (Module 13, unchanged) and the doctor's approval (Prompt 15, unchanged) are present before the report_version is created; if either is missing, finalization must be blocked.
- Culture tests: finalization must wait for the culture's own lifecycle to reach its stage `FINAL` (per D19/M12) in addition to whatever sign-off rule applies — investigate the current culture stage implementation and integrate correctly; do not let a culture test finalize early.
- A cancelled, rejected, spoiled, or Not-Performed test order must never be finalizable — confirm the existing status checks already block this, or add the check.

## Item 3 — Concurrency and auto-save
- Investigate whether the existing Module 13 draft-save mechanism already prevents two people from having the same draft open/editable at once. If it does not, add a simple guard (e.g. a "currently being edited by X, last saved at Y" indicator, or an optimistic-lock check on save) — keep it simple, this is not meant to be a full collaborative-editing system.
- Auto-save on drafts is already expected to exist from Module 13; confirm it still works and is not disturbed by this prompt's changes.

## Item 4 — Signatures (minimal, no file-upload build-out)
- The scope mentions signature images/digital seals can be uploaded. For this prompt, store only the **text** signature data already available (doctor/technician name + registration number, already used in the Prompt 15 doctor-approval snapshot and Module 13's technician sign-off) on the `report_versions` row for later printing. **Do not build file upload for signature images or seals in this prompt** — that belongs with the actual report-printing/PDF work (M9/QR/M25 territory), which is not part of Module 14's scope here. State this limitation plainly in the report.

## Item 5 — Report-ready "SMS" hook (placeholder only)
- At the moment a report becomes Final, write a clear placeholder/log entry (e.g. an `sms_log`-style row with status `PENDING_INTEGRATION`, or an audit row) marking "report-ready notification due" — **do not integrate with any real SMS gateway or send any actual message.** This mirrors how stock deduction was left as a documented integration boundary in Prompt 06; M25 will build the real sending later. Say explicitly in the report that no real SMS was sent or attempted.

## Item 6 — Fill the "Issued Reports" sidebar tab
- The existing `/reports` page's "Issued Reports" tab (built in Prompt 10F, intentionally left empty) should now list test orders with a `report_versions` row (`status = FINAL`), reusing the existing Ready Results list's UI patterns (search, filters) rather than building a new list component from scratch — follow the same precedent Prompt 15 used when it matched the Ready Results markup for its own queue.
- Clicking an issued report should show the finalized, immutable snapshot (reuse the existing result-preview component, as Prompt 15 did by extracting `ResultPreviewBody` — do not duplicate it a second time).

## Must NOT do
- Do not build Module 15 (Corrections) — no new-version-on-correction mechanism, no Superseded status handling beyond what already exists in the cancellation flow.
- Do not build any real SMS sending, WhatsApp, or QR code — placeholder/log only, per Item 5.
- Do not build signature image/seal file upload.
- Do not build actual PDF/print rendering of the finalized report (that's M9/M26 territory) — the "Issued Reports" view is a screen inside the app, not a printable document.
- Do not touch the pre-lock cancellation, business-day status, or reference-range versioning work from Prompts 13/13A/13B/14 except where this prompt's own finalization logic must correctly interact with an existing Cancelled/Not-Performed status (investigate and report; do not rebuild that logic).
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not start any other module.
- Do not commit, push, stash, or reset anything.
- Do not add a new permission key unless genuinely required — check existing keys (e.g. whatever already gates "Finalize report" per the permission matrix) first.

## Schema change requirement
This prompt changes the schema (new `report_versions` table at minimum, possibly a concurrency/lock field, possibly a placeholder SMS-log table). This requires: a correct Alembic migration with correct `down_revision` and a single head (report `alembic heads` before and after); hand-reviewed autogenerated operations; a fresh `pg_dump` into `backups/` before applying anything to `medscope_dcms`.

## Required checks (non-browser)
`pytest` (against `medscope_test` only), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`. Include a test proving a Final report_version's stored content cannot be altered by any later change to the underlying result (non-destructiveness, same style as Prompt 14's test).

## Documentation requirement
Update all nine canonical docs with current-state-only content, per the owner's standing rule — no superseded/historical sections left in any doc you touch. If a doc has no substantive change, say so explicitly.

## Required report
`report/PROMPT_16_IMPLEMENTATION_REPORT.md`: what you found first (the actual current relationship between COMPLETED, doctor_approvals, culture stages, and any existing notion of "final" before this prompt); Done/Partial/Blocked/Deferred per item; Assumptions table (auto-finalize-on-approval vs separate click, and why; concurrency guard chosen; anything else underspecified above); files changed; migration details; API path/operation counts before/after; actual validation results including the non-destructiveness test; confirmation that no real SMS/QR/PDF work was attempted.
