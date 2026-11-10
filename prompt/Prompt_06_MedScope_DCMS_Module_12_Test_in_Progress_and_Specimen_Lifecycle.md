# **Prompt 06 — MedScope DCMS: Module 12 — Test in Progress & Specimen Lifecycle**

## **1\. Project Context**

Continue the existing MedScope Diagnostic Center Management System (DCMS) implementation.

**Current accepted baseline:**

* Prompts 01–04: Previously accepted Receptionist Portal and related workflows.  
* Prompt 05: Test Catalog readiness (Module 5), Laboratory Task Routing (Module 10), and Technician Worklist (Module 11).  
* Existing technology stack:  
  * Frontend: React 19 \+ TypeScript \+ Vite  
  * Backend: FastAPI \+ Python  
  * Database: PostgreSQL \+ SQLAlchemy 2.x  
  * Migrations: Alembic

Before making changes, inspect the actual repository state, current implementation, project handoff, and all nine canonical project documentation files. Treat the current source code and documentation as the implementation baseline. Do not assume that a previous agent report proves a feature is implemented correctly.

## **2\. Phase Objective**

Implement **Module 12 — Test in Progress** from `DCMS Final Scope V1.docx`.

The purpose is to track every sample and every operational step from specimen collection through test processing.

This phase must extend the existing Prompt 05 workflow rather than replace or redesign it.

Implement only Module 12 scope. Do not start Module 13, 14, 15, or 16 as separate modules.

## **3\. Mandatory Restrictions — DO NOT TEST**

**Absolutely DO NOT run any tests or testing activities.**

Prohibited activities include:

* Pytest or any other automated backend tests.  
* Playwright, Cypress, Selenium, or browser automation.  
* Unit, integration, API, E2E, regression, or manual tests.  
* Starting a testing server or browser session for verification.  
* Creating test data or changing existing records for testing.  
* Running test suites or test commands.  
* Asking another agent to perform testing.

Do not claim that anything has passed testing.

### **Regression review is still mandatory**

Perform a **static regression review only**:

* Inspect the affected source files and their dependencies.  
* Review diffs for unintended changes to existing workflows.  
* Trace existing frontend/backend code paths without executing them.  
* Check that existing API contracts, permissions, database relationships, and business rules remain compatible.  
* Identify possible regressions and unresolved risks in the final report.

Do not execute tests to perform this review.

Do not run build, typecheck, migration, seed, or other validation commands unless the user explicitly authorizes them later.

## **4\. Existing Workflows That Must Remain Intact**

Preserve all previously accepted functionality, including:

### **Patient and Receptionist Workflows**

* Patient registration, search, and patient identity handling.  
* Receptionist dashboard and patient intake.  
* Prescriber and referrer selection.  
* New Invoice workflow and invoice preview.  
* Test selection and duplicate-line prevention.  
* Discount calculations and synchronized percentage/Taka inputs.  
* Invoice confirmation and payment collection.  
* Invoice search, history, and payment-status filtering.  
* Invoice printing and duplicate reprint audit.  
* Business Day opening and closing permissions.  
* Refund request and approval workflow.

### **Prompt 05 Laboratory Workflows**

* Test Catalog configuration and active/inactive filtering.  
* Individual TestOrder creation for each confirmed invoice test line.  
* Department and performing-role-based routing.  
* Doctor-required test routing to AWAITING\_DOCTOR.  
* Urgent/STAT priority preservation.  
* Assignment and reassignment history with mandatory reasons.  
* Patient Clock and Laboratory Clock.  
* Technician My Work (`/worklist`) screen.  
* Technician-specific task visibility.  
* Strict financial-data separation for technicians.  
* Existing Quick Route Sample Taken action and its timestamp/audit behavior.

**Do not break, remove, rename, or silently alter existing accepted functionality.**

The development role switcher must remain available. Production authentication/RBAC is still outside this phase.

## **5\. Module 12 Functional Requirements**

