# Prompt 14 Implementation Report: D24 Reference Ranges Versioned by Sex and Age Band (Days)

**Date:** 2026-11-14. **Browser acceptance:** not run (owner does it). Nothing was committed, pushed, stashed or reset. Module 14 (Draft → Final) was not started. The master context file was not edited.

## 1. What I found first

| Item | Finding |
|---|---|
| Git state | Unchanged since the 13B report: 2 commits (latest `a6c0243`), ~165 modified/untracked paths; Prompts 10D to 13B are still uncommitted. |
| Current range implementation | Single, non-versioned `ref_min`, `ref_max`, `critical_min`, `critical_max`, `reference_range_text` columns directly on `test_components` (plus `impossible_min/max`, which are per-component physiological limits). `result_items` already snapshots `ref_min/ref_max/critical_*` and `reference_range` text at entry (the D24 snapshot pattern existed); it did not record which range was used. |
| Informal sex/age distinction | **None.** A scan of all `reference_range_text` values (both DBs) for male/female/child/infant/adult/neonate/men/women found 0 hits; every component had one range. (Some demo values look sex-specific, e.g. hemoglobin 12.0-16.0, but they are one range for everyone: I carried them as-is.) |
| Data volumes | `medscope_dcms`: 26 components (26 with reference values, 26 with critical limits), 18 result items. `medscope_test`: 27 components, 396 result items. |
| Age source | `visits.age_value` + `age_unit` + `gender` + `created_at` (visit date). `visits.age_days` exists but is a rough `x365 / x30` float; I did not rely on it for banding. |
| Catalog area | `CatalogAdminPage` (Tests / Doctors & 3rd parties / Deleted). No component or range management existed. Permission `test_catalog.manage` (Admin, Owner; not money) already gates that page. |
| Alembic head before | `a4d8c2e6f1b7` (single). |

## 2. Done / Partial / Blocked / Deferred

### Item 1: versioned reference range model: **Done**
- New table `reference_range_versions` (model `ReferenceRangeVersion`): component FK, `sex` (`ANY`/`MALE`/`FEMALE`), `age_days_min`/`age_days_max` (inclusive; max NULL = open ended), `ref_min/max`, `critical_min/max`, `reference_range_text`, `version_no`, `is_current`, `effective_from`, `retired_at`, `retired_by_id`, `created_by_id`, `created_at`, `change_note`. Partial unique index: one current row per (component, sex, band start). Several bands per component are current at once.
- Versioning: a new version inserts `version_no + 1` and sets the old row `is_current = false`/`retired_at`; rows are never updated in place or deleted. Retire marks a band not current (reason required). Same-sex current bands cannot overlap (409); an `ANY` band may sit beside sex bands.
- Migration of existing data: every component's single range became **version 1** (sex ANY, age 0 to no limit, `effective_from` = component `created_at`). Nothing was lost (see section 5).
- Old columns on `test_components` were **dropped** (not deprecated in place) to avoid two sources of truth, after the carry-forward was verified inside the migration. `impossible_min/max` stay on the component.

### Item 2: use the versioned range at result entry: **Done**
- Age + visit date -> total days (`age_to_days`: days as entered; months/years counted as calendar spans back from the visit date, leap years respected; 365/30 approximations only if there is no visit date). Gender -> `MALE`/`FEMALE`/none.
- Band choice (`pick_band`): (1) current band for the sex covering the age -> `MATCHED`; (2) current `ANY` band covering the age -> `MATCHED` if the component has no sex bands, `FALLBACK_ANY` if it has; (3) otherwise `NO_BAND`.
- **Fallback implemented (as requested to state):** an any-sex band for the age if one exists (labelled "any-sex range used"); otherwise the row is flagged for review: no range, **no flag computed (never "Normal")**, the UI says "No range for this age/sex: review manually", and the item is stored with `range_match = NO_BAND`. The old single range is never used as a guess. Gender Other/Unknown can only match `ANY` bands.
- The result template shows, and the save uses, the band for this patient; the server chooses the band (a client-sent range for a known component is ignored). Reference limits, critical limits and the flag come from the band; the Prompt 07 impossible-value check is unchanged (still rejects absurd values, tested).
- Snapshot: `ref_min`, `ref_max`, `critical_min`, `critical_max`, range text, plus new `result_items.reference_range_version_id` and `range_match` are stored on the item at entry. Results saved before this prompt keep their values and have both new columns NULL.
- Re-saving a still-draft result re-snapshots with the band current at that moment (existing draft behaviour); completed results are immutable (existing rule).

