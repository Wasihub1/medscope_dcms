# Prompt 15: Doctor Sign-Off Screen (Per-Test Approval, D22)

## Context — read first
Inspect the real repository, the real database, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the Prompt 14 report; do not assume the working tree matches that report. This prompt implements **D22** (approval rule per test) and the approval half of Module 14's per-test rule from the master scope — it does **not** build the full Draft → Final report-versioning mechanism (`report_versions`, immutable Final state, QR, SMS). That is separate, larger work for Module 14 proper and must not be started here. What this prompt builds is the mechanism and screen by which a doctor-required or both-signature test actually gets its doctor sign-off recorded, which Module 14 will later depend on to decide when such a test order can finalize.

## Background (master scope, for reference)
- D22 / M5 / M14: approval rule is per test — `technician-final`, `doctor-required`, or `both-signature` (technician writes, then a second approver signs).
- B2 item 3 (confirmed by the owner, legal check advised): visiting doctors have no login (D59); **authorized staff record approval on the doctor's behalf** with an attestation tick; the report must print the doctor's name + registration number; the log must show who actually recorded the approval.
- M10: a doctor-required test order already has an `AWAITING_DOCTOR` status from existing routing (Prompt 05). This prompt uses that existing status as the queue, it does not invent a new one.
- Owner's decision in this chat (14 Nov 2026): approval can happen two ways —
  1. **Admin/Owner**, selecting the doctor and ticking attestation, approving on that doctor's behalf (the only path for visiting doctors, who have no login).
  2. **The DOCTOR role itself**, logged in, approving its own assigned test orders directly.
  Both paths must print the same doctor name + registration number on the eventual report, but the audit log must distinguish who actually clicked approve (the staff member, or the doctor personally).
- `both-signature` tests: the technician's own sign-off already happens at result entry (existing Module 13 result-submit step); this screen only adds the **second, doctor-side** signature. Do not rebuild or duplicate the technician's sign-off.
- `technician-final` tests never reach this screen at all — out of scope here.

