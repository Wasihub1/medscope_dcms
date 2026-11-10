# DCMS Receptionist Phase — Session Handoff for a New Chat

**Prepared:** 6 November 2026 (Asia/Dhaka)  
**Project:** MedScope / Diagnostic Center Management System (DCMS)  
**Current phase:** Production redevelopment — Receptionist vertical slice  
**Purpose:** This document is a self-contained context handoff. In the next chat, the user will provide only this handoff and Antigravity Gemini's completion report. Do not ask the user to re-upload the earlier scope, audit, prompt, or legacy source files unless the report cannot be assessed without a specific missing artifact.

---

## 1. Instruction to the next assistant

When this handoff and Antigravity's report arrive:

1. Read both completely.
2. Treat this handoff as the agreed business and implementation baseline.
3. Treat the Antigravity report as a claim of what was implemented, not automatic proof that everything works.
4. Compare the report against every mandatory rule and deliverable in this handoff.
5. Identify completed, partial, missing, contradictory, or unverifiable items.
6. Pay special attention to database migrations, Pydantic coverage, business-rule enforcement, interface documentation, seed data, and the instruction that tests were not run.
7. Do not plan the next business module until the Receptionist slice has been reviewed and accepted.
8. Do not assume tests passed. The user explicitly instructed Antigravity not to run tests; the user intends to test the system.

The immediate task in the next chat will be to review Antigravity's completion report and determine what has genuinely been delivered, what needs correction, and how the user should start and manually test it.

---

## 2. Product and redevelopment direction

MedScope is a Diagnostic Center Management System for small-to-medium diagnostic centers in Bangladesh.

The legacy system was developed as:

- Python
- Streamlit
- SQLite
- Raw SQL
- A large monolithic `DCMS V1.py`
- Separate `accounting.py`
- Streamlit session-state-driven workflows

The legacy system is now a behavioral and data-model reference only. The production redevelopment direction is:

- React.js frontend, preferably React with TypeScript
- FastAPI backend
- Pydantic v2 for mandatory API validation and contracts
- SQLAlchemy 2.x typed ORM
- PostgreSQL
- Alembic migrations
- Module-by-module vertical-slice delivery
- Documentation developed together with every interface and database change

The new implementation must not use Streamlit. Legacy Streamlit code should remain temporarily available as a reference until the new slice is accepted; it should not be destructively removed during this phase.

---

## 3. Earlier source material and audit context

Earlier sessions used:

- `DCMS Final Scope V1.md`
- `project-context.md`
- `DCMS_CURRENT_STATE_AUDIT.md`
- Legacy application and SQLite database descriptions
- `Antigravity_Receptionist_Portal_Implementation_Prompt.md`

The current-state audit described the legacy application as an advanced functional prototype/alpha with many working operational workflows. It reported:

- Patient registration and visits
- Billing, discounts, payments, and dues
- Test assignment and laboratory workflow
- Result entry and report versioning
- Report delivery
- Inventory
- Cashier Business Day handling
- Commission
- Double-entry accounting
- Tenant-isolated SQLite databases

However, the audit also contained evidence-quality issues, including impossible line-number references and some overconfident “fully functional” conclusions despite having no automated tests. Therefore:

- Use the legacy audit as orientation, not as unquestionable proof.
- The current production work is a fresh module-based implementation.
- Business rules agreed with the user override conflicting legacy behavior.

---

## 4. Development method agreed with the user

The project will proceed one module/vertical slice at a time.

For each slice:

```text
Business rules
→ Workflow confirmation
→ PostgreSQL schema
→ SQLAlchemy ORM
→ Alembic migration
→ Pydantic schemas and validation
→ FastAPI services and APIs
→ React interfaces
→ Development sample data
→ User testing
→ ADL and interface/database documentation
→ project-context.md update
```

No new module should begin until the current module is complete and reviewed.

The first slice is the **Receptionist Portal**, not merely a metrics dashboard. It includes the Receptionist's connected operational interfaces and workflows.

---

## 5. Confirmed Receptionist capability scope

The Receptionist must be able to:

