# **Prompt 05 — MedScope DCMS**

## **Test Catalog Readiness, Laboratory Task Routing & Technician Worklist**

Continue development from the currently accepted MedScope DCMS baseline, including Prompts 01–04 and the user's subsequent Invoice Payment Status dropdown fix.

This is an incremental development phase. Preserve the existing application and workflows. Do not redesign or rewrite previously accepted features.

## **1\. Mandatory Instructions**

Before making any changes:

1. Inspect the actual current repository and understand its structure.  
2. Read the project instructions and all nine canonical project documents.  
3. Read `project-context.md`, `docs/TESTING.md`, and the relevant architecture and database documentation.  
4. Inspect the existing Test Catalog, test-related database models, billing confirmation flow, staff/role structure, and current frontend/backend implementation.  
5. Identify which parts already exist and which parts are missing.

**Do not assume that something is missing simply because it is not mentioned in this prompt. Inspect the actual implementation first.**

### **Critical preservation requirements**

Keep all previously accepted functionality intact, including:

* Patient registration and management.  
* Receptionist Portal.  
* Referrer selection.  
* New Invoice and Billing workflow.  
* Discount management and payment collection.  
* Invoice search/history.  
* Invoice printing.  
* Business Day opening and closing workflow.  
* Receptionist-side refund request/status workflow.  
* The recently fixed and documented Invoice Payment Status dropdown.  
* Existing development role switcher.

Do not remove, replace, rename, or unnecessarily modify existing functionality.

If a change to an existing component is necessary, make the smallest possible additive change.

Production authentication and full RBAC remain deferred. Do not treat the existing development role switcher as production authentication, and do not attempt to replace it in this phase.

## **2\. Testing Restriction — Do Not Test**

The user has explicitly instructed that Antigravity must not test.

Therefore:

* Do not run pytest.  
* Do not run Playwright.  
* Do not run unit, integration, E2E, browser, or manual tests.  
* Do not execute test suites or testing commands.  
* Do not initiate a testing server or browser session for verification.  
* Do not spend time creating or expanding test suites in this phase.

You may inspect existing test files if needed to understand the repository, but do not execute them.

At the end, clearly report:

**Testing: Not performed — explicitly instructed by the user.**

Never report tests as passed when they were not run.

## **3\. Part A — Test Catalog Readiness Assessment (Module 5\)**

First inspect the existing Test Catalog implementation.

The catalog is the source of information required for laboratory task routing and future report processing.

Check whether the existing implementation supports the following fields and behavior:

### **Test configuration**

Each test should support:

* Test name.  
* Short name.  
* Alternate names, including English and Bangla spellings written in English letters.  
* Department.  
* Sample type.  
* Report turnaround time.  
* Performing role.  
* Report template.  
* Approval rule.  
* Required stock.  
* Outsourced flag.  
* Active/inactive status.

### **Additional catalog requirements**

Check the existing implementation for:

1. Profile tests containing multiple components.  
2. Reference ranges versioned by sex and age band measured in days.  
3. Historical reference-range preservation for existing results.  
4. Cost price visibility restricted to Owner and Admin.  
5. Test price history.  
6. Bill-line price preservation at billing time.  
7. The four supported report template types:  
   * Numeric table  
   * Narrative (imaging)  
   * Culture and sensitivity  
   * Histopathology  
8. Per-test approval rules:  
   * Technician final  
   * Doctor required  
   * Both signatures  
9. Outsourced test identification.  
10. Starter test-list CSV import support.

### **Important scope limitation**

This is a readiness assessment, not a request to rebuild the entire Test Catalog.

* Preserve existing working catalog behavior.  
* Do not redesign catalog screens.  
* Do not introduce unrelated catalog features.  
* Do not change existing prices, price history, or billing snapshots.  
* Implement only the minimum missing catalog functionality that is genuinely necessary for Modules 10 and 11\.  
* If a missing feature is not required for this phase, document it as a future item instead of expanding the scope.

Provide a concise catalog readiness report in your final implementation report.

## **4\. Part B — Module 10: Splitting the Work**

### **Objective**

When an invoice is confirmed, every test line must become an individual laboratory Test Order and be routed to the appropriate staff member.

The bill itself must never be assigned as one combined laboratory task.

### **4.1 Test Order creation**

When a bill is successfully confirmed:

* Create one Test Order for each eligible test line.  
* Preserve the relationship between patient, visit, bill, bill line, and Test Order.  
* Each Test Order must retain its relevant test, department, performing role, priority, and turnaround information.  
* Ensure order creation is idempotent.