### Item 3: Admin management: **Done**
- Backend (`/reference-ranges/...`, 4 endpoints, `test_catalog.manage`): list a test's components with all versions; add band; new version of a band; retire a band. Audit rows (`REFERENCE_RANGE_BAND_CREATED`, `_NEW_VERSION`, `_BAND_RETIRED`) are written in the same transaction.
- Frontend: new **Reference ranges** tab in Catalog & Deleted (`ReferenceRangesPanel`), reusing the page's existing look, `Modal` and `ConfirmDialog`: test search, per-component table, Add band, New version, Retire (required reason), "Show old versions". The result entry modal shows the matched range, the any-sex note, or the no-range warning.
- **Permission key:** **no new key.** `test_catalog.manage` (Admin/Owner, not a money key) already covers the catalog area; only its description text now also says "manage reference-range versions". Receptionist, Cashier and Lab Tech get 403 (tested).

### Partial / Blocked / Deferred
None. Not done on purpose: no clinical range values were invented; the owner enters real age/sex bands. A date of birth is not recorded, so age comes from the age entered at the visit.

## 3. Assumptions

| Assumption | Choice |
|---|---|
| Fallback behaviour | any-sex band for the age, else flagged `NO_BAND` for manual review, never a wrong band (section 2). |
| Age band inclusivity | both ends inclusive, whole days; max NULL = no limit. |
| Age at the visit | calendar span counted back from the visit date (`visits.created_at` date), since only the entered age is known. |
| Where critical limits live | on the band (they can differ by age/sex), per the prompt. Impossible limits stay on the component. |
| Old columns | dropped after verified carry-forward (not kept deprecated). Downgrade restores them from the current any-sex/age-0 band. |
| `effective_from` of version 1 | the component's `created_at`. |
| Permission | existing `test_catalog.manage`; no new key. |
| Dev DB migration | applied to `medscope_dcms` (the app needs it) after a fresh `pg_dump`; see section 5. |
| Draft re-save | re-snapshots with the currently current band (existing draft behaviour). |
| Test data | the new tests create probe catalog tests (`P14_...`) in `medscope_test`, like the Prompt 13 probes; they are not purged (not asked). |

## 4. Files changed

Backend: new `app/services/reference_range_service.py`, new `app/api/v1/endpoints/reference_ranges.py`, `app/api/v1/router.py`, `app/models/test.py`, `app/models/result.py`, `app/models/__init__.py`, `app/schemas/result.py`, `app/services/result_service.py`, `app/core/permissions.py` (description text only), new migration `alembic/versions/b7e3d91c5a24_prompt14_reference_range_versions.py`. Frontend: new `features/admin/ReferenceRangesPanel.tsx`, `features/admin/CatalogAdminPage.tsx`, `components/common/ResultEntryModal.tsx`, `api/client.ts`, `types/index.ts`. Tests: new `tests/test_prompt14_reference_ranges.py` (12), `tests/conftest.py` (CBC demo components now get version-1 ranges). Docs: all nine.

## 5. Migration details