### **5.1 Sample Barcode Label Generation and Printing**

Implement barcode label generation for every collected sample.

Requirements:

* Every sample must have a unique sample identifier.  
* Generate a printable barcode label associated with the correct sample and TestOrder.  
* The barcode must identify the sample, not merely the invoice or patient.  
* Scanning a sample barcode should locate and open the corresponding task directly, consistent with Module 11\.  
* Support the existing Quick Route and the planned Full Route collection workflow.  
* Offline-created labels must use the temporary sample ID specified by the project scope.  
* Preserve the relationship between temporary and permanent identifiers during synchronization, if the existing offline architecture supports it.  
* Avoid duplicate sample IDs or duplicate collection events.  
* Do not expose financial information on barcode labels.

Inspect the current printing architecture and existing printer conventions before implementation. Keep the label layout practical for diagnostic-center barcode printers.

### **5.2 Sample Taken — Line Lock and Stock Event**

The Module 12 workflow must respect the scope's sample-locking rule.

At the Sample Taken event:

* Lock the corresponding invoice test line against ordinary cancellation/refund.  
* The lock is per test line, not per invoice.  
* Record the sample-taken event and timestamp.  
* Preserve the existing Patient Clock and Laboratory Clock behavior.  
* Prevent duplicate sample collection events for the same action.  
* Record the responsible staff member and relevant audit information.

**Stock boundary:**

* The scope states that stock is deducted at the sample lock event.  
* Inspect the existing database and stock architecture before implementing this.  
* Do not build the complete Module 16 Stock Management module in this phase.  
* If the required stock ledger/item linkage already exists, implement the appropriate consumption event safely and idempotently.  
* If the required stock infrastructure does not yet exist, do not invent fake stock balances or silently claim that stock deduction is complete. Implement only a properly documented integration boundary and report the dependency as Blocked/Deferred for Module 16\.  
* Never deduct stock twice for duplicate requests or retries.

### **5.3 Spoiled or Rejected Sample Workflow**

Implement a controlled workflow for a spoiled, unsuitable, or rejected specimen.

Requirements:

* Authorized staff must be able to record a rejected/spoiled sample.  
* A rejection reason is mandatory.  
* Record who rejected it and when.  
* Preserve the original sample record and its history.  
* Record the operational status and audit trail.  
* The patient must be marked for contact/call follow-up according to the scope.  
* Do not silently reopen the original invoice line for a free recollection.

Apply the existing D15 rule:

1. A collected sample that is invalid or spoiled follows the **Not Performed** outcome and the prescribed Admin/Owner approval process.  
2. Refund handling must follow the original payment channel and existing refund approval rules.  
3. If the patient agrees to a new collection, a new invoice line and a new sample ID are required.  
4. There is no free re-run.  
5. Stock already consumed must not be silently restored; wastage and stock handling must follow the existing scope and stock architecture.

Do not bypass the existing post-sample cancellation/refund lock. Implement the explicit exception through the authorized workflow only.

### **5.4 Timestamped Operational History**

Every relevant operational step must preserve its timestamp and responsible actor.

At minimum, support the lifecycle events applicable to:

* Sample created.  
* Sample collected / Sample Taken.  
* Sample rejected or spoiled.  
* Test processing started.  
* Imaging performed.  
* Awaiting doctor.  
* Culture incubation.  
* Culture preliminary stage.  
* Culture final stage.  
* Outside-lab sent.  
* Outside-lab received.

Use the existing event/audit architecture where possible. Prefer append-only history over destructive updates.

Do not overwrite previous event history when a task changes status.

### **5.5 Department-Specific Workflow Extensions**

Preserve the common TestOrder workflow while supporting the following department-specific extensions from the scope.

**Imaging**

* Support `Performed`.  
* Support `Awaiting Doctor`.  
* Do not treat imaging as an ordinary sample-based laboratory test when its workflow does not require a specimen.  
* Respect the existing no-sample cancellation/locking rule: the imaging line locks at result completion, not at sample collection.  
* Preserve the existing doctor-routing behavior.

