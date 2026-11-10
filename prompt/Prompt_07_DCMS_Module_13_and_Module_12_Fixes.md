# Prompt 07 — MedScope DCMS: Module 13 Result Entry & Report Data + Module 12 Corrections

## 1. Mission

Continue the existing MedScope Diagnostic Center Management System from the current repository state.

Implement:

1. **Module 13 — Entering Results and Report Data**, strictly according to `DCMS Final Scope V1.docx`.
2. The four newly confirmed corrections to the existing Module 12 / Technician Worklist / Specimen Lifecycle / Invoice workflows described in Section 5 of this prompt.

This is a continuation of the existing project, not a rewrite.

**Do not start Module 14 (Draft to Final). Do not implement future modules.**

## 2. Mandatory instructions — follow exactly

### 2.1 Read before changing anything

First inspect the actual repository and read:

- `README.md`
- `project-context.md`
- `docs/SCOPE.md`
- `docs/ARCHITECTURE.md`
- `docs/DESIGN.md`
- `docs/API.md`
- `docs/WORKFLOWS.md`
- `docs/DATABASE.md`
- `docs/TESTING.md`
- The Prompt 06 implementation report, if present.
- The actual source code, models, migrations, endpoints, services, frontend pages, components and existing workflows relevant to Modules 5, 10, 11, 12 and billing/refunds.

Use the repository and current canonical documentation as the implementation source of truth.

Do not assume that an earlier implementation report accurately describes the current code. Verify the actual implementation before changing it.

### 2.2 Browser testing restriction and validation

**DO NOT PERFORM BROWSER TESTING.**

The user has prohibited browser-based testing and will perform manual acceptance testing.

Do not:
- Open or operate the application in a browser for testing.
- Use browser automation, Playwright, Selenium, or other browser-driven UI/E2E testing.
- Perform manual UI acceptance checks on the user's behalf.

This restriction is specifically about browser testing. Do not incorrectly expand it into a blanket ban on all other engineering validation.

You may run appropriate non-browser validation when useful, including:
- Backend automated tests (for example, pytest).
- Non-browser frontend unit/component tests.
- TypeScript typechecks.
- Linting.
- Build commands.
- Static analysis and code-quality checks.

Do not claim a check passed unless you actually ran it and observed its result. Clearly report which checks were run, which were not run, and any failures.

The user will perform browser-based manual acceptance testing.

### 2.3 Collaboration and implementation rules

- Work step by step, but complete the defined Prompt 07 scope before reporting.
- Preserve all previously accepted functionality and workflows.
- Do not redesign or rewrite unrelated pages.
- Do not introduce unrelated enhancements.
- Follow existing architecture, component conventions, API patterns and naming.
- Trace every change end to end: UI → state → API → schema → service → database → response → UI.
- Enforce business rules on the backend, not only by hiding or disabling frontend controls.
- Preserve audit history and append-only financial records.
- Keep existing data safe. Never reset or destructively modify the database.
- Preserve development role switching.
- Do not introduce production authentication/RBAC as part of this prompt.
- Keep technician financial privacy intact.
- Do not expose prices, payments, dues, refunds or commission information to Lab Tech users.
- Do not create fake stock balances or stock movements.
- Do not invent clinical reference ranges, impossible-value thresholds, or business rules that are absent from the source of truth.
- If a requirement cannot safely be completed because a dependency or existing configuration is missing, document it as Blocked or Deferred with the exact reason. Do not fabricate an implementation.

## 3. Module 13 — Result Entry

### 3.1 Objective

Implement result entry for eligible Test Orders.

The system must allow the authorized laboratory staff to enter the correct type of result according to the test's configured result/report template.

Result entry must be connected to the existing Test Catalog, TestOrder, Sample and lifecycle architecture.

Do not create an isolated result-entry system disconnected from the existing workflow.

### 3.2 Numeric result templates

For numeric tests, support report rows containing:

- Component name.
- Result value.
- Unit.
- Reference range applicable on the result date.
- Automatically determined flag.
- Optional comment.

Reference ranges must be taken from the applicable test/component configuration.

Preserve a historical snapshot of the reference range used for each result. Later changes to a test's reference range must never alter an already-entered historical result.

### 3.3 Automatic result flags

Automatically determine:

- LOW
- HIGH
- CRITICAL
- Normal/no abnormal flag, according to existing conventions.

Determine flags by comparing the entered result against the applicable configured reference limits.

Requirements:

- Perform validation on the backend.
- Display the calculated flag in the UI.
- Do not trust a client-supplied flag as the authoritative value.
- Preserve the applicable reference-range snapshot.
- Do not invent or hardcode clinical limits.
- Handle missing or incomplete reference-range configuration safely.
- Do not silently classify a result as normal when the required configuration is missing.

