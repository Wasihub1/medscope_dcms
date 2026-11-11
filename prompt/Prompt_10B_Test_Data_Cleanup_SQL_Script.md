# Prompt_10B — SQL Script to Remove Test-Created Records (Run by the Owner in pgAdmin)

You are working on **MedScope DCMS**. Earlier test runs wrote fake records into the owner's main database `medscope_dcms` (patients, referrers, invoices, payments, refunds, test orders, samples, results, audit and reprint logs). Tests no longer touch it (Prompt_08 Part B). The owner does not need these records and will run a full end-to-end cycle later to create fresh data.

**Your job: write ONE SQL script that the owner runs himself in the pgAdmin Query Tool.** No cleanup application, no CLI tool. **You must not run any DELETE, UPDATE or INSERT against `medscope_dcms`.**

Existing leads (unverified; the two reports disagree with each other on counts and patterns): `report/TEST_RECORD_CANDIDATES.md` and `report/PROMPT_08_IMPLEMENTATION_REPORT.md`. Do **not** copy the draft SQL in that report: it uses range filters such as `invoices.id >= 6` that would also delete legitimate QA rows.

## 1. Deliverable

`backend/scripts/sql/cleanup_test_data.sql`, plain SQL that runs as-is in **pgAdmin** (no `psql` meta-commands such as `\set` or `\echo`; use temporary tables, CTEs and `DO` blocks; use `RAISE NOTICE` or result sets for messages).

The script has four sections in this order:

1. **Header comments:** what it deletes, what it protects, and the instruction to take a **fresh pgAdmin backup first** (Backup, custom format). Note that the old `backups/medscope_dcms_pre_prompt08.dump` is **older than the login tables added in Prompt_09** and must not be used to restore.
2. **Configuration + PREVIEW (read-only):** a small temp config table (for example `include_medium`, default `true`), then temp tables holding the exact ids selected per table, then a result set with counts per table and per tier, plus a list of the protected rows that are kept. Nothing is deleted in this section.
3. **DELETE (inside a transaction):** `BEGIN;` then deletions in a safe foreign-key order using only the ids from the preview tables, each step printing the number of rows deleted.
4. **Post-checks, then `ROLLBACK;` as the default last line:** queries proving there are no orphaned foreign keys, protected rows still exist and kept-row counts are as expected. The last statement must be `ROLLBACK;` with a clear comment: *"Review the counts above. To keep the changes, replace ROLLBACK with COMMIT and run the script again."* (This makes the first run a safe dry run.)

## 2. What to delete (evidence rules, never id ranges)

- Read the existing test files to learn the exact patterns they create (patient and referrer name patterns, notes/reasons, fixed transaction reference, sample codes, etc.) and build selection rules from those patterns plus foreign-key children.
- **Tiers:** *High* = unambiguous markers or children of High rows. *Medium* = rows on baseline seed patients created during pytest runs (for example invoices on the baseline patient). With `include_medium = true` both tiers are deleted; with `false`, only High.
- Find **all dependent tables from the database catalog** (`pg_constraint` / `information_schema`), not by hand, so nothing is missed (visits, assignment history, sample events, ledger/drawer rows, commission rows, anything else), and generate a static, topologically correct deletion order. Also handle references without a foreign key (`audit_logs` entity type/id, `reprint_logs`, test-order events).
- Delete audit rows that refer to deleted entities. If it is straightforward, insert one summary audit row `TEST_DATA_CLEANUP` with the counts.
- Scope everything to the tenant `center-seba-01`.

## 3. What must be protected (never deleted)