**Culture**

* Support the multi-stage lifecycle:  
  * `Incubating`  
  * `Preliminary`  
  * `Final`  
* Preserve timestamps and responsible actors for stage transitions.  
* Do not force culture tests into an ordinary single-step completion lifecycle.

**Outside Laboratory**

* Support:  
  * `Sent`  
  * `Received`  
* Preserve the external destination/reference information available in the existing model.  
* Do not implement the complete Module 31 outside-lab management module.

Keep these extensions compatible with the common worklist and TestOrder lifecycle.

## **6\. Workflow and State-Transition Integrity**

Review the existing Prompt 05 states before changing anything.

Existing states include:

* ASSIGNED  
* PENDING  
* SAMPLE\_PENDING  
* IN\_PROGRESS  
* AWAITING\_DOCTOR  
* COMPLETED

Preserve existing valid transitions and introduce only the additional states or event records needed for Module 12\.

Important rules:

* A task awaiting sample collection must not be marked operationally completed before the required collection/processing steps.  
* A Sample Taken action must not create duplicate samples.  
* A rejected sample must follow the controlled Not Performed exception workflow.  
* A doctor-required task must not bypass doctor authorization.  
* Imaging, culture, and outside-lab workflows must not be forced into an incorrect generic transition.  
* UI actions must be available only when valid for the current state and actor.  
* Backend transition rules must enforce the same business constraints; hiding a button alone is insufficient.

### **Important correction to the current Worklist behavior**

During manual review of the Prompt 05 Worklist, the user observed that `Complete` is displayed even for tasks still in `ASSIGNED` status with `Specimen Pending Collection`.

Review this behavior as part of the Module 12 state-transition work.

Expected behavior:

* Before Sample Taken, a sample-based task must not offer an ordinary Complete action.  
* After Sample Taken and processing, the appropriate operational actions may appear.  
* Completion must represent the correct operational milestone, not sample collection and not final report publication.  
* Do not let a technician bypass required doctor approval or the rejected-sample workflow.

Correct the UI and backend transition rules consistently, without breaking valid existing worklist actions.

## **7\. Scope Boundaries — Do Not Implement Yet**

The following are explicitly outside this phase:

### **Module 13 — Entering Results and Reports**

* Result value entry forms.  
* Numeric parameter entry.  
* Multi-component profile result trees.  
* Age/sex-based reference-range matrices.  
* Automatic Low/High/Critical result flags.  
* Narrative/imaging report authoring.  
* Culture sensitivity result entry.  
* Final report generation.

### **Module 14 — Draft to Final**

* Doctor authorization/signature workflow.  
* Multi-signature approval.  
* Final report locking and publication.

### **Module 15 — Corrections**

* Report amendments.  
* Addenda.  
* Correction history workflow.

### **Module 16 — Stock Management**

* Full reagent inventory management.  
* Vendor stock replenishment.  
* Complete stock administration and reporting.

### **Instrument Integration**

* Automatic machine/instrument result imports are deferred.  
* Version 1 must not introduce automatic instrument integration.  
* Result-entry functionality belongs to Module 13\.

Do not implement these deferred modules as hidden subprojects inside Prompt 06\.

## **8\. Database, API, and Architecture Rules**

Before changing the database:

* Inspect existing models, relationships, migrations, indexes, and constraints.  
* Reuse existing structures when suitable.  
* Add Alembic migrations only when genuinely required.  
* Make migrations safe and reversible.  
* Preserve tenant isolation and existing tenant data.  
* Avoid destructive schema changes or data resets.  
* Ensure event creation and associated audit records are transactionally consistent.  
* Enforce idempotency for collection, barcode, rejection, and stock-consumption operations where applicable.  
* Preserve existing API response contracts unless a necessary backward-compatible extension is required.  
* Maintain strict financial-data privacy for LAB\_TECH users.

