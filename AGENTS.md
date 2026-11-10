# MedScope Agent Instructions

## Mission

MedScope is a multi-tenant diagnostic-center operations application for patient intake, billing, laboratory workflows, reporting, inventory, cashier sessions, referrals, accounting, and platform administration.

Read [project-context.md](project-context.md) before making repository-level changes. Use the existing runtime data and source files; never assume a conventional web framework is present.

## Mandatory repository rules

1. Preserve the current architecture unless a change explicitly requests modernization.
   - Primary application: `DCMS V1.py`
   - Accounting module: `accounting.py`
   - Styling: `theme.css`
   - Custom dropdown: `keyboard_dropdown/index.html`
2. Do not split the monolith or introduce a new framework without an explicit architectural request.
3. Treat SQLite tenant databases and `medscope_data/` as sensitive operational data. Never expose secrets, patient records, PINs, passwords, database contents, tokens, or backup data in responses or source control.
4. Use tenant-scoped database transactions. Never create or query tenant data through the platform database.
5. All persistent destructive or financial actions must be auditable where the application already uses audit records.
6. Preserve existing records and backward compatibility when changing the schema. Initialization must remain safe to run repeatedly.
7. Never reset an existing database, tenant, patient, invoice, sample, result, report, or financial ledger as a shortcut for testing.
8. Never fabricate historical records to make a UI or report appear correct.
9. Prefer small, directly validated changes. Do not rename public UI labels, route/page names, database columns, session keys, or button keys unless the request explicitly requires it and all call sites are updated.
10. Streamlit reruns the full script. Keep widget/session-state behavior deterministic across reruns.

## Before editing

- Locate every use of a changed function, widget key, session-state key, table, column, SQL query, and role check.
- Read nearby code rather than copying an implementation from a distant unrelated screen.
- Check [PERMISSIONS.md](PERMISSIONS.md) before changing navigation or authorization.
- Check schema initialization and additive migrations in `initialize_database()` before changing database fields.
- Backward-compatible changes are preferred: nullable/defaulted columns, additive schema upgrades, and guarded accesses.

## Python and Streamlit conventions

- Use Python and SQLite standard-library features.
- Keep UI functions separate from database mutation when practical.
- Use the existing `database()` context manager for tenant writes and `platform_database()` for platform writes.
- Commit and rollback behavior already belongs to these context managers. Do not open ad hoc tenant connections without a clear reason.
- Enable foreign keys for tenant operations.
- Use `st.session_state` deliberately. Streamlit widget identity must be stable and uniquely scoped to the data record it represents.
- Avoid widget keys that depend only on UI position when duplicate rows or reruns can reorder.
- Include tenant/test/invoice/patient identifiers in state keys where identity matters, not only row index.
- Avoid assigning `value=` and mutating the same widget key in ways that conflict across a rerun.
- Custom component `dropdown()` calls must preserve the expected `selected`, `options`, and session-state contract.
- Keep labels concise and use the project's existing money formatting, notifications, tabs, columns, and button patterns.

## Database and migration rules

- Platform storage: `medscope_data/platform.db`
- Tenant storage: `medscope_data/tenants/<tenant-uuid>.db`
- Never construct a tenant database path before validating the tenant UUID.
- Schema changes belong in `initialize_database()`, accounting schema initialization, or the relevant explicit upgrade routine.
- Use `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and additive migrations.
- For existing columns, inspect the table before `ALTER TABLE`.
- Never change foreign-key constraints, unique constraints, or tables containing financial history by destructively replacing them without an explicit migration plan and backup procedure.
- Preserve audit, payment, refund, sample, result, report, commission, and accounting history.
- Merges that combine records must preserve source history and be reversible when the feature explicitly supports Developer undo.

## Billing and discount invariants

- Gross invoice amount is the sum of selected test prices.
- Each selected test has at most one individual discount mode: percentage or fixed amount.
- Individual percentage discounts are capped by test policy and must never exceed 50% unless the policy is intentionally changed and migrated.
- Individual fixed amount discounts must never exceed the test price.
- Master Discount uses one mode only: percentage or fixed amount.
- Master percentage must not produce a discount above the invoice subtotal.
- Master fixed amount must not exceed the invoice subtotal.
- If Master Discount is active, individual discounts are inactive in calculations but preserved in session state for reactivation.
- Individual line discounts are not the basis for Net Payable while Master Discount is active.
- Persist the discount mode and value consistently to the invoice and invoice-line records, including master versus individual calculation outcomes.
- Verify net, due, payment, refund, accounting, and invoice display values after any discount change.

## Laboratory and report invariants

- `visit -> invoice -> invoice_line -> sample -> result -> report_version -> report_delivery` is the core workflow.
- A result workflow must preserve attribution and state transitions.
- Sample collection, result entry, verification, and authorization should enforce the existing lifecycle rules.
- Cancellation must respect whether a sample has already been collected.
- Report release with an outstanding due requires an Owner/Admin reason according to the current permission model.
- Do not alter historical report versions or deliveries when revising display-only behavior.

## Authorization

- Tenant roles: Owner, Admin, Receptionist, Cashier, Lab Tech.
- Platform Dev is platform-level and distinct from tenant roles.
- Role checks must be enforced in handlers/actions, not only by hiding navigation.
- Consult [PERMISSIONS.md](PERMISSIONS.md) before editing a page's access.
- Platform Dev tenant sign-in attribution must remain visible in the tenant audit trail.

## Validation requirements

Run the smallest relevant check first:

```powershell
python -m py_compile "DCMS V1.py"
python -m py_compile accounting.py
python -m streamlit run "DCMS V1.py" --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

For UI changes:

1. Start Streamlit.
2. Exercise the changed screen with multiple rows and reruns.
3. Confirm duplicate labels, identifiers, button keys, and session keys remain unique.
4. Test both enabled and disabled states.
5. Test the relevant roles.
6. Confirm the database record created or updated.

For schema or billing changes, also verify:

- Existing tenant databases initialize successfully.
- Existing rows receive safe defaults.
- Foreign-key references remain valid.
- Displayed totals match persisted totals.
- Transaction rollback works when a later write fails.

Do not claim UI behavior was verified unless it was actually exercised in a running app or an automated test covers it.

## Sensitive and non-source paths

Do not add runtime data, credentials, patient data, invoice data, SQLite files, backups, secrets, environment exports, browser session artifacts, or generated reports to Git.

Runtime and data paths include:

- `medscope_data/`
- tenant `.db` and `.db-*` SQLite sidecar files
- local virtual environments
- cached Python bytecode

## Completion checklist

Before finishing:

- The change matches the request and does not introduce unrelated refactors.
- Relevant call sites, role checks, schema upgrades, persistence, UI state, and reports are consistent.
- Python syntax passes.
- Existing behavior was exercised or targeted validation was documented.
- No runtime databases or patient/financial data were modified as test fixtures unless the user explicitly requested it.
- Generated temporary files were cleaned up.