1. View the Receptionist Dashboard.
2. Search patients and view permitted patient history.
3. Create a new invoice.
4. Create a new patient inside the invoice workflow.
5. Create a basic referrer inside the invoice workflow.
6. Take an initial payment and later due payments.
7. View tests left unassigned after automatic assignment and assign them.
8. Search, view, and reprint old invoices.
9. View patient dues and settle them by taking payment.
10. Initiate an eligible cancellation/refund request before sample collection.
11. Search, print/reprint, and deliver finalized reports.
12. Open a Business Day.
13. Correct permitted fields of their own profile.

The Receptionist must not:

- Close a Business Day
- Reopen a closed Business Day
- Adjust a closed Business Day
- Approve or execute their own refund request
- Write off dues
- Approve payment reversals
- View or edit referrer commission rates or amounts
- View test cost price or profitability
- View owner-only accounting information
- Change their role or permissions

### Critical correction that must not be lost

The final confirmed Business Day rule is:

- **Receptionist can Open Business Day.**
- **Receptionist cannot Close Business Day.**

This overrides any earlier ambiguous summary that grouped Receptionist and Cashier together as both opening and closing the day.

---

## 6. Detailed confirmed business rules

### 6.1 Patient search and history

Receptionist search criteria should include:

- Permanent patient number
- Temporary patient number if supported
- English or Bangla patient name
- Mobile number
- Last four digits of mobile number
- Appropriate approximate matching

Permitted patient history includes:

- Permitted demographics
- Visits
- Invoices
- Tests on invoices
- Paid and due status
- Payment history
- Sample/test workflow status
- Report status
- Report delivery status

The Receptionist must not see commission, test cost, profit, or unnecessary restricted clinical/internal data.

### 6.2 Patient creation

The Receptionist can create a patient without leaving New Invoice.

Minimum fields:

- Name
- Age under the final-scope age rules
- Sex
- Mobile number
- Address containing at least one meaningful word

Bangla and English Unicode must work. Likely duplicates must be detected using relevant patient identity data and shown before creation.

### 6.3 Invoice creation

- A visit is created for the patient's arrival.
- A new invoice begins as Draft.
- Receptionist selects tests through autocomplete.
- Test search supports ID/code, name, short name, alternate name, and department.
- Confirmation assigns a permanent invoice number transaction-safely.
- Unpaid, Partly Paid, and Paid are derived states.
- Historical invoice lines snapshot the applicable test and price information.
- Receptionist may mark tests urgent.
- Commission values must not be exposed.

### 6.4 Discount rule — user correction

The user clarified that “permitted limit” means the **Test Price**, not a separate Receptionist percentage ceiling.

- A line discount cannot exceed that line's applicable Test Price.
- A line may become zero but never negative.
- A bill-level discount cannot exceed the eligible bill subtotal.
- Final payable cannot become negative.
- The backend must enforce the rule regardless of React validation.
- Money in the new schema/API is whole-Taka integer money.

### 6.5 Basic referrer creation

Receptionist can search and create a basic referrer from New Invoice.

Permitted fields may include:

- Name
- Referrer type
- Contact/mobile
- Registration number when applicable
- Specialty or chamber details when applicable

Receptionist cannot access:

- Commission rate
- Commission amount
- Commission rule configuration
- Referrer ledger
- Commission payout

### 6.6 Payments and dues

- Initial and later payments are allowed.
- Partial payment is allowed.
- Due is derived.
- Overpayment is forbidden.
- Only the amount applied to the invoice is persisted.
- Non-cash payments validate transaction/reference values.
- Duplicate references are prevented under the payment rules.
- Payments are append-only.
- Receptionist cannot write off due.
- Receptionist cannot independently reverse a payment.

### 6.7 Automatic and manual assignment

- Confirmed invoice lines create test orders.
- Automatic assignment uses configured department, performing role, and destination/assignee rules.
- If no eligible automatic destination exists, the order remains explicitly Unassigned.
- Receptionist can view the operational Unassigned queue.
- Receptionist can assign an unassigned test to an eligible technician, room, or destination.
- Reassignment of an existing assignment requires the approved reason/history mechanism and cannot silently overwrite history.
- Assignment activity is audited.

### 6.8 Invoice search and reprint

Search supports invoice ID/number, temporary ID where present, patient number/name/mobile, test criteria, and relevant date or Business Day filters.

Reprinting must:

- Show `Duplicate`
- Log actor and time
- Preserve original historical values

### 6.9 Refund request before sample collection — user correction