**Important:** Automatic flags are part of this scope. Automatic critical-result notifications/alerts are not.

### 3.4 Impossible-value validation

Implement impossible-value limits to prevent absurd or invalid numeric entries.

Example from the scope: a hemoglobin result of 150 must be prevented where the configured limits make it impossible.

Requirements:

- Inspect the existing Test Catalog and result configuration first.
- Reuse existing configuration if available.
- If impossible-value limits are not represented in the current architecture, introduce an appropriate configurable mechanism consistent with the existing design.
- Do not invent universal clinical thresholds.
- Reject impossible values on the backend as well as in the UI.
- Provide a clear validation message.
- Do not silently clamp, rewrite or accept an invalid value.

There is no previous-result comparison in Version 1. Do not implement previous-result comparison.

### 3.5 Imaging and narrative reports

Support narrative report data containing:

- Findings.
- Impression.
- Comments.

Do not implement image attachment or image-upload functionality. Image attachment is excluded from Version 1.

Preserve existing Imaging lifecycle states from Module 12, including Performed and Awaiting Doctor where applicable.

Do not confuse imaging performed status with result entry or report finalization.

### 3.6 Ultrasound templates

Support structured or partly structured Ultrasound result templates.

Inspect the existing Test Catalog/template architecture and implement this without creating a separate, incompatible reporting subsystem.

The structure must remain suitable for the later Draft-to-Final workflow.

### 3.7 Result authorization and role access

- Preserve the existing assigned-technician and supervisor permission model.
- A Lab Tech must not gain access to another technician's restricted tasks merely because result-entry screens exist.
- Supervisors must retain their authorized access.
- Preserve role-based access on the backend.
- Preserve the technician financial-data restriction.

Respect each test's existing approval configuration.

Do not implement the complete Module 14 approval/finalization workflow in this prompt.

### 3.8 Result status and TestOrder status must remain distinct

Do not treat these as interchangeable:

- Sample status.
- TestOrder operational status.
- Result-entry status.
- Report approval/final status.

Saving or entering a result must not automatically publish a final report.

Do not mark a TestOrder COMPLETED merely because a result form was saved unless the existing, explicitly defined operational completion rules require it.

Do not introduce Module 14 finalization behavior.

### 3.9 Explicit Module 13 exclusions

Do not implement:

- Draft-to-Final workflow.
- Final report locking/version correction workflow.
- Module 14 approval and finalization UI.
- Automatic critical-result notification.
- Previous-result comparison.
- Imaging image attachments.
- Instrument result import.
- New report-delivery or SMS functionality.
- QR authenticity implementation belonging to Module 25.
- Any future module.

Preserve existing integration points where necessary, but do not implement these excluded features.

## 4. Module 13 integration with Module 12

Before implementing result entry, inspect the actual Module 12 lifecycle.

Ensure that:

- Result entry is available only for eligible Test Orders.
- Rejected/Spoiled samples cannot accidentally proceed through ordinary result entry.
- Imaging, Culture and Outside Laboratory lifecycle extensions remain compatible.
- Existing timestamped lifecycle history is preserved.
- Existing TestOrder assignment and permissions remain intact.
- Existing Sample ID and barcode relationships are preserved.

Do not change the meaning of the existing lifecycle states merely to make result entry easier.

## 5. Mandatory corrections from the user's latest review

These are confirmed requirements, not optional suggestions.

### FIX 1 — Remove the Line Lock badge from Technician UI

In Technician Worklist and Specimen Lifecycle screens:

- Do not display the `Line Lock` badge.
- Do not display equivalent unnecessary lock-status decoration to technicians.
- Keep all existing backend line-lock functionality.
- Keep all cancellation/refund restrictions.
- Keep all lock-event and audit behavior.
- Do not unlock a line merely because the badge is hidden.

This is a UI presentation correction only. It must not weaken business rules.

### FIX 2 — Stat Urgent badge must remain until Test Status is COMPLETED

Current issue: the Stat Urgent notification badge may disappear too early.

Required behavior:

- If a TestOrder is marked Stat Urgent, its Stat Urgent notification badge must remain visible while its Test Status is anything other than COMPLETED.
- Sample Taken must not remove it.
- Sample Collected must not remove it.
- IN_PROGRESS must not remove it.
- AWAITING_DOCTOR must not remove it.
- Other intermediate statuses must not remove it.
- Remove the Stat Urgent badge only when the authoritative TestOrder/Test Status becomes COMPLETED.

Derive the badge from the urgent flag and authoritative TestOrder status. Do not maintain a separate frontend-only state that can become inconsistent.

Apply the same rule wherever the relevant urgent notification is displayed in Technician Worklist and related workflow screens.

Do not confuse TestOrder COMPLETED with final report publication.

### FIX 3 — Sample status must automatically update in Invoice View

