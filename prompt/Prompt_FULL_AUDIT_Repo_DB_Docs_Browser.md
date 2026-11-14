# Prompt: Full Read-Only Audit — Repository, Database, Docs, and Live App

## Context
This is MedScope DCMS. A previous chat session (not this one) tracked progress through Prompt 10B and Prompt 11, but received no confirmed report back for either. No code, database, or browser inspection has actually happened from that chat — everything there was based on Antigravity's self-reported claims. The owner (Tanzil) is now running this prompt himself via Claude Code, which has real access to the repo, the database, and a browser. This prompt's job is ONLY to look and report — not to fix, not to change, not to assume anything from prior reports is true until verified here.

## Scope — READ ONLY, NO EXCEPTIONS
- Do NOT modify, create, or delete any file in the repository.
- Do NOT modify, insert, update, or delete any row in any database (`medscope_dcms` or `medscope_test`). Every DB query must be a pure `SELECT` (or read-only equivalent). If you need to check migration state, use read-only commands (`alembic current`, `alembic history`), never `alembic upgrade/downgrade`.
- Do NOT run `git` commands that change state (no `add`, `commit`, `checkout`, `restore`, `stash`, `reset`, `rm`). Read-only git only (`status`, `log`, `diff`, `show`).
- Playwright is permitted but READ-ONLY interactions only: navigation, login with existing test accounts, viewing pages/modals, taking screenshots. Do NOT create, edit, submit, or delete any record through the UI (no new invoices, no result entry, no refund actions, no deletes). If a check would require a write action to verify, SKIP it and note it as "not verifiable read-only" rather than performing the write.
- Do not touch the ~15 tracked files that show as deleted in `git status` — only report their names.
- Do not touch `master_context_all_harness.md` / the master context file.

## What to check

### A. Repository state
1. Current git branch, current commit hash, and full `git status` output (staged, unstaged, untracked, and the deleted-but-tracked files).
2. Current Alembic head revision (`alembic current`) and whether it matches a single head (`alembic heads` should show exactly one). Compare to the expected head `b9e41d82f05a`.
3. Confirm Prompt 10B outcome: does `backend/scripts/sql/cleanup_test_data.sql` exist? Does it look like it was ever run (e.g. any log, comment, or commit referencing it)? Report file contents summary, don't execute it.
4. Confirm Prompt 11 outcome: has any soft-delete code (delete endpoints, confirm dialogs, `is_deleted`/`deactivated` style columns) been implemented anywhere in the codebase, or is it still unimplemented?
5. Run the project's own non-browser checks exactly as the existing standing rules specify: `pytest` (against `medscope_test` only — confirm the test suite's own DB guard refuses the main DB before running), `tsc -b`, oxlint/lint, frontend build. Report pass/fail and real counts — do not estimate.
6. Confirm whether `selectDevRole` or any dev-role-switcher code still exists anywhere (it should have been fully removed in Prompt 09).
7. Check `frontend/e2e/test_modal_regression.spec.ts` — does it still reference `selectDevRole`? Does it currently pass or fail if run (read-only Playwright is fine for this, since these are the pre-approved regression specs from Prompt 08)?

### B. Database state (read-only queries only)
1. List of tables (confirm ~25 domain tables as last reported, note any drift).
2. Row counts for: patients, visits, invoices, test orders, samples, results, payments, refunds, audit/event log table, users/login table. Just counts — do not dump PII.
3. Confirm the 4 known login accounts still exist (`reception_fatima`, `admin_tariq`, `tech_kamal`, `tech_nasrin`) and their role assignments, including whether `CASHIER` role is actually present and whether any backend permission-check code actually references/guards on `CASHIER` (this was flagged as unverified).
4. Spot-check: do any obviously test/QA-looking records exist in `medscope_dcms` (the main DB) still, e.g. names/patterns matching what Prompt 08's `TEST_RECORD_CANDIDATES.md` identified? Just report counts/patterns, do not delete anything.
5. Confirm whether business-day / drawer / channel balance tables show any staleness (as flagged: deleting test payments/refunds would leave these stale) — just report current state, do not reconcile.

### C. Docs vs code audit
1. For each of the 9 canonical docs (`README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`): confirm it exists, note its last-updated indicator if any (git log date), and flag any claim in it that visibly contradicts the current code — in particular:
   - `docs/DESIGN.md` narrative fields claim ("technique, findings, impression, recommendations") vs actual code fields (findings, impression, comments) — confirm which is true now.
   - API path/operation counts in `docs/API.md` vs actual route count in code (last reported: 69 paths / 79 operations).
   - Domain table count in `docs/DATABASE.md` vs actual DB table count.
2. Report any other material mismatch you find between a doc's stated behavior and the actual implementation, even if not listed above.

### D. Specific unresolved risk items — verify each one directly in code
For each item below, state clearly: CONFIRMED PRESENT / CONFIRMED ABSENT / COULD NOT VERIFY, with the file/line or query that shows it:
1. `prefers-reduced-motion` handling — was it actually removed from the landing/login animation code?
2. Do any committed files (reports, scripts, config) contain a plaintext DB connection string with password, or a hardcoded dev login password? List file paths only — do NOT reprint the secret values in your output file.
3. Result-entry guard logic — does it check `sample.status != "COLLECTED"` in a way that would also wrongly block valid later states (e.g. culture incubating, outsourced sent/received)? Quote the actual guard condition.
4. D15 refund logic — does refund approval add the line's full net price to `refund_due` regardless of how much was actually paid on the invoice? Quote the actual calculation code.
5. Invoice numbering — confirm whether deleting/cleaning test invoices would leave gaps (i.e., is invoice number a simple auto-increment with no reuse/compaction)?

### E. Live app check (Playwright, read-only only)
1. Load `/` and `/login` — confirm pages render, no console errors, screenshot each.
2. Log in as each of the 4 existing accounts, confirm successful login and landing route, screenshot the post-login view, then log out. Do not create/edit/delete anything.
3. Confirm 390px width shows no horizontal scroll on `/` and `/login` (resize viewport, screenshot).
4. Confirm `/abc` shows the branded 404.
5. From Invoices (if any invoices already exist) open one in view mode and click "Patient History" — confirm the modal opens without a URL/route change. Do not submit any form. If no invoices exist in the DB to test this with, state that clearly rather than creating one.

## Output
Write ONE file: `report/FULL_AUDIT_REPORT_<today's date>.md`. Structure it with the exact section headers A–E above. For every single checked item, state a clear verdict (Confirmed / Not confirmed / Contradicts prior report / Could not verify) — no vague language, no assumptions carried over from old reports. Where this audit contradicts something previously reported as "Done," say so explicitly and show the evidence (file path, query, or screenshot reference). Include the git commit hash and timestamp of this audit at the top of the report.

## Must NOT do
- Must NOT modify any file, database row, or git state.
- Must NOT perform any write/create/submit/delete action through the browser.
- Must NOT run `alembic upgrade`, `alembic downgrade`, or any migration.
- Must NOT run or execute `cleanup_test_data.sql` or any other SQL script.
- Must NOT touch the master context file.
- Must NOT start any new module or write any new feature code.
- Must NOT print secret values (passwords, connection strings) in the output report — reference file paths only.
- Must NOT restore, delete, or move the ~15 tracked-but-deleted files — only report their names.