The user explicitly confirmed:

- Before sample collection, the Receptionist initiates the refund/cancellation request.
- An Admin approves or rejects it.

Required workflow:

```text
Receptionist selects eligible unlocked line
→ enters mandatory reason
→ backend verifies no sample/lock
→ request becomes PENDING_ADMIN_APPROVAL
→ Admin approves or rejects
→ only approval may create refund/reversal records
→ every transition is audited
```

Receptionist cannot approve or execute their own refund. Normal pre-sample refund initiation must be rejected once the line is locked or a sample exists.

Because the Admin portal is outside this phase, the implementation prompt allowed a minimal, clearly separated Admin approval API for manual end-to-end testing, without building the full Admin interface or RBAC administration UI.

### 6.10 Report print and delivery

- Only Final/Authorized reports can be printed for delivery.
- Reprints are logged.
- Delivery is logged.
- If the center's due-hold setting is enabled and test charges remain due, Receptionist cannot release the report.
- Admin/Owner override is required for a held report.
- Restricted financial/commission information must not appear.

### 6.11 Business Day

- Receptionist can view current day status.
- Receptionist can open a Business Day with required opening balances.
- Only one Business Day may be open per center/tenant.
- PostgreSQL enforcement must be concurrency-safe.
- Receptionist cannot close/reopen/adjust the day.
- The Close action must be absent from the Receptionist UI.
- Backend rejection is also required; hiding the button is insufficient.

### 6.12 Own profile correction

The user confirmed that Receptionist can correct their own profile. The implementation prompt used this provisional field boundary:

Permitted:

- Display name
- Mobile
- Email
- Address
- Profile image reference if supported

Not permitted:

- User/staff ID
- Tenant/center
- Role
- Permissions
- Employment status
- Other users
- PIN/password through the general profile form

This field-level boundary was an implementation assumption added to make the requirement actionable. It should be checked against Antigravity's report and confirmed with the user if Antigravity implemented a different boundary.

---

## 7. UI and design baseline

### 7.1 Layout

- React interface
- Uneven Bento Grid tiles, not a uniform card grid
- Responsive desktop/tablet/basic mobile behavior
- Collapsible sidebar
- Hamburger menu
- Expanded/collapsed preference may persist locally
- Accessible keyboard interaction
- Loading skeletons
- Empty/error/retry states
- Stable `data-testid` attributes

### 7.2 Mandatory product palette

| Color | Hex | Primary relevance |
|---|---:|---|
| Persian Orange | `#CF8852` | Primary actions, selected accents, highlights, controlled attention |
| Platinum | `#E8E7E3` | Main background, neutral surfaces, table headers, inputs, separators |
| Dark Moss | `#525333` | Sidebar, navigation, headings, primary text, structural emphasis |

Derived lighter/darker variants may be used for hover, focus, pressed, disabled, and layered surfaces. All derived and semantic colors must be documented. Brand colors must come from centralized tokens, not component-level hard-coding.

### 7.3 Sidebar items

- Dashboard
- Patients
- New Invoice
- Unassigned Tests
- Invoice Search
- Dues
- Reports & Delivery
- Business Day
- My Profile

Do not show Admin, Owner, accounting, commission, staff management, test configuration, or Close Day actions.

### 7.4 Dashboard tiles

Expected tiles include:

- Business Day status/Open action
- Quick Actions
- Current Business Day patients
- Current Business Day confirmed invoices
- Payments collected in the current Business Day
- Outstanding patient dues
- Unassigned tests
- Reports ready for delivery
- Reports held due to outstanding balance
- Pending Receptionist-initiated refund requests
- Recent invoices/activity

Authoritative totals must come from the backend.

### 7.5 Global autocomplete search

Search across permitted criteria:

- Patient ID
- Patient name in Bangla/English
- Full mobile or last four digits
- Invoice ID/number
- Temporary invoice ID where supported
- Test ID/code
- Test name, short name, alternate name
- Report ID
- Sample barcode/ID where relevant to permitted front-desk activity

Requirements include debouncing, keyboard navigation, grouped results, highlighted matches, loading/no-result/error states, safe limits, appropriate PostgreSQL indexes, and no restricted data leakage.

---

## 8. Mandatory design and interface documentation

### 8.1 Design convention