Current issue: Lab Tech performs Sample Taken/Sample Collected, but the Invoice View does not automatically show the updated sample status.

Required behavior:

- When Lab Tech successfully performs Sample Taken or Sample Collected, the corresponding Invoice View test line must reflect the latest sample status automatically.
- Use the authoritative backend state.
- Update the relevant invoice detail/list state through the existing application data-refresh mechanism.
- If the application uses query caching, invalidate/refetch the correct invoice and related data.
- Avoid stale cached status.
- Avoid duplicate sample events or duplicate collection actions.
- Do not require a user to manually edit the invoice.
- Do not create a separate, conflicting sample status field in the invoice.
- Preserve per-test-line status accuracy when an invoice contains multiple tests.

The status shown in Invoice View must reflect the actual sample associated with that specific invoice line/TestOrder.

### FIX 4 — Correct Rejected/Spoiled Sample D15 Refund Workflow

This is a critical business-rule correction.

#### Current observed problem

Lab Tech records a Rejected/Spoiled Sample, enters the reason and submits a Patient Refund Request.

However, Invoice View still exposes a normal Refund Initiate option. Attempting the refund produces errors such as:

`No eligible uncollected test line found for cancellation refund.`

and:

`Specimen REJECTED: Hemolyzed specimen unsuitable for analysis (D15 rule locked)`

The current generic pre-sample cancellation refund workflow is incorrectly handling a post-collection D15 case.

#### Required business behavior

A collected sample that is subsequently rejected/spoiled is not an ordinary uncollected test line.

Implement the D15 exception as a separate, explicit workflow.

**A. When Lab Tech rejects/spoils a sample**

- Require a rejection/spoilage reason.
- Preserve the original Sample ID and all sample/lifecycle history.
- Preserve the actor and timestamp.
- Record the appropriate rejected/spoiled status.
- Record the test outcome as `NOT PERFORMED` under D15.
- Preserve the original sample collection/lock event.
- Do not unlock the invoice line.
- Do not permit the same invoice line to be recollected or rerun.
- Preserve existing stock deduction behavior.
- Consumed stock must not be restored. Record wastage through existing stock/wastage infrastructure where supported.
- Preserve patient follow-up/call recording already implemented in Module 12.

**B. Lab Tech Refund Request**

Lab Tech must be able to submit a D15 Refund Request for the rejected/spoiled test line.

- The request must include the rejection reason and relevant sample/test/invoice references.
- The request must be distinguishable from ordinary pre-sample cancellation/refund requests.
- Create an approval-pending state such as `PENDING_ADMIN_APPROVAL`, following existing naming conventions.
- Do not make Lab Tech an approver.
- Lab Tech must not execute a refund.
- Do not create a payment refund, reversal or cash disbursement merely because a request was submitted.
- Do not unlock the invoice line.
- Do not bypass D15 or D18.

**C. Invoice View behavior**

This is a specific UI correction.

For a locked line with a Rejected/Spoiled Sample under D15:

- Do not expose the ordinary `Initiate Refund` action as if it were an eligible uncollected-line refund.
- Do not allow that generic action to execute against this line.
- Display the sample status: `REJECTED` or `SPOILED`.
- Display the test outcome: `NOT PERFORMED`.
- Display the appropriate D15 refund request status.
- When the request is pending, show `Refund Pending Approval`.
- When rejected by Admin/Owner, show `Refund Rejected` with the recorded reason.
- When approved, distinguish approval from actual refund disbursement.
- Show `Partially Refunded` or `Fully Refunded` only according to actual refund/payment records, not merely approval.

Do not remove or break ordinary pre-sample refund behavior for eligible unlocked test lines.

**D. Admin/Owner approval**

Use the existing refund approval workflow wherever possible.

- Admin/Owner can review the D15 request.
- Admin/Owner can approve or reject it.
- A decision requires the existing reason/audit requirements where applicable.
- Approval must create the appropriate authorized refund processing path.
- The refund must go through the original payment channel.
- Actual refund/disbursement must be recorded separately from approval.
- Approved but not yet disbursed must not be displayed as Fully Refunded.
- Preserve payment/refund append-only rules.
- Reverse the associated commission whenever the line is cancelled/refunded, consistent with the scope.
- Keep all actions auditable.

**E. If the patient agrees to a new collection**

- Create a new invoice line.
- Create a new Sample ID for the new collection.
- Preserve the original rejected sample and its history.
- Do not unlock and reuse the original invoice line.
- Do not create a free rerun.
- Follow existing billing and supplementary-invoice rules.

#### D15 and line-lock integrity

The governing principle is:

**D15 Not Performed is an exception to the ordinary post-lock cancellation/refund prohibition. It is not permission to unlock and reuse the original line.**

Keep the original line locked and preserve its lock event. The D15 workflow must be implemented as an explicitly authorized exception with appropriate audit history.