If invoice confirmation is retried, it must not create duplicate Test Orders for the same bill line.

Order creation must respect the existing transaction and error-handling architecture.

Do not create laboratory orders from unconfirmed invoices.

### **4.2 Staff assignment and routing**

Route each Test Order using:

* The test's configured department.  
* The test's configured performing role.  
* The existing staff/role assignment structure.

Do not assign an entire bill to one technician.

A staff member should receive only tasks that match their eligible role and department.

If no eligible staff member is available:

* Do not silently assign the task to an unrelated person.  
* Preserve the Test Order.  
* Keep it in an appropriate pending/unassigned state using the existing status conventions.  
* Make the assignment situation visible to the authorized management role.

If the current system has no suitable status or assignment mechanism, implement the smallest consistent extension and document the decision.

### **4.3 Visiting doctor workflow**

Some tests require a visiting doctor, such as ultrasound.

These tests must enter an **Awaiting Doctor** state until the relevant doctor is available.

Visiting doctors do not need a normal system login for this workflow.

Do not implement the complete doctor approval or report-signing workflow in this phase. That belongs to the relevant later modules.

### **4.4 Urgent priority**

Urgent priority is selected during billing by an authorized receptionist, Admin, or Owner.

* Preserve the existing billing workflow.  
* If urgent priority is not currently available, add a minimal per-test-line priority option.  
* Do not redesign the invoice screen.  
* Carry the urgent flag into the corresponding Test Order and technician worklist.  
* Preserve the priority when a task is reassigned.

### **4.5 Assignment and reassignment history**

Authorized staff should be able to assign or reassign a Test Order.

Every reassignment must:

* Require a reason.  
* Preserve the previous assignee.  
* Record the new assignee.  
* Record who performed the reassignment.  
* Record the timestamp.  
* Keep an assignment history.

Do not overwrite or erase historical assignment records.

### **4.6 Turnaround clocks**

Implement the two clocks described in the project scope:

**Patient clock**

* Starts at bill confirmation.  
* Measures elapsed time from confirmation.

**Laboratory clock**

* Starts when the Sample Taken event is recorded.  
* Measures elapsed time from sample collection.

Use the turnaround time configured for the relevant test.

A test line becomes late when either applicable clock exceeds its configured turnaround time.

The late indicator must be visible in the relevant management and technician views.

If turnaround time is missing or invalid, do not invent a value. Make the configuration gap identifiable.

### **4.7 Sample collection route foundation**

The scope defines two sample collection routes:

**Full route**

* A separate collection step.  
* A collector records the sample collection event.  
* The collection time is recorded in real time.

**Quick route**

* The technician can use a Sample Taken action.  
* The technician may manually edit the sample time.  
* Manual time edits must be recorded in the audit/history mechanism.

The default route should be configurable at center level.

Both routes must create a Sample Taken event because the laboratory clock depends on it.

Important boundary:

This phase must establish the sample-event foundation only. Do not implement the complete Module 12 workflow.

Do not implement barcode label printing, stock deduction, cancellation locking, rejected-sample handling, or instrument-result imports in this prompt.

Preserve the data structure so these features can be added in the next phases without rewriting this work.

## **5\. Part C — Module 11: Technician Worklist**

### **Objective**

Create a technician-facing My Work area where a technician can see and manage only their own assigned laboratory tasks.

### **5.1 My Work screen**

The technician's first work screen should show their assigned Test Orders.

Display the relevant operational information:

* Patient identification and necessary patient details.  
* Test name.  
* Department.  
* Sample type, where available.  
* Assignment status.  
* Current task status.  
* Urgent priority.  
* Late indicator.  
* Relevant timestamps.

Keep the interface consistent with the existing application design.

Do not redesign the overall application navigation or unrelated screens.

### **5.2 Task statuses**

Use the existing status architecture where available.

The worklist should support the applicable workflow states:

* Assigned  
* Pending  
* Sample Pending  
* In Progress  
* Awaiting Doctor  
* Completed

Do not introduce conflicting duplicate status systems.

Status transitions must follow the existing backend/domain architecture. Do not allow a technician to perform actions outside their permitted workflow.

### **5.3 Urgent and late indicators**

* Urgent tasks must be clearly identifiable.  
* Late tasks must have a red late indicator.  
* Late status must derive from the turnaround clocks, not from a manually selected flag.  
* The urgent priority must originate from the billing workflow.

### **5.4 Strict financial-data separation**