This file must be created before production interface development:

`docs/design/design-convention.md`

It is the authoritative UI convention and must cover:

- Product colors and derived tokens
- Semantic colors
- Typography
- Spacing
- Borders, radius, shadows
- Bento Grid conventions
- Cards, forms, tables, dialogs, drawers, toasts, badges
- Sidebar/hamburger/header/global search
- Buttons and form controls
- Validation/help text
- Loading/empty/error/disabled/blocked states
- Responsive breakpoints
- Accessibility/focus/contrast/keyboard rules
- Icons
- Print layouts
- `data-testid` naming
- Date/time/timezone/number/whole-Taka presentation
- Bangla and English handling

### 8.2 One Markdown file for every interface

Each page, major modal/drawer, print view, or operational workflow interface must have its own `.md` file.

Expected documentation tree:

```text
docs/interfaces/receptionist/
├── README.md
├── dashboard.md
├── global-search.md
├── patient-search.md
├── patient-history.md
├── patient-create.md
├── invoice-create.md
├── referrer-create.md
├── invoice-search-detail.md
├── invoice-print-reprint.md
├── payment-and-dues.md
├── unassigned-test-assignment.md
├── refund-request.md
├── report-search-print-delivery.md
├── business-day-open.md
└── my-profile.md
```

Each interface document must explain the complete interface and workflow without requiring source-code reading. It should include route, purpose, user, entry points, preconditions, fields, data definitions, actions, workflow, diagrams where useful, rules, permissions, validations, APIs, Pydantic models, ORM/tables, state transitions, transaction boundary, UI states, edge cases, audits, print behavior, seed data, `data-testid` values, manual scenarios, limitations, date, and ADL references.

An interface is incomplete if its documentation is missing or stale.

---

## 9. Backend and API baseline

Required backend characteristics:

- FastAPI
- Thin routers
- Business logic in application/domain services
- SQLAlchemy 2.x typed ORM
- Repository/query layer
- Explicit transaction boundaries
- PostgreSQL
- Alembic, not only `create_all()`
- Pydantic v2 for every API boundary
- UTC timestamp storage
- Asia/Dhaka business/presentation timezone
- Structured errors
- Pagination
- Versioned API such as `/api/v1`
- CORS for React development
- Environment-based settings
- No hard-coded credentials or server information

Expected API capability groups:

- Dashboard and global search
- Patients and history
- Referrers
- Test search and invoices
- Payments and dues
- Assignment
- Refund request and minimal Admin approval boundary
- Reports/print/delivery
- Business Day status/open/rejection of Receptionist close
- Own profile

### Pydantic requirements

- Pydantic v2 mandatory
- Explicit request/response/query/filter models
- Cross-field validators
- Field length/range/enums/pattern constraints
- ORM response support via `ConfigDict(from_attributes=True)` where appropriate
- Unknown financial/state-transition fields rejected where appropriate
- No raw ORM objects returned without response schemas
- Bangla Unicode preserved
- Whole-Taka integer API values

---

## 10. PostgreSQL, ORM, and Alembic baseline

The schema should cover only the Receptionist slice and integrity dependencies, likely including:

- Center/tenant boundary
- Current development actors
- Patients
- Visits
- Referrers
- Tests
- Assignment destinations/configuration
- Invoices and invoice lines
- Counters/sequences
- Payments/reversals required for correct balance
- Refund requests and approved refunds
- Test orders
- Sample/lock record needed for refund eligibility
- Report versions/status
- Report delivery
- Business Days and opening balances
- Audit/reprint events

Important integrity expectations:

- Keys, foreign keys, uniqueness, checks, and relevant indexes
- No floating-point money
- Whole-Taka integer money
- Historical invoice price snapshots
- Append-only financial/event records
- Transaction-safe invoice numbering
- At most one open Business Day per center/tenant
- Overpayment protection
- No negative line payable
- Refund eligibility checked against sample/lock
- Audit actor and timestamp
- Consistent center/tenant scoping

The final multi-tenancy strategy was not yet approved. The Antigravity prompt allowed a provisional `tenant_id`/`center_id` boundary, provided the assumption is documented in ADL rather than hidden.

Alembic requirements:

- PostgreSQL baseline migration
- Constraints, indexes, enums, and defaults included
- Safe upgrade/downgrade where possible
- Seed separated from schema except structural reference values
- Alembic operating documentation
- Migration revision recorded in `project-context.md`