`staff`, `staff_roles`, `auth_sessions` (the owner's login accounts must survive), the test catalog, test components, destinations/workstations, `business_days` rows themselves, `sequence_counters`, `alembic_version`, the baseline seed patients/referrers/invoices (list them explicitly by reading the database), and **every row not matched by a rule**. Do **not** reset sequence counters (numbering gaps are acceptable).

## 4. Cash drawer / business-day balances

Payments and refunds changed stored drawer and channel balances. First read how the application stores and updates these balances, then make the script recompute the stored balances of the **open** business day from the remaining legitimate rows, using the same rules as the application. **Validate your recomputation method on the current data first** (recomputing from all current rows must equal the stored values); if it does not, do not guess: leave the balances untouched, print a clear warning in the script output and describe the evidence in the report. Do not modify closed business days; if candidate rows sit inside a closed day, list the affected days and figures in the preview and stop that step with a warning.

## 5. Verify the script safely

Create a scratch database from a **fresh `pg_dump` of the main database** (for example `medscope_cleanup_rehearsal`; never restore over `medscope_dcms`), run the script there with `ROLLBACK`, then with `COMMIT`, and report counts before/after, protected rows intact, and that a second run finds nothing to delete. Drop the scratch database afterwards. If the database user cannot create databases, report **Blocked** for this verification and still deliver the script, saying clearly that it was not rehearsed.

## 6. Report extras

In the report give the owner short **pgAdmin steps**: take a backup, open the script in the Query Tool, run it (dry run with `ROLLBACK`), read the preview and the notices, switch to `COMMIT` and run again, and how to restore a backup through pgAdmin if needed. List the counts per table, state which of the two earlier reports' numbers were correct, and list anything uncertain.

## 7. Documentation

Document the script (location, purpose, how to run) in `docs/DATABASE.md` and `docs/TESTING.md`; update `project-context.md`; review the other canonical docs and record that they were reviewed.

## 8. Must NOT do

- Do not run DELETE/UPDATE/INSERT on `medscope_dcms` (SELECT is fine).
- Do not use id ranges as deletion rules; do not copy the earlier draft SQL.
- No new tool, CLI or app code; no schema change; no browser testing.
- Do not change passwords, accounts or credentials (the owner decided to leave them as they are for now), and do not print secrets.
- Do not start Prompt_11 or any other module.


## Permanent project rules (apply to this prompt)

1. **Inspect first.** Read all nine canonical docs (`README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`) and the actual code you will touch. **The code is the truth.** If a doc disagrees with the code, say so in your report and correct the doc.
2. **Browser testing is prohibited** (no Playwright, Selenium, Cypress, Puppeteer, no opening the app in a browser), **except where this prompt explicitly grants a narrow exception**. Never claim browser acceptance; the product owner performs acceptance personally.
3. **Non-browser checks are expected:** `pytest`, TypeScript typecheck (`tsc -b`), lint, build, `alembic heads/current/check`, read-only DB inspection. Report exactly what you ran and the real output. Never write "passed" for anything you did not observe.
4. **Alembic rule.** Any change to a database model/schema requires a matching migration with the correct `down_revision` and a **single head**. Verify the current head before creating anything (last reported head: `a7d834bc912e`; later prompts may have moved it). Never reset, truncate or destroy existing data. If a migration cannot be applied, still create/review it and state the exact remaining action.
5. **Docs rule.** At the end, update **all nine** canonical docs so they are mutually consistent and match the code. If one has no substantive change, verify it and record that it was reviewed. Record every decision from this prompt in the right docs (SCOPE.md for business rules, ARCHITECTURE.md ADL for technical decisions, DATABASE.md, API.md, WORKFLOWS.md, DESIGN.md, TESTING.md). `project-context.md` must show current phase, state, completed work, known limitations, next step. Before finishing, **audit the docs you touched against the code** and fix mismatches.
6. **Report.** Write `report/PROMPT_09_IMPLEMENTATION_REPORT.md` with: Done / Partial / Blocked / Deferred table, files changed, migration/head status (say clearly if no migration was created), API and permission changes, tests added and their **actual** results, docs updated (one line each), remaining limitations, and an explicit statement about browser testing.
7. **Business rules to protect:** whole-taka integer money; payments, refunds, stock, audit, events, results and snapshots are append-only (never rewrite history); technicians never see financial data; keep accepted workflows and existing data.
8. **Owner decisions in force:** automatic LOW/HIGH/CRITICAL/NORMAL result flags are kept and technicians cannot override them; who may open/close the business day and who may physically disburse an approved refund are **not fixed** and will become configurable per customer later (do not change them now); only Admin/Owner approve refunds; self-approval of refunds is blocked by default.
9. **Working tree.** `git status` has previously shown ~15 tracked files as deleted (old prompt/report files and `DCMS Final Scope V1.docx`). Do **not** restore, delete or move them; just list them in the report.
10. **Never** put secrets, passwords or tokens in code, docs, reports, prompts or logs. Do not start any phase or module other than the one in this prompt.