Do not expose invoice totals, prices, discounts, payments, dues, commissions, or reagent cost prices through technician endpoints.

## **9\. UI/UX Requirements**

* Extend the existing MedScope visual system.  
* Preserve the current sidebar, header, navigation, worklist layout, typography, spacing, and color conventions.  
* Do not redesign unrelated screens.  
* Provide clear status labels and valid actions for each workflow state.  
* Show specimen/sample identity clearly.  
* Make rejected/spoiled states distinguishable from ordinary in-progress states.  
* Make barcode labels practical for printing and scanning.  
* Keep operational history understandable to staff.  
* Preserve responsive behavior and existing keyboard usability.  
* Do not use fake buttons or decorative controls without working backend behavior.

## **10\. Static Regression Review — Mandatory, Without Testing**

Before completing the phase, inspect the changes against the accepted baseline.

Review at least:

* Patient registration and search.  
* New Invoice and invoice confirmation.  
* Invoice test-line snapshots and individual TestOrder creation.  
* Payment and refund workflows.  
* Invoice printing.  
* Business Day permissions.  
* Test Catalog and department routing.  
* Technician worklist and technician isolation.  
* Urgent priority and dual clocks.  
* Sample Taken and audit history.  
* Financial-data privacy.

This is a code/documentation review only. Do not run any tests, builds, typechecks, migrations, seed commands, or browser sessions.

Record:

* Files and code paths reviewed.  
* Existing behavior intentionally preserved.  
* Potential regressions identified.  
* Unresolved risks or dependencies.  
* Features marked Done, Partial, or Blocked.

Do not claim runtime correctness or test success.

## **11\. Documentation Updates — Mandatory at Phase End**

Update all affected canonical documentation files and keep the full set consistent.

The nine canonical documents are:

1. `project-context.md`  
2. `docs/TESTING.md`  
3. `docs/DATABASE.md`  
4. `docs/API.md`  
5. `docs/WORKFLOWS.md`  
6. `docs/SCOPE.md`  
7. `docs/ARCHITECTURE.md`  
8. `docs/DESIGN.md`  
9. `README.md`

At minimum:

* Update `project-context.md` with the Prompt 06 implementation record and current phase status.  
* Update `docs/TESTING.md` to explicitly record that no testing or validation commands were executed in this phase.  
* Document any database/model/migration changes.  
* Document new or modified API endpoints and permission rules.  
* Document sample lifecycle, rejection, locking, timestamps, and department-specific transitions.  
* Document any deferred stock dependencies and scope boundaries.  
* Keep README and architecture descriptions consistent with the actual implementation.

Do not claim a document was updated unless it was actually changed.

## **12\. Final Implementation Report**

Create a detailed report named:

`PROMPT_06_IMPLEMENTATION_REPORT.md`

Include:

1. Executive summary.  
2. Module 12 requirements acceptance matrix (`Done`, `Partial`, `Blocked`).  
3. Barcode generation and printing implementation.  
4. Sample collection and line-lock behavior.  
5. Rejected/spoiled sample workflow.  
6. Timestamp and audit-history implementation.  
7. Imaging, culture, and outside-lab workflow extensions.  
8. Database changes and Alembic migration details, if any.  
9. API endpoints and permission changes.  
10. Static regression review findings.  
11. Explicitly deferred Module 13–16 items.  
12. Documentation files updated.  
13. Known limitations and unresolved dependencies.  
14. Testing status: **NOT PERFORMED — explicitly prohibited by the user.**

List the actual modified files.

Do not invent evidence, claim tests passed, or mark unimplemented work as Done.

## **13\. Stop Condition**

Implement Module 12 only.

Do not start Module 13 or any later module.  
Do not automatically proceed to another prompt.  
Do not perform testing.

After implementation and documentation are complete, provide the implementation report and stop. Wait for the user's review and explicit next instruction.

**The user will manually review and decide whether Prompt 06 is accepted.**