---

## 11. Database setup already completed by the user

The user created a local PostgreSQL database based on the earlier instructions and added the `.env` file to the project.

Known configuration intent:

```dotenv
APP_ENV=development
APP_NAME="MedScope DCMS"
DEBUG=true
TIMEZONE=Asia/Dhaka

API_HOST=127.0.0.1
API_PORT=8000

DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_NAME=medscope_dcms
DATABASE_USER=medscope_app
DATABASE_PASSWORD=<USER'S LOCAL PASSWORD — DO NOT REQUEST OR EXPOSE UNLESS CONNECTION DEBUGGING REQUIRES USER ACTION>
DATABASE_SSLMODE=prefer

DATABASE_URL=postgresql+psycopg://medscope_app:<URL_ENCODED_PASSWORD>@127.0.0.1:5432/medscope_dcms

DATABASE_ECHO=false
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800

CORS_ORIGINS=http://localhost:5173
FRONTEND_URL=http://localhost:5173
```

Database facts:

- PostgreSQL host: `127.0.0.1`
- Port: `5432`
- Database: `medscope_dcms`
- Application role/user: `medscope_app`
- pgAdmin registration display name is not part of the connection string
- `.env` must be excluded from Git
- `.env.example` must not contain a real password
- If the password has reserved URL characters, the `DATABASE_URL` password portion must be URL-encoded

The exact password is intentionally not recorded in this handoff.

---

## 12. Sample data and testing instruction

Antigravity was instructed to create an idempotent, development-only seed process with fictional data, including:

- One development center/tenant
- Receptionist and minimal Admin development identities
- 10–15 patients with Bangla/English names
- Shared family mobile examples
- Multiple visits
- Several referrers
- 20–30 tests across departments
- Assignment destinations
- Invoice/payment/due examples
- Assigned/unassigned test orders
- Ready/held/delivered reports
- Pending/approved/rejected refund-request examples where safe
- Business Day example
- Audit/reprint examples

The seed must be safe to rerun and guarded against production execution.

### Testing decision

The user explicitly instructed:

> After implementation, do not run tests. The user will test it.

Antigravity was told not to run:

- Pytest
- Unit tests
- Integration tests
- Playwright/Cypress
- React test runners
- E2E scripts
- Coverage
- Manual browser workflow testing

Allowed setup actions included dependency installation, Alembic migration, PostgreSQL setup, and seed execution.

Therefore, Antigravity's report must say:

`Tests were not run at the user's request.`

Do not interpret this as a successful test result. The delivered system must instead provide start commands, development URLs/identities, reset/reseed instructions, stable routes and `data-testid` values, API examples, and a manual E2E checklist with expected outcomes.

---

## 13. Documentation and tracking contract

The implementation must include:

- Architecture Decision Log (ADL)
- Receptionist module business/workflow/API/database documentation
- `docs/design/design-convention.md`
- One Markdown file per interface
- PostgreSQL schema overview
- Mermaid ER diagram
- Constraint/index rationale
- Relevant SQLite-to-PostgreSQL mapping
- Alembic guide
- Seed guide
- Manual E2E guide
- Updated `project-context.md`

ADL means **Architecture Decision Log** in this project. Entries should contain status, date, context, decision, alternatives, consequences, and affected files.

`project-context.md` must be updated at phase completion with:

- What was implemented
- New repository structure
- Start commands
- Database architecture
- Completed Receptionist capabilities
- Confirmed rules
- ADL references
- Alembic revision
- Seed command
- Explicit testing status
- Limitations/deferred items
- Next discussion point, without starting another module

---

## 14. Antigravity prompt status

The final implementation prompt was prepared and given to the user:

`Antigravity_Receptionist_Portal_Implementation_Prompt.md`

It required Antigravity to implement the complete Receptionist slice and finish with a report containing:

1. Implementation summary
2. Files/directories changed
3. PostgreSQL and migration status
4. Current Alembic revision
5. Seed status and command
6. Backend command/URL
7. Frontend command/URL
8. Development actor/login instructions
9. Manual E2E guide path
10. ADL/database docs paths
11. Design-convention/interface docs paths
12. Environment configuration summary without password disclosure
13. `project-context.md` update summary
14. Limitations/deferred items
15. Statement that tests were not run