| | |
|---|---|
| Revision / `down_revision` | `b7e3d91c5a24` / `a4d8c2e6f1b7` |
| `alembic heads` before / after | `a4d8c2e6f1b7` / `b7e3d91c5a24` (single both times) |
| `alembic check` after | "No new upgrade operations detected." |
| Autogenerate review | Generated, then rewritten by hand: (1) the autogenerated plain `drop_column` of the five range columns would have **lost every range**, so a data step now inserts one version-1 row per component, checks `components = versions` and that no value differs (raises and drops nothing otherwise), and only then drops the columns; (2) the unnamed `result_items` foreign key got the name `fk_result_items_range_version` (autogenerate's drop in the downgrade would have failed); (3) the downgrade re-adds the columns and restores them from the current any-sex/age-0 band. |
| `pg_dump` | **Taken before applying to `medscope_dcms`:** `backups/medscope_dcms_pre_prompt14.dump` (custom format, ~194 KB, git-ignored; checked with `git check-ignore`). |
| Applied to | `medscope_dcms` (after the dump) and `medscope_test` (by the test session; also exercised both ways). |
| `medscope_dcms` result | 26 components -> 26 version-1 bands (26 with reference values, 26 with critical limits, all `sex ANY`, age 0 to no limit, version 1, current); 18 result items untouched (version id NULL). Spot check: HGB 12.0-16.0 critical 6.0-20.0 "12.0 - 16.0 g/dL"; ESR 0-20 critical max 100; TC 4000-11000 critical 1500-50000. |
| `medscope_test` result | 27 components -> 27 versions. Round trip: `downgrade a4d8c2e6f1b7` restored all 27 component ranges (exactly equal to the current bands), `upgrade head` re-created 27 versions. |
| Data lost | None. The only dropped objects are the five single-range columns whose values now live in version 1. |

## 6. API path / operation counts

| | Before (13B) | After |
|---|---|---|
| Paths | 102 | **106** |
| Operations | 116 | **120** |
| Permission keys / money | 39 / 21 | 39 / 21 (no new key) |

New: `GET /reference-ranges/tests/{test_id}`, `POST /reference-ranges/components/{id}/bands`, `POST /reference-ranges/versions/{id}/new-version`, `POST /reference-ranges/versions/{id}/retire`. Changed: result template and result save (and result item responses) now carry `reference_range_version_id` and `range_match`.

## 7. Validation (real results)

| Command | Result |
|---|---|
| `pytest` (`medscope_test` only), run **twice** | **180 passed, 0 failed** both runs (168 before + 12 new); referrer rows 10 after |
| Non-destructiveness test (`test_changing_a_range_never_alters_a_saved_result`) | passes: a result is saved (male, 12.5 -> LOW on 13-17); then a new version of the band (12-16, which would make 12.5 NORMAL), a new band and a retirement are made; the item's version id, match type, ref/critical limits, range text and flag are identical in the database and when re-read through the API; the next result uses the new data (or `NO_BAND` after retirement) |
| Other new tests | age conversion (leap years, month spans, no-visit-date approximation), sex mapping, sex band vs female band, any-sex fallback labelled, `NO_BAND` (no flag, no range, no wrong band, Other gender), impossible value still rejected, new version used for future results only, old row intact and history listed, validation/overlap/retire rules, Admin/Owner only (Receptionist, Cashier, Lab Tech 403), every component has a version 1 |
| `tsc -b` | 0 errors |
| `oxlint src` | 0 errors, 122 warning lines (unchanged baseline; one new warning I introduced was fixed) |
| `vite build` | succeeds |
| `alembic heads` / `current` / `check` | `b7e3d91c5a24` / `b7e3d91c5a24` / clean |

## 8. Documentation: old Prompt 13/13A/13B sections removed

The three sections the 13B report left as historical records and every other place with the same "superseded / was ... now ..." pattern were **deleted and replaced with current-behaviour-only text**:

| Doc | Removed | Replaced by |
|---|---|---|
| `docs/SCOPE.md` | §8 "Prompt 13 Notes", §9 "Prompt 13A Notes" (including the 13B supersession bullets); matrix cell text "Prompt 13A, see §9"; §4.3 pre-lock bullet and lock-boundary bullet wording about the old flow | new §8 "Pre-Lock Cancellation and Business Day Status" (current rules, dated owner decisions); new §9 "Reference Ranges Versioned by Sex and Age Band (D24)"; matrix and §4.3 rewritten; the "dynamic versioning is deferred" note replaced |
| `docs/API.md` | §8 "Prompt 13", §9 "Prompt 13A", §10 "Prompt 13B" and the chained count history | new §8 (current cancellation/refund/business-day endpoints) and §9 (reference range endpoints); header 106 / 120 |
| `docs/DESIGN.md` | §16 "Prompt 13 UI", §17 "Prompt 13A UI", §18 "Prompt 13B UI" | new §16 (current cancellation, disbursement and business-day UI) and §17 (reference range UI) |
| `docs/WORKFLOWS.md` | §11 "Prompt 13" diagram (with its update banner), §12 "Prompt 13A", §13 "Prompt 13B"; the table row for "Request Cancellation" | new §11 (pre-lock vs D15, then disburse; business-day indicator) and §12 (reference range versioning); table row corrected |
| `docs/ARCHITECTURE.md` | wording that kept the superseded flows inside ADL-005 and ADL-058 to ADL-066 ("Prompt 13A supersedes...", "Superseded by ADL-065", etc.) | ADL-058 to ADL-066 rewritten to current truth (same ids); new ADL-067 (versioned bands) and ADL-068 (selection and snapshot) |
| `docs/DATABASE.md` | "Prompt 13 / 13A / 13B - Reviewed, No Schema Change" sections | "Reference Range Versions" section (table, relationships, migration, dev DB result) and "Refund Requests and Cancellation Statuses" (current data rules); head, migration history row, `test_components` and `result_items` entries updated |
| `docs/TESTING.md` | §16, §17, §18 per-prompt verification blocks (including the in-flow payout checklist items) | new §16 (current cancellation/disbursement/business-day verification and owner checklist C-1 to C-10) and §17 (D24 verification and owner checklist R-1 to R-8) |
| `project-context.md` | three separate Prompt 13 / 13A / 13B sections | one current-state section for the cancellation line plus a Prompt 14 section |
| `README.md` | count history chain, phase line | current counts and phase |

Older, unrelated "superseded by" notes (Prompts 09 to 12, e.g. acting-role removal, 10E to 10F sample rule) are legitimate decision-log history for decisions still in force and were left alone. Past reports (`report/`) were not edited.

## 9. Noticed, not fixed

- `visits.age_days` (a rough float from the 365/30 rule) is now unused by banding; it is left in place.
- The demo ranges are single any-sex/any-age bands (version 1). Components such as hemoglobin therefore show one range for everyone until the owner adds real bands.
- Probe tests (`P14_...`) accumulate in `medscope_test` like the earlier probe tests (not part of this prompt).
- Frontend behaviour is checked by `tsc`/`vite build` and code review only (no frontend test runner, no browser run).