## Item 1 — Inspect and confirm the DOCTOR role/user
- Check whether a DOCTOR role and at least one DOCTOR user already exist in `medscope_dcms` and `medscope_test` (the owner believes he created a DOCTOR user manually in the dev DB — verify, don't assume). Report exactly what you find.
- If no DOCTOR role exists, create it with the permissions it needs for this screen only (see Item 4) — do not grant it anything beyond that scope.
- If no DOCTOR user exists in `medscope_test` for testing, create one seed user there. Do not create a user in `medscope_dcms` — the owner manages real users there himself; if one is genuinely missing there, say so in the report and let the owner create it.

## Item 2 — The approval queue
- A worklist/queue view showing test orders that are `ENTERED` (result submitted, per Module 13) and whose test's approval rule is `doctor-required` or `both-signature`, and are not yet doctor-approved.
- **DOCTOR role** sees only test orders assigned to them (their own queue), mirroring how Lab Tech's worklist is scoped to assigned work.
- **Admin/Owner** see all such pending test orders across all doctors (for the visiting-doctor attestation path), with a way to pick which doctor's test orders to review/filter by.
- Reuse the existing worklist/queue UI patterns already built for Lab Tech (Module 11) rather than building a new list component from scratch.

## Item 3 — The approval action itself
- Opening a pending item shows the result (read-only, same data the technician entered — reuse the existing result display component from Module 13, do not rebuild it), the reference range used (per the new D24 versioned-range snapshot from Prompt 14), the test's approval rule, and the assigned/relevant doctor's name and registration number.
- **Path A — Admin/Owner on a doctor's behalf:** a doctor selector (search by name, same pattern as referrer/doctor search elsewhere in the app), a mandatory attestation checkbox/tick with explicit wording (e.g. "I confirm Dr. X has reviewed and approved this result"), and a Confirm action. Reason/notes field optional.
- **Path B — DOCTOR role, own result:** no doctor selector needed (it's always themselves); a single Confirm/Approve action, no attestation checkbox needed (they are the one approving, not attesting on someone else's behalf).
- Both paths write an approval record: who clicked it (`approved_by_user_id`), which doctor the approval is attributed to (`doctor_id` — same as `approved_by_user_id`'s linked doctor profile in Path B, or the selected doctor in Path A), whether it was an attestation (`is_attestation: true/false`), timestamp, and optional notes. Write an audit row in the same transaction distinguishing "Dr. X approved own result" from "Staff Y recorded approval on behalf of Dr. X" — this distinction must be visible in the audit log viewer built in Prompt 11.
- For `both-signature` tests, this record is the **second** signature; store it alongside (not overwriting) the existing technician sign-off from Module 13. Confirm in the report how the two are related/queryable together (e.g. both visible on the same test order).
- On successful approval, the test order's status changes to whatever already indicates "doctor-approved, ready to finalize" if such a status exists in the current state machine (e.g. moving out of `AWAITING_DOCTOR`), or, if no such target status exists yet pending Module 14's own work, add the minimal flag/column needed (`doctor_approved_at`, `doctor_approved_by_id`) without inventing the rest of the Draft→Final machinery. State clearly in the report which you did and why.
- Rejecting/sending back (the doctor or staff disagrees with the result) is **out of scope for this prompt** — if the owner wants a reject-and-return-to-technician path, that is a separate future decision; do not build it speculatively here.

## Item 4 — Permissions
- Reuse `test_catalog`-style existing permission conventions. A `doctor.approve` style permission (or equivalent existing key if one already fits — check `invoice.line_unlock`/`audit.view`-style precedent before adding a new one) should gate: Admin and Owner (attestation path), and DOCTOR role for their own assigned items only (not other doctors' items, even though they hold the same permission key — scope by assignment in the query, same pattern as Lab Tech's own-tasks scoping).
- Receptionist, Cashier, Lab Tech must not see or reach this screen (403).
- Confirm whether a new permission key is genuinely needed or an existing one already covers it, and say so explicitly in the report (do not add one without checking first, per the project's standing precedent from Prompts 13/13A/14).

## Must NOT do
- Do not build the full Draft → Final report-versioning mechanism (`report_versions` table, immutable Final locking, QR, SMS trigger) — that is Module 14 proper, a separate future prompt.
- Do not build a reject/send-back-to-technician path — out of scope, not decided yet.
- Do not touch `technician-final` tests' flow.
- Do not rebuild the technician's own sign-off from Module 13 — only add the doctor-side signature alongside it.
- Do not create a DOCTOR user in `medscope_dcms` — dev-DB user creation there is the owner's own job; report if one seems to be missing.
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not start any other module.
- Do not commit, push, stash, or reset anything.
- Do not add a new permission key unless Item 4's check genuinely requires one.

## Schema change requirement (if any)
If a schema change is needed (e.g. a new `doctor_approvals` table, or `doctor_approved_at`/`doctor_approved_by_id` columns on the test order), it requires a correct Alembic migration with a correct `down_revision` and a single head — report `alembic heads` before and after, review autogenerated operations by hand, and take a fresh `pg_dump` into `backups/` before applying anything to `medscope_dcms`.

## Required checks (non-browser)
`pytest` (against `medscope_test` only), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`.

## Documentation requirement
Update all nine canonical docs (README, project-context, SCOPE, ARCHITECTURE, DESIGN, API, WORKFLOWS, DATABASE, TESTING) with real, current-state content — per the owner's standing rule, describe only current truth; do not leave superseded/historical sections in place anywhere you touch. If a doc has no substantive change, say so explicitly rather than skipping it silently.

## Required report
`report/PROMPT_15_IMPLEMENTATION_REPORT.md`: what you found first (DOCTOR role/user state in both DBs, current test-order states for doctor-required/both-signature tests, whether any approval mechanism already exists informally); Done/Partial/Blocked/Deferred per item; Assumptions table (wording of the attestation checkbox, exact target status/flag chosen in Item 3, permission-key decision); files changed; migration details if any; API path/operation counts before/after; actual validation results; confirmation of which doc sections describe only current truth.