The user will bring Antigravity's resulting report into the next chat together with this handoff.

---

## 15. Review checklist for the next chat

When the report arrives, assess at least the following.

### Repository and execution

- Did Antigravity create a separate React/FastAPI implementation?
- Is Streamlit absent from the new runtime path?
- Are exact startup commands present?
- Are environment variables read correctly?
- Is `.env` ignored and `.env.example` safe?

### Database

- Did Alembic create the PostgreSQL schema?
- Is the revision reported?
- Are SQLAlchemy models typed and related correctly?
- Is money integer Taka, not float?
- Is invoice numbering transaction-safe?
- Is one open Business Day enforced safely?
- Are refunds blocked after sample/lock?
- Is tenant/center scope consistently applied?
- Is the seed idempotent and development-only?

### Backend and validation

- Does every endpoint use Pydantic request/response models?
- Are business rules in services rather than routers/UI?
- Are overpayment, discount, due, assignment, refund, delivery, and Business Day restrictions enforced server-side?
- Can Receptionist open but not close a Business Day?
- Can Receptionist initiate but not approve a refund?

### Frontend

- Uneven Bento Grid implemented?
- Required palette used by relevance?
- Sidebar/hamburger complete?
- Global autocomplete covers patient/invoice/test/report criteria?
- Restricted data absent?
- All Receptionist workflows reachable?
- Stable test IDs and manual testing support present?

### Documentation

- `design-convention.md` created before/with interface implementation?
- One complete Markdown file per interface?
- Interface index present?
- ADLs present?
- ER diagram, Alembic, seed, and manual E2E docs present?
- `project-context.md` updated?

### Testing status

- Confirm tests were not run.
- Do not accept any “all tests passed” claim unless the user later authorizes and performs testing.
- Extract the manual testing order and expected outcomes for the user.

---

## 16. Known unresolved or provisional points

These were not fully finalized and may require review after the report:

1. Final multi-tenancy strategy: database-per-tenant, schema-per-tenant, or shared tables with `tenant_id`.
2. The implementation prompt allowed a provisional tenant/center boundary for this slice.
3. Exact own-profile editable fields were made explicit as a practical assumption and should be confirmed if changed.
4. Full Admin UI and full RBAC are deferred; only a minimal Admin approval boundary may exist for refund testing.
5. Other roles and modules remain deferred.
6. The user, not Antigravity, will perform testing.

Do not allow these unresolved items to silently become permanent architecture decisions without ADL documentation and user confirmation.

---

## 17. Durable “do not lose” memory

The following facts are essential for continuity:

- Project: MedScope/DCMS diagnostic-center management system.
- Legacy: Streamlit + SQLite; new production stack is React + FastAPI + PostgreSQL + SQLAlchemy + Alembic + mandatory Pydantic v2.
- Work proceeds one vertical slice at a time.
- Current slice: Receptionist Portal.
- Receptionist can open Business Day but cannot close it.
- Receptionist initiates eligible pre-sample refund; Admin approves/rejects.
- Receptionist discount cannot exceed applicable Test Price; net cannot be negative.
- Receptionist can search/view permitted patient history, create patient/invoice/basic referrer, take payments, settle dues, assign unassigned tests, reprint invoices, print/deliver eligible reports, and correct permitted own-profile fields.
- Commission/cost/profit/owner data are not visible to Receptionist.
- Mandatory palette: Persian Orange `#CF8852`, Platinum `#E8E7E3`, Dark Moss `#525333`.
- UI: uneven Bento Grid, collapsible hamburger sidebar, global autocomplete search.
- `docs/design/design-convention.md` is mandatory from the beginning.
- Every interface must have a complete standalone Markdown workflow document.
- ADL means Architecture Decision Log.
- `project-context.md` must be updated at the end of every phase.
- PostgreSQL local database created: `medscope_dcms`, role `medscope_app`, host `127.0.0.1`, port `5432`; project `.env` has been added.
- Never expose the database password.
- Development seed data is required.
- Antigravity must not run tests; user will test.
- Next chat input: this handoff plus Antigravity's completion report.
- Next chat task: audit the report against this baseline and guide manual startup/testing/corrections; do not start another module prematurely.

