# Prompt 19 — Module 23 (Full Audit Trail): Discovery & Gap Analysis

**Type: investigation only. Do not implement, do not change behavior, do not touch the schema.**

## 0. Context

Module 23 (Audit) is the last of the two originally-flagged BIG gaps in this project (the other, full Accounting/Day Close, was substantially closed by Prompts 18/18B). Per the module-coverage dashboard, M23 currently sits at "scattered audit records; full coverage / report-view logs / export pending" — meaning pieces of audit-like logging already exist (added incidentally in several earlier prompts), but nothing was ever built as one coherent Module 23.

The spec for M23, from the master context, is:

> Rows: user, acting role, time, action, before, after (bills, discounts, payments, reports, stock, accounting, settings, permissions). Immutable even for vendor. Report-view logging; vendor session log; viewing audit is a separate permission; kept forever.

and, from the cross-cutting rules section:

> Audit rows: who, acting role, when, what, before, after — for bills, discounts, payments, reports, stock, accounting. Nobody (incl. vendor) can delete. Kept indefinitely (D61).

Before any build prompt is written, we need an honest inventory of what already exists vs. what's actually missing — the project's own history (Prompts 12, 13, 15, 16, 17) shows that assumed premises about existing behavior are often wrong once someone actually reads the code. Do not assume the small `/audit-log` viewer (Prompt 11) or any per-feature audit write (e.g. the `UPDATE_REFERRER` audit entry from Prompt 19/18C, the `ReprintLog`, the day-close variance history, write-off records, doctor-approval snapshots) is either complete or absent — check each one directly.

## 1. What to investigate

For each item below, report what you actually find in the repository — table names, columns, where it's written from (which service/endpoint), and whether it matches the spec. Do not guess from naming conventions; read the code and, read-only, the `medscope_test` schema if useful.

1. **Inventory every existing audit-like write mechanism.** List each one found (e.g. the Prompt 11 `audit_log` table/viewer, `ReprintLog`, `business_day` variance-by-staff history, doctor-approval snapshot fields, write-off records, the `UPDATE_REFERRER`/`DELETE_REFERRER` entries, soft-delete reason fields, anything else). For each: what columns it has, whether it captures who + acting role + when + action + before/after, whether it's genuinely immutable (no UPDATE/DELETE path at the DB or ORM level), and whether it's the *same* table/mechanism as the others or a separate one-off.
2. **Coverage by domain**, against the spec's list — bills, discounts, payments, reports, stock, accounting, settings, permissions: for each domain, does *any* mutating action currently get logged anywhere, and if so by which mechanism from item 1? Call out domains with zero coverage explicitly.
3. **Report-view logging.** Does opening/viewing a finalized report get logged anywhere today? (Expected: no — confirm.)
4. **Vendor session log.** Does a Vendor role/session concept exist in the codebase at all yet? If not, say so plainly rather than inventing a partial answer.
5. **"Viewing audit is a separate permission."** What permission key currently gates the `/audit-log` viewer? Is it distinct from general admin/owner access, or just folded into an existing role check?
6. **Immutability and retention.** For each mechanism in item 1: can a row ever be updated or deleted through any code path (including cascade deletes, admin tools, or test-cleanup scripts that might touch the same tables)? Is there any TTL/purge/archival logic anywhere that would conflict with "kept forever"?
7. **Fragmentation assessment.** Based on items 1–6, is this project looking at (a) one audit mechanism that needs extending to uncovered domains, or (b) several incompatible one-off mechanisms that would need consolidating onto a single real audit log? State your own assessment plainly — this is the key input the next (build) prompt needs.

## 2. What NOT to do

- No schema changes, no Alembic migration, no new tables/columns.
- No new endpoints, no new permission keys, no UI changes.
- No refactor of any existing mechanism found in item 1 — observe and report, don't fix, even if something looks clearly wrong.
- No doc edits (`docs/*.md`, `README.md`, `project-context.md`) — this is a findings report, not a change to current truth.
- No `pg_dump`/backup needed — nothing is being migrated.
- No browser testing — there is nothing new to click.
- Do not touch the master context file, ever.

## 3. Deliverable

A single written findings report (same report format as previous prompts: numbered sections, Done/Partial/Blocked-style framing isn't needed since nothing is being built — use Found / Partial / Missing per item instead). It must end with a short, direct recommendation: whether Module 23 should be built as (a) an extension of one existing mechanism, (b) a consolidation of several into one, or (c) something built fresh alongside the old ones with a migration path — plus a rough list of what the real build prompt (19B) will need to decide (e.g. retention enforcement, export format, which domains need new instrumentation vs. already have it).

No code diff is expected back — just the report, saved and returned the same way implementation reports have been.
