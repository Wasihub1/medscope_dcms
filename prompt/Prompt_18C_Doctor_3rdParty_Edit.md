# Prompt 19: Investigate and Fix — Doctor/3rd Party Edit

## Context — read first
Inspect the real repository, the real database, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the Prompt 18B report; do not assume the working tree matches it. This is a small, targeted fix prompt, not a new module.

**The gap:** on the Catalog & Deleted screen's "Doctors & 3rd parties" tab, every row has only a **Delete** action — no visible way to edit an existing doctor/3rd-party's own details (name, phone, type, registration number, specialty, chamber, etc.). If this is really the only screen that manages these records, then once a doctor/referrer is created, a typo'd phone number or wrong registration number can never be corrected — the only options would be deleting it (soft delete, per Prompt 11) and adding a new one, which breaks the link existing bills/reports have to the original record.

## Item 1 — Investigate first
- Confirm whether an edit path for an existing doctor/3rd-party record exists **anywhere** in the app — check: clicking into a row on this screen (does anything happen?), the inline-add-during-billing flow (does it allow editing an already-selected referrer, or only adding a new one?), the rate-card editor mentioned in the master scope (M4 — does editing a rate card also allow editing the referrer's own name/phone/registration number, or only the rate?), and any other screen that might reach this data.
- Report exactly what you find: is there truly no edit capability at all, or does one exist somewhere non-obvious that just needs surfacing/linking from this screen?

## Item 2 — If no edit capability exists anywhere, build it
- Add an **Edit** action alongside Delete on the "Doctors & 3rd parties" tab (and, if a parallel situation exists on the "Tests" tab for the test catalog, note that in the report — but do not build a Tests-tab edit here unless it's trivially the same mechanism already in place; stay scoped to doctors/3rd parties).
- Edit should open the same fields available at creation (name, type, phone, registration number, specialty, chamber, etc. — whatever the current create-flow actually captures, per your Item 1 investigation) in an editable form, save via a `PUT`/`PATCH`-style update to the existing record (not a delete+recreate).
- Editing a doctor/3rd-party's own details must **never** affect already-saved bills, reports, or commission ledger entries that reference them — those keep whatever snapshot they already captured (e.g. a report that already printed a doctor's registration number should not retroactively change if the registration number is corrected later). Investigate whether such snapshots already exist (e.g. does a report snapshot the doctor's registration number at finalization, per Prompt 16's report_versions content_snapshot?) and confirm editing is safe; if any place reads the referrer's live record instead of a snapshot where it shouldn't, flag it — don't silently rework that data flow here unless it's a one-line read-vs-snapshot fix.
- Editing a referrer's **rate card** is a separate, already-existing mechanism (per master scope M4) — confirm this prompt's edit screen either reuses it (link out to it) or leaves it untouched; do not duplicate rate-card editing here.
- Gate Edit with the same permission that already gates Delete on this screen (Admin/Owner, per Prompt 11's soft-delete scope) — do not invent a new permission key unless Item 1 reveals the existing one genuinely doesn't fit.

## Must NOT do
- Do not touch the Delete/restore mechanism from Prompt 11 — only add Edit alongside it.
- Do not rebuild the rate-card editor if one already exists — reuse/link to it.
- Do not change how commission, billing, or report snapshots work — only confirm they're unaffected by this edit, per Item 2.
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not start any other module.
- Do not commit, push, stash, or reset anything.
- Do not add a new permission key unless genuinely required.

## Schema change requirement (if any)
This is expected to be a UI + API fix with no schema change (the fields almost certainly already exist on the doctor/referrer table, since they're captured at creation). If Item 1's investigation reveals a genuinely missing field, it requires a correct Alembic migration with a correct `down_revision`, a single head (report `alembic heads` before/after), and the `pg_dump`-before-migrate sequence against `medscope_dcms` stated exactly, in order.

## Required checks (non-browser)
`pytest` (existing suite, `medscope_test` only — confirm it still passes; add a small number of tests proving: edit updates the record, edit requires the same permission as delete, and an existing bill/report's snapshot of the referrer's details is unchanged after an edit), `tsc -b`, `oxlint`, `vite build`, `alembic heads`/`alembic check` only if a migration was needed.

## Documentation requirement
Update the relevant doc sections (at minimum `docs/DESIGN.md` for the new Edit UI, `docs/API.md` for the new/changed endpoint, `docs/SCOPE.md` if this closes a gap worth recording) with current-truth-only content. If a doc has no substantive change, say so explicitly.

## Required report
`report/PROMPT_19_IMPLEMENTATION_REPORT.md`: what you found first (whether edit existed anywhere before this prompt, and where); Done/Partial/Blocked; files changed; the snapshot-safety confirmation (how you verified existing bills/reports/commission entries are unaffected by an edit); migration details if any; actual validation results; confirmation of which doc sections now describe only current truth.