This requirement is critical.

Technicians must never see:

* Test prices.  
* Invoice totals.  
* Payments.  
* Outstanding dues.  
* Discounts.  
* Referrer commission.  
* Cost price.  
* Other financial information.

This restriction must be enforced at the backend/API response level, not merely by hiding fields in the frontend.

Technician-specific API endpoints and response schemas must return only the information needed for their operational work.

Do not expose financial fields and assume that frontend filtering is sufficient.

### **5.5 Worklist access boundaries**

* A technician sees their own assigned tasks only.  
* A technician must not access another technician's worklist by changing a URL, request parameter, or API identifier.  
* Preserve the existing development role-switching workflow.  
* Do not implement the low-priority colleague leave-access feature in this phase.  
* Do not implement owner technician productivity reports in this phase.

### **5.6 Barcode navigation boundary**

The scope says scanning a sample barcode should open the corresponding task directly.

However, barcode label generation and printing belong to Module 12\.

For this phase:

* Keep the worklist and task structure compatible with future barcode-based navigation.  
* Do not build a fake barcode workflow.  
* Do not implement barcode generation or printing.  
* Do not expand into Module 12\.

## **6\. Database and Backend Requirements**

Follow the existing architecture:

* FastAPI backend.  
* Pydantic v2 request/response schemas.  
* SQLAlchemy 2.x ORM.  
* PostgreSQL.  
* Alembic migrations.  
* Existing service/domain layer and repository conventions.  
* Existing API versioning and tenant/center boundaries.

Before adding or changing database structures:

1. Inspect the existing models and relationships.  
2. Reuse existing entities where appropriate.  
3. Avoid duplicate or overlapping tables.  
4. Preserve tenant/center isolation.  
5. Use appropriate database constraints for data integrity.  
6. Make migrations safe and consistent with the existing migration history.  
7. Do not modify existing patient, billing, payment, or invoice data destructively.

Use whole-Taka integer money values wherever financial fields are involved. Do not introduce floating-point money calculations.

Persist timestamps in UTC and use Asia/Dhaka for business/display time, following the existing project convention.

## **7\. Frontend Requirements**

* Use the existing React and TypeScript architecture.  
* Follow existing component, routing, state-management, and API-client conventions.  
* Maintain consistent UI styling.  
* Keep the existing Receptionist Portal unchanged except for the minimal urgent-priority addition if required.  
* Build the technician worklist as an additive feature.  
* Handle loading, empty, error, and permission-denied states appropriately.  
* Do not create unrelated dashboards or management screens.

## **8\. Documentation**

At the end of implementation:

* Update all affected canonical project documents.  
* Keep all nine canonical Markdown documents consistent.  
* Update `project-context.md`.  
* Update `docs/TESTING.md`, explicitly recording that testing was not performed because the user instructed Antigravity not to test.  
* Document new database models, relationships, APIs, statuses, routing rules, and configuration changes.  
* Record any deferred requirements and implementation limitations.

Do not claim that documentation is updated unless the actual files have been modified.

## **9\. Strict Scope Boundaries**

This prompt covers only:

1. Module 5 — Test Catalog readiness assessment and minimum necessary prerequisites.  
2. Module 10 — Splitting the Work.  
3. Module 11 — Technician Worklist.

Do not start:

* Module 12 — Test in Progress.  
* Module 13 — Entering Results and Reports.  
* Module 14 — Draft to Final.  
* Module 15 — Corrections.  
* Module 16 — Stock management.  
* Module 17 — Report Handover.  
* Any accounting, commission, refund, or unrelated module.

Do not introduce speculative features or redesign existing workflows.

## **10\. Final Implementation Report**

After completing the implementation, provide a numbered report containing:

1. Test Catalog readiness findings.  
2. Module 10 implementation status.  
3. Module 11 implementation status.  
4. New or modified database models and relationships.  
5. New or modified API endpoints and schemas.  
6. Frontend screens/components changed or added.  
7. Migration files and migration status.  
8. Documentation files updated.  
9. Existing workflows explicitly preserved.  
10. Deferred items and known limitations.  
11. Testing status: **Not performed — explicitly instructed by the user.**

For each requested feature, use one of these statuses:

* Done  
* Partial  
* Blocked  
* Deferred

Do not claim completion for partially implemented features.

Do not begin another module after this phase. Stop after Prompt 05 and wait for the user's review and next instruction.

**Final priority: preserve the accepted Receptionist workflow, implement only this laboratory foundation, and make no unrelated changes.**

