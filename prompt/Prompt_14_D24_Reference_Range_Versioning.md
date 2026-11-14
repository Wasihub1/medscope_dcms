# Prompt 14: D24 — Reference Ranges Versioned by Sex and Age Band (Days)

## Context — read first
Inspect the real repository, the real database schema, and all nine canonical docs before changing anything. Re-check `git status` / `git log` — the owner may have committed since the 13B report; do not assume the working tree matches that report. This is a new, standalone piece of work (not a continuation of the Prompt 13 cancellation line) — it implements **D24** of the master scope, which Module 14 (Draft → Final report) will depend on later. Do **not** start Module 14 or any other module in this prompt.

## Background (master scope, for reference)
- D24 / M5 / M13 (master context, Part B, decision 24): "Reference ranges versioned by sex and age band in days; change = new version; old results keep snapshot."
- B3 §3.2 (snapshots and immutability): "Each result stores the reference range used at the time (D24); editing a range never changes an old report."
- B3 §3.5: age is entered in years/months/days at each visit; for reference-range band matching the system converts entered age + visit date to **total days**.
- Known conflict already on record (Part D of the master context / this project's own history): Prompt 07 built a simple, non-versioned `ref_min`/`ref_max` directly on the result-item/component data, with no sex or age-band dimension and no version history. That is the gap this prompt closes.

## Item 1 — Build the versioned reference range model
- Design and create a `reference_range_version` table (or equivalently-named, per existing naming conventions in the repo): test/component reference, sex (including "any"/not-applicable where a test has no sex-dependent range), age-band-in-days (`age_days_min`, `age_days_max`), value range (`ref_min`, `ref_max`), optional critical limits, an effective/version marker, and a link back to the component it ranges. Follow the Alembic and model conventions already in the codebase (naming, soft-delete/active flags if the codebase uses them elsewhere, timestamps).
- A component can have several bands (e.g. different age bands, different sex) active at once; a **new version for a given band** supersedes the old one for *future* results only — never rewrites history.
- Migrate existing data: the current simple `ref_min`/`ref_max` on test components becomes **version 1** of the new versioned model (one band covering the full age range, sex = "any", unless the current data already distinguishes sex/age in some ad hoc way — inspect and report what you find). Do not lose any existing range value in the migration.

## Item 2 — Use the versioned range at result entry, without touching old results
- At result entry, the system must pick the correct band by converting the patient's **entered age + the visit date into total days**, matching sex, and matching the test component, then use that band's range/critical limits for display and for the impossible-value validation already built in Prompt 07.
- The chosen band's range (and critical limits, if present) must be **snapshotted onto the result item at entry time**, exactly as the existing result-item snapshot pattern already does for other fields (component name, unit) — so an existing, already-saved result is untouched by this change and a later new version of a range never alters a historical report.
- If no band matches a given patient's age/sex for a component (a gap in the owner's data), decide a safe fallback (e.g. use an "any age / any sex" band if one exists, else flag the result row for review) and say in the report which fallback you implemented — do not silently use a wrong band.

## Item 3 — Admin management of ranges
- Give Admin/Owner a way to add/edit reference range versions per test component (new band, new version of an existing band, retire a band) from within the existing Catalog area — reuse existing Catalog UI patterns rather than building a parallel screen. Adding a new version must never edit or delete an old version's row; it only marks the old one no-longer-current going forward.
- This is catalog/admin work, not a money action — no new permission key should be needed if the existing "Edit test catalog/prices" permission already covers reference ranges; confirm and say so in the report, or justify a new key if genuinely required.

## Must NOT do
- Do not start Module 14 (Draft → Final) or any other module.
- Do not alter any already-saved result's stored range/flags — this prompt must be provably non-destructive to history (include a test that saves a result, then changes/adds a range version, then confirms the old result's snapshot is unchanged).
- Do not edit the master context file.
- Do not do any browser testing or claim browser acceptance.
- Do not touch `medscope_dcms` data directly — all schema changes go through Alembic, and before applying any migration to `medscope_dcms`, take a fresh `pg_dump` into the git-ignored `backups/` folder, per the owner's standing rule.
- Do not commit, push, stash, or reset anything.
- Do not invent clinical range values — the 26 seeded components from Prompt 07 are demo data; if real band values are needed beyond what already exists, carry the existing values forward as version 1 rather than guessing new clinical numbers.

## Schema change requirement
This prompt **does** change the schema (new `reference_range_version`-style table, and however the old `ref_min`/`ref_max` fields are deprecated/migrated). This requires:
- A correct Alembic migration with a correct `down_revision` and a **single head** after applying — run `alembic heads` before and after and report both.
- Autogenerated operations reviewed by hand, not blindly applied.
- A fresh `pg_dump` of `medscope_dcms` into `backups/` **before** applying the migration there (if the owner has you apply it there at all this session — confirm with the report what you actually ran it against; `medscope_test` is always fine to migrate freely).
- `docs/DATABASE.md` updated with the new table, its relationships, and the migration history.
- If old `ref_min`/`ref_max` columns are dropped rather than deprecated-in-place, say so explicitly and confirm no data was lost in translation (show before/after row counts or a spot-check).

## Documentation requirement — current truth only
Update all nine canonical docs as always (Done/Partial/Blocked report, real validation results). In addition, for this prompt specifically: **go back through the docs touched by Prompt 13/13A/13B and remove the old, superseded descriptions entirely rather than leaving them as historical/labelled-superseded records.** Each doc should describe only the current, correct behavior — no "this used to work this way, now superseded" sections left in place. This applies at minimum to `docs/SCOPE.md` §9, `docs/API.md` §9, and `docs/DESIGN.md` §17 (the sections the 13B report explicitly said it left as historical records), and to any other doc where the same pattern was used. Confirm in this prompt's report which sections you removed.

## Required checks (non-browser)
`pytest` (against `medscope_test` only), `tsc -b`, `oxlint`, `vite build`, `alembic heads`, `alembic check`, plus the non-destructiveness test described in "Must NOT do."

## Required report
`report/PROMPT_14_IMPLEMENTATION_REPORT.md`: what you found first (current `ref_min`/`ref_max` implementation, whether any sex/age distinction already exists informally, git state); Done/Partial/Blocked/Deferred per item; Assumptions table (fallback-band behavior, whether a new permission key was needed, anything else underspecified above); files changed; full migration details (`down_revision`, head before/after, autogenerate review notes, `pg_dump` confirmation); API path/operation counts before/after; actual validation results including the non-destructiveness test; confirmation of which old doc sections were deleted per the documentation requirement above.