Inspect existing refund models, services, APIs, invoice actions and approval states before making changes. Reuse the existing financial architecture. Do not create a parallel refund ledger or bypass existing controls.

If the current architecture cannot represent D15 separately, make the smallest safe and consistent schema/API change required.

## 6. Regression and preservation requirements

Perform static regression review only.

Inspect the impact of changes on:

- Receptionist patient and invoice workflows.
- Invoice detail and Invoice View.
- Invoice line locking.
- Pre-sample cancellation/refund requests.
- Existing Admin/Owner refund approval.
- Payment and refund records.
- Commission reversal.
- Technician Worklist and task assignment.
- Sample Taken/Sample Collected.
- Rejected/Spoiled Sample.
- D15 Not Performed.
- Barcode/Sample ID relationships.
- Sample lifecycle history.
- Imaging, Culture and Outside Laboratory workflows.
- Urgent TestOrder handling.
- Technician financial privacy.
- Role permissions.
- Existing routes, API contracts and navigation.

Do not modify unrelated accepted functionality.

## 7. Database, API and implementation integrity

- Inspect existing models and migrations before changing them.
- **Whenever any database model/schema definition changes, create the corresponding Alembic migration and update the migration chain so the new migration is the current Alembic head. This is mandatory; never leave database definitions changed without a matching migration.**
- Ensure the migration has the correct `down_revision`, is consistent with the existing migration history, and does not create multiple unintended heads.
- Review the generated migration carefully; do not blindly trust autogenerated operations.
- Apply/run database migrations only when required for the implementation and safe in the configured development environment. Never reset or destructively modify existing data. If migration execution is unsafe or unavailable, still create and review the migration, make the limitation explicit, and leave clear instructions.
- Keep migration history safe and non-destructive.
- Preserve existing records.
- Keep financial, sample and audit events transactionally consistent.
- Use idempotency where appropriate.
- Prevent duplicate refund requests or duplicate sample collection events.
- Ensure backend authorization for every restricted action.
- Ensure the frontend displays authoritative server responses.
- Preserve existing API compatibility unless a necessary documented change is required.
- Update dependency manifests only if implementation genuinely requires a dependency change.

Do not add unnecessary dependencies.

## 8. Documentation — mandatory

**At the end of every phase, update all relevant project documentation.** This is a standing project rule, not an optional close-out task.

For this Prompt 07 phase, update all nine canonical documentation files:

1. `project-context.md`
2. `docs/TESTING.md`
3. `docs/DATABASE.md`
4. `docs/API.md`
5. `docs/WORKFLOWS.md`
6. `docs/SCOPE.md`
7. `docs/ARCHITECTURE.md`
8. `docs/DESIGN.md`
9. `README.md`

Documentation must accurately reflect:

- Module 13 implementation status.
- Numeric result-entry structure.
- Reference-range snapshots.
- Automatic flag logic.
- Impossible-value validation.
- Imaging/Narrative/Ultrasound result structures.
- Module 13 exclusions and Module 14 boundary.
- Line Lock badge removal from Technician UI.
- Stat Urgent badge lifecycle.
- Invoice sample-status synchronization.
- D15 Not Performed and refund-request workflow.
- Refund approval versus actual disbursement distinction.
- API and database changes.
- Remaining limitations and deferred dependencies.

Do not mark deferred or blocked functionality as Done.

## 9. Implementation report

Create:

`PROMPT_07_IMPLEMENTATION_REPORT.md`

The report must include:

1. Executive summary.
2. Actual repository baseline inspected.
3. Module 13 implementation details.
4. Each of the four mandatory fixes, separately.
5. UI → API → service → database implementation mapping.
6. Modified and newly created files.
7. Migration files added, if any, and their purpose.
8. API endpoints and schema changes.
9. Permission and authorization changes.
10. Static regression review findings.
11. Documentation files updated.
12. Items marked Done, Partial, Blocked or Deferred.
13. Known limitations.
14. Explicit statement that no tests/build/typechecks/migrations/seeds/browser checks were executed, as instructed.
15. Manual acceptance points for the user.

Be precise. Do not claim runtime verification or successful tests.

## 10. Scope boundary and stop condition

Prompt 07 includes:

- Module 13 Result Entry.
- The four Module 12/UI/Invoice/D15 corrections in Section 5.

Prompt 07 does not include:

- Module 14 Draft-to-Final.
- Final report authorization/publication.
- Module 15 Corrections.
- Module 16 full Stock Management.
- Module 25 QR implementation.
- Instrument integrations.
- Offline architecture implementation.
- Any unrelated module.

When the defined work and documentation are complete, stop.

Do not begin Module 14 or prepare/execute Prompt 08.

Return the implementation report and wait for the user's review and manual acceptance instructions.
