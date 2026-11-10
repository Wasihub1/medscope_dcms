# MedScope DCMS — Master Session Handoff

**Prepared:** 7 November 2026 (Asia/Dhaka)  
**Project:** MedScope / Diagnostic Center Management System (DCMS)  
**Working mode:** ChatGPT is the user's ongoing product/architecture/QA partner; **Antigravity** is the repository implementation agent.  
**Current checkpoint:** Receptionist Portal — Prompt 04 corrections completed and reported; user subsequently corrected the **Invoice Payment Status dropdown**, confirmed it is **fixed and documented**, and says the **remaining development is okay**. The user wants to add more features/changes **in the next session**, not now.  
**Important:** This is a *self-contained continuity document*, not an independently inspected source-code audit or an instruction to redo accepted work.

---

## 1. Instructions to the next ChatGPT session — READ FIRST

1. Treat this document as the current project handoff and collaboration baseline. **Do not ask the user to repeat the earlier history or upload the original handoff/chat logs solely to understand the project.**
2. Recognize the user's most recent decision: the **Invoice Payment Status dropdown issue is fixed and documented**; **all other development is considered okay by the user for now**. Do not re-open earlier speculative gaps as active defects without new user evidence. The user will specify additional changes in the next session.
3. On receiving new requirements, help clarify ambiguous business behavior **only where necessary**, finalize the decisions, then prepare a precise, numbered English implementation prompt for Antigravity, generally with a downloadable `.md` artifact if requested.
4. Continue prompt numbering from **Prompt 05** (Prompts 01–04 were earlier phases; Prompt 03 and Prompt 04 are well documented below). Never silently reset numbering.
5. For every Antigravity implementation prompt, require **end-of-phase updates to all affected canonical project documents**, with `project-context.md` and `docs/TESTING.md` explicitly updated. Require an actual implementation/evidence report, not vague assertions.
6. Maintain all accepted workflows and visuals; prefer incremental changes over redesigns. Use the real repository state and documentation as source of truth for implementation details; Antigravity claims and reports are not the same as independent source verification.
7. **Do not initiate a new module, bug-fix campaign, or large audit on your own.** The user will give the next set of additions. Do not write Prompt 05 until the user asks for it or describes the changes to be included.
8. Current development includes a **dev role switcher**; production login and full RBAC remain deferred. Do not remove the switcher until the user elects to replace it.
9. Tests: The **original no-tests restriction was superseded**. Since Prompt 03/04 the user allows and expects Playwright E2E and relevant backend tests as part of verification. Report actual commands, results and limitations.
10. Keep sensitive local credentials out of prompts, documentation, logs, reports and chat. Never expose or request a database password unless strictly needed for a specific debugging step.

### The user's most recent message, controlling this checkpoint

> “ami kichu change korsi, invoice payment status dropdown e, ekhon fix hoise, ar documented hoise, ar baki development gulo thik ase, aro kichu addd korte hobe, seta porer session e korbo.”

**Meaning:** The user made changes to the Invoice Payment Status dropdown; it is now fixed and documented. They accept the rest of the development as okay at present and plan to add more requirements next time. The exact code change, dropdown options, and document section were **not provided in this conversation**, so do not invent them. In a future implementation task, have Antigravity inspect the actual files for exact current behavior.

---

## 2. Product purpose and technology baseline

MedScope DCMS is a Diagnostic Center Management System intended for small-to-medium diagnostic centers in Bangladesh. It handles front-desk operations, laboratory investigations, payments, report delivery, business-day processes and connected administrative/financial workflows.

### Legacy reference (not new production runtime)

- Python, Streamlit, SQLite and raw SQL; main monolith `DCMS V1.py`, separate `accounting.py`, Streamlit session state.
- Earlier audit described patient visits, billing, discounts, payments/dues, test assignment, result entry/report versioning, inventory, business days, commissions, double-entry accounting and tenant-isolated SQLite databases.
- The legacy audit was **orientation**, not infallible proof (earlier evidence-quality and test-coverage concerns). Existing legacy files should not be destructively deleted solely because a new slice is built.

### Modern production implementation

| Layer | Agreed approach |
|---|---|
| Frontend | React with TypeScript; current report says React 19 / Vite 8 |
| Backend | FastAPI, thin routers, service/domain layer |
| Validation/contracts | Pydantic v2 for requests, responses and filters |
| Data access | SQLAlchemy 2.x typed ORM and repository/query approach |
| Database | PostgreSQL, tenant/center-scoped data |
| Schema changes | Alembic migrations, reversible where safe |
| Money | **Whole-Taka integer** persisted/API values; never floating-point money |
| Timestamps | UTC persisted, Asia/Dhaka business/display timezone |
| APIs | Versioned e.g. `/api/v1`, structured errors, pagination, CORS config |
| Verification | Pytest as relevant, browser Playwright E2E, real evidence |
| Delivery | Vertical-slice development; documentation with each phase |

**Multi-tenancy:** A provisional `tenant_id` / `center_id` boundary is in place or was permitted; final strategy (shared tables vs schema/database per tenant) was not formally finalized. Record any durable architecture decision in the ADL within `docs/ARCHITECTURE.md` rather than pretending this is settled.

### Known local environment (historical, recheck if changed)

- PostgreSQL development host `127.0.0.1`, port `5432`; database `medscope_dcms`; application user `medscope_app`.
- The user configured a project `.env`; must remain Git-ignored. `.env.example` must not contain real credentials.
- Backend development API intended on port `8000`, frontend Vite on port `5173`.
- Antigravity Prompt 04 report: Windows 10/11, Python 3.14.7, Node.js v22.14.0, PostgreSQL 18, Vite 8.
- Playwright `@playwright/test` v1.58.2 and Chromium were reportedly installed; browser path is local to the agent's Windows machine and **not** a portable installation prerequisite. Dependency declarations and install commands belong in repository docs.

---

## 3. Collaboration method and prompt conventions

The user discusses product needs, workflows and defects in Bangla/Banglish, with English technical nouns. ChatGPT helps interpret requirements, flags meaningful conflicts, and creates complete Antigravity prompts (usually English for execution). Antigravity reads the actual repository, implements, tests, updates docs, and returns a detailed completion report; ChatGPT reviews that report before declaring anything independently verified.

**Standard phase flow:** Business decisions → current-code audit → UI/API/state/validation/service/database changes as required → migration if needed → test data as needed → Playwright + backend checks → update canonical docs → implementation/evidence report → user acceptance/next changes.

**Prompt naming:** `Prompt_05_DCMS_<Short_Description>.md`, then `Prompt_06...`, etc. Include the number in both title and filename; a previous prompt had an accidental numbering omission that the user specifically corrected.

**Default implementation guardrails:**

- First read `README.md`, `project-context.md`, and the nine canonical Markdown documents; inspect actual code before making changes.
- No unnecessary rewrite of acceptable UI; preserve history, real data, routes, working behavior, audit records and print integrity.
- Trace a feature end-to-end: UI → state → API → Pydantic → service → ORM/database → response → UI.
- Enforce business rules server-side; do not rely only on disabled/hidden UI controls.
- Preserve idempotent development seeds and safe migrations; no destructive database reset.
- Maintain stable `data-testid` selectors, negative/error cases and browser navigation tests.
- Update backend `requirements.txt` with runtime/test dependencies as needed; keep frontend `package.json` + lockfile aligned. Verify installation and dependency checks and report results.
- If Playwright is missing, Antigravity installs/configures it **inside its own sandbox**, including browser binaries, without making the user handle setup.
- For new tests, report what actually ran and what remains untested; no fabricated 100%-coverage claims.

---

## 4. Canonical Markdown project control — exactly nine main files

The user deliberately simplified previously sprawling interface/phase documentation into **nine canonical files**. This list should be used for all subsequent implementation prompts:

| File | Purpose |
|---|---|
| `README.md` | Quick start, commands, project map and document links |
| `project-context.md` | Current state, last phase, known limitations, pending work, phase log, next decisions |
| `docs/SCOPE.md` | Product scope, roles, functional requirements and business rules |
| `docs/ARCHITECTURE.md` | Architecture, integration boundaries and **Architecture Decision Log (ADL)** |
| `docs/DESIGN.md` | UI design conventions, branding, components, interactions, accessibility |
| `docs/API.md` | Endpoint contracts, schemas, errors, role authorization |
| `docs/WORKFLOWS.md` | Screens, UI/API mappings, states, routes, workflows and diagrams |
| `docs/DATABASE.md` | PostgreSQL schema, constraints/indexes, migrations, seeds, ERD |
| `docs/TESTING.md` | Test strategy, manual E2E scenarios, real automated test evidence and gaps |

Keep nonredundant operational files such as `AGENTS.md`, licenses and tool-specific instructions. Do **not** automatically create a separate `.md` for each UI, prompt phase or modal. Old relevant information should be merged into the canonical documents before redundant docs are removed. **Every implementation phase must update applicable documentation and `project-context.md`**, not merely claim that documentation exists.

**Historical note:** The first handoff required many individual interface documents and `docs/design/design-convention.md`. The later Prompt 03 decision **superseded this** with the nine-file canonical structure and `docs/DESIGN.md`. Follow the latest structure, not the original exploded file tree.

---

## 5. Design, UX and global conventions

### Brand palette

- Persian Orange `#CF8852` — primary actions, selected accents, highlights.
- Platinum `#E8E7E3` — background/surfaces/input/table separators.
- Dark Moss `#525333` — navigation/sidebar/headings/structural emphasis.
- Derived/semantic colors belong in centralized tokens, not random hard-coded component colors.

### UI approach

- Responsive uneven **Bento Grid**, not a generic uniform card grid.
- Collapsible sidebar / hamburger, desktop/tablet/basic mobile behavior, proper keyboard/focus handling.
- Loading skeletons, empty/error/retry/disabled states and stable test IDs.
- Global search is **inline in the header**, with anchored autocomplete dropdown, not a modal; `Ctrl+F` focuses app search where appropriate, replacing former `Ctrl+K` app shortcut (without interfering with native print/find contexts).
- Bangla/English Unicode names and meaningful locale formatting; whole-Taka figures; Asia/Dhaka display time.

### Receptionist navigation baseline

Dashboard; Patients; New Invoice; Unassigned Tests; Invoice Search / Diagnostic Invoices; Dues; Reports & Delivery; Business Day; My Profile. The dev role switcher is intentionally retained for testing other role interfaces; this is not production authentication.

---

## 6. Receptionist vertical slice: agreed operations and restrictions

### Receptionist can

- View dashboard and relevant Business Day aggregates.
- Search patients by permanent/temporary IDs where available, Bangla/English name, mobile/last four digits and approximate matches; view permitted visits, invoices, tests, payments, sample/report/delivery histories.
- Create patient inline during invoice entry, with name, age per existing rules, sex, mobile and meaningful address; detect likely duplicates without automatically banning legitimate shared family mobile numbers.
- Search investigations/tests, create invoice, mark urgency, apply full eligible discounts within limits, collect initial or later payment, settle dues, view old invoices, print/reprint invoices.
- Create/select basic Doctor and third-party referrers inline according to latest dual-field rules.
- View unassigned test-order queue; assign eligible technician/workstation/room with audit trail.
- Initiate eligible pre-sample cancellation/refund requests with mandatory reason, subject to Admin approval.
- Search, print/reprint and deliver eligible Final/Authorized reports, subject to due-hold rules.
- **Open** Business Day if valid.
- Edit permitted own-profile fields only (display name, mobile, email, address and supported profile image, as historically provisional boundary).

### Receptionist cannot

- **Close**, reopen or adjust a Business Day (Cashier cannot close either; **Admin/Owner can close**).
- Approve or execute own refund; write off dues; reverse payment without authorization.
- See existing referrer commission rates/amounts/payouts/ledgers, test cost/profit, owner-only accounting data; change own role/permissions/tenant or edit other staff.

### Business integrity rules

- A visit is created for patient arrival. Invoices/lines retain historical test-price snapshots.
- A draft/non-final preview is **not** a persisted confirmed invoice and does not reserve permanent invoice number or book a payment; final save does so atomically.
- Full eligible line discount may reach line price (100%); bill discount may not exceed eligible subtotal; final due cannot be negative. No invented 50% receptionist cap.
- Initial paid amount defaults to **৳0**; no zero-amount payment row; positive payments may be partial; no overpayment; noncash transactions require valid references; payments are append-only.
- Invoice-payment labels agreed in Prompt 04: **Unpaid**, **Partial Due**, **Paid**. **Important new checkpoint:** the user subsequently fixed and documented the **Invoice Payment Status dropdown**; exact choices/filters may have been changed. Treat current repository/docs as authoritative for that dropdown; do not overwrite them with these historical label examples.
- One Business Day open per center at a time, PostgreSQL concurrency-safe.
- Refund request gate: before sample collection or lock → `PENDING_ADMIN_APPROVAL` → Admin/Owner decision → approved refund/reversal records, fully audited. Approved request without actual disbursement must not be presented as paid-out refund.
- Only authorized/final reports can be delivered; configured due-hold requires Admin/Owner override.

---

## 7. Prompt 04 — the 14 finalized corrections (historical accepted baseline)

These are the user-confirmed instructions to Prompt 04. Antigravity reported them **DONE**, and the user subsequently stated the rest of the development is okay. Preserve these behaviors unless the user requests a change.

1. **Prescribed By (Doctor)** and **Referred By (Doctor / Third Party)** are independent fields. Prescriber is Doctor-only; Referred By may be Doctor, Palli Chikitsak, Broker, etc. Both can inline Add; same Doctor can appear in both. New addition can accept commission while stored commission remains invisible to Receptionist.
2. **Business Day Close** available to Admin/Owner only; Receptionist/Cashier may not close. Receptionist can open day. Dev role switcher retained.
3. When a test/investigation is selected, remove it from autocomplete suggestions; if removed from invoice, make it selectable again; avoid accidental duplicate lines.
4. Offer discount by **percentage (%)** and **amount (৳)**, without double-applying or exceeding test/subtotal price.
5. Default initial Paid Amount = **৳0**.
6. **Generate Preview → Back & Correct OR Save [& Print]**; A4 landscape with **Patient Copy** and **Office Copy** side by side. No permanent number/payment booked at preview stage.
7. After **successful final save**, reset invoice entry form but retain saved invoice context for print/reprint; preserve form on failure.
8. Header global search inline; remove search modal.
9. Use **Ctrl+F** instead of Ctrl+K for app search as appropriate.
10. Diagnostic Invoices Print must invoke the actual print flow for the selected saved invoice; print/reprint preserves historical data; reprint marked `Duplicate` and audited once.
11. Historical UI payment labels: **Full Due → Unpaid**, **Partial Paid → Partial Due**, **Paid → Paid**; see newest dropdown caveat above.
12. Opening old invoice from Patient History should not change the background page from Patients to Invoice Registry; closing restores patient history context.
13. Review component props/callbacks and run **real Playwright browser E2E** for navigation/buttons/modal/print/state; fix unintended redirects/wrong records.
14. Show **separate Refund Status** in invoice list/detail: No Refund, Pending, Rejected, Partially Refunded, Fully Refunded, tied to actual request/payment outcomes and appropriate history.

### Explicit removal / out-of-scope issue

The user **deleted an earlier correction #14** that requested investigating the “refund max ৳1 / maximum refundable ৳0” bug. Prompt 04's #14 was replaced with the **refund-status-display** requirement. The agent's report says the amount-limit issue was intentionally untouched. **Do not resurrect the deleted investigation automatically**; it is a known historical deferred issue only if the user raises it again.

---

## 8. Implementation chronology / what happened

### Prior initial phase (Prompt 01 / initial Receptionist vertical slice)

Agreed full Receptionist business scope, production stack, PostgreSQL migration/seed, interface design requirements and documentation. User created local PostgreSQL DB and `.env`. Antigravity was initially instructed **not to run tests**. Its initial completion evidence was not fully established at that early checkpoint.

### Connection audit/fix (prior follow-up, often called Prompt 02)

The user reported that UI looked acceptable but showed **Failed to fetch**. An audit/fix prompt covered API URL, CORS, environment, database connection, migrations and seed. The user subsequently confirmed **data was appearing from the database**, so the connectivity blockage was resolved sufficiently to proceed. Do not infer that every other API worked solely from this.

### Prompt 03 — UI/API Wiring + E2E + Documentation

After data began loading, many UI pages/workflows were still not wired. The user ordered page/detail/action → API → backend mapping and implementation, retained **dev role switcher** until later authentication, required E2E tests and standardized documentation into nine canonical Markdown files. Prompt numbering and `requirements.txt` completeness were specifically reinforced. Its report claimed backend test progress, full discount-cap correction and patient/invoice history links; browser proof/dependency evidence was still questioned at that time.

### Prompt 04 — Final corrections and Playwright verification

Actual file: `Prompt_04_DCMS_Receptionist_Corrections_E2E_Documentation.md`.

Antigravity completion report: `DCMS_RECEPTIONIST_CORRECTIONS_PLAYWRIGHT_REPORT.md`, dated 7 November 2026. It claims:

- **14/14 corrections implemented**.
- **6/6 Playwright Chromium headless browser E2E passed (16.7 seconds)**, in `frontend/e2e/receptionist_corrections.spec.ts`, including inline search/shortcut, close permissions, intake/preview/discounts, invoice list/print/status, patient context, responsive viewport.
- **19/19 backend pytest passed (1.19 seconds)**: 14 earlier tests plus 5 Prompt 04 invariant tests.
- Frontend build succeeded; Python main-file compilation succeeded.
- PostgreSQL Alembic revision **`c94589ffc4ee`**, adding `invoices.prescribed_by_id` FK to `referrers` and index, reportedly applied to head.
- New/updated contracts: `GET/POST /api/v1/referrers`, `POST/GET /api/v1/invoices`, `POST /api/v1/invoices/{id}/reprint`, `POST /api/v1/business-day/close`, refund status in invoice responses.
- UI files mentioned: `NewInvoicePage.tsx`, `DualCopyInvoiceModal.tsx`, `BusinessDayPage.tsx`, `Header.tsx`, `AppLayout.tsx`, `InvoicesPage.tsx`, `PatientsPage.tsx`, `DashboardPage.tsx`, `utils/formatters.ts`.
- Backend files mentioned: `schemas/referrer.py`, `schemas/invoice.py`, `services/invoice_service.py`, `services/business_day_service.py`, `endpoints/referrers.py`, `endpoints/invoices.py`, `endpoints/business_day.py`.
- All nine canonical Markdown documents reportedly updated, including ADL-010/011/012 in `docs/ARCHITECTURE.md`.
- Limitations disclosed: role switcher via `X-Staff-Role` and `X-Staff-Id` dev headers, native print confirmation cannot be fully automated and was mocked in Playwright, deleted refund-amount bug left alone.

**Interpretation:** These are Antigravity **reported** results; the prior ChatGPT review noted that passing 6 browser tests did not independently prove every interaction or actual printed paper output, and code/test source was not independently inspected in this chat. However **the user then explicitly said the rest of development is okay**. Therefore, treat Prompt 04 as the user's **working accepted baseline**, not an invitation to reopen the earlier gap audit by default.

### Post-Prompt-04 user changes (newest status)

- The user made additional changes to the **Invoice Payment Status dropdown**.
- They confirm the issue is **fixed**.
- They confirm this fix is **documented**.
- They confirm **other development is okay** for now.
- They will share **additional items to add in the next session**.
- Exact dropdown behavior, implementation diff, file names and tests were **not supplied**. If a later feature depends on it, inspect repo/current canonical docs first.

---

## 9. Current status dashboard (as of handoff)

| Area | Status / handling |
|---|---|
| Product definition & stack | Established baseline |
| Modern Receptionist frontend/backend | Implemented per agent reports; user currently considers okay |
| PostgreSQL connection | Earlier “Failed to fetch” resolved per user |
| Prompt 04 corrections | 14/14 reported done; working accepted baseline |
| Invoice Payment Status dropdown | **Fixed and documented per user's latest statement** |
| E2E browser tests | 6 passed, per agent report |
| Backend tests | 19 passed, per agent report |
| Migration | `c94589ffc4ee` applied, per agent report |
| Nine canonical docs | Updated per agent report; dropdown fix separately documented per user |
| Dev role switcher | Intentionally retained |
| Full auth / RBAC | Deferred, not a newly discovered regression |
| Full Admin/Owner/other business modules | Outside this accepted Receptionist slice unless explicitly directed |
| Historical refund ৳1 / max ৳0 investigation | User removed from Prompt 04; do not automatically include |
| Next action | **Await user's new feature/change requirements**, then prepare Prompt 05 |

---

## 10. What to do when the user returns

The next assistant should begin by acknowledging it understands MedScope's Receptionist Phase and the latest accepted status, then listen to the user's requested additions. Do **not** generate a large unsolicited audit or ask them to resubmit prior context.

For each new requested feature/correction:

1. Determine expected role, screen, workflow, UI states and business rules; call out genuine conflicts with existing decisions.
2. Preserve the user's **newly fixed Payment Status dropdown** and other accepted work; if adjacent changes are needed, ask Antigravity to read the actual current code/docs before modifying.
3. Decide whether the change is UI-only, UI+API, or requires Pydantic/ORM/Alembic; do not invent a migration where unnecessary.
4. Include authorization, tenant boundary, financial accuracy, audit trail, error handling, keyboard/mobile behavior and print implications where relevant.
5. Ask Antigravity to add meaningful Playwright and backend tests for the changed paths (including negative cases) and fix failures; do not confuse a report of passes with independent proof.
6. Require all nine canonical docs to stay consistent, updating those impacted and updating `project-context.md` + `docs/TESTING.md` every phase. Keep dependency manifests current.
7. Have Antigravity return a numbered acceptance matrix (`Done`, `Partial`, `Blocked`), modified files, migration/seed status, tested commands/results, known limitations, and documentation revisions.
8. Continue with **Prompt 05**, then Prompt 06 onward. Do not mark a new phase accepted until the user reviews it.

### Suggested future prompt header

> **Prompt 05 — MedScope DCMS: [User's New Requested Additions]**  
> Continue from the accepted Prompt 04 Receptionist Portal and the user's later documented Invoice Payment Status dropdown fix. First inspect actual source and the nine canonical documents. Preserve all working behavior and data. Implement only the newly confirmed additions, verify affected workflows with Playwright/backend tests, update docs and dependencies, and return an evidence-based report.

This is only a **template**, not an instruction to run Prompt 05 now.

---

## 11. Important distinctions and continuity safeguards

- **Latest user input overrides stale agent reports:** the user says Invoice Payment Status dropdown is fixed and documented. Do not frame it as unresolved because a prior gap analysis mentioned status coverage.
- **User-accepted versus independently verified:** Antigravity states all work is complete and tests passed, while the chat did not independently inspect current repository. Respect the user's acceptance without presenting unverifiable specifics as self-checked facts.
- **Commission privacy:** new Doctor/third-party creation may permit a narrowly scoped initial commission input; viewing existing commission remains forbidden to Receptionist.
- **Role access:** front-desk opens day; Admin/Owner closes; Receptionist/Cashier do not close. Development role switching is temporary.
- **Discount cap:** can be 100% of eligible price/subtotal, not 50%; no negative payable.
- **Invoice money and print:** whole-Taka integer amounts, zero default payment, non-final preview, dual copy, persistent historical snapshots, audit on reprints.
- **Refund status != payment status:** invoice may have both. Approved-but-unpaid-out refund is not “Fully Refunded.” Earlier amount-limit bug was expressly removed from Prompt 04.
- **Tests:** the first handoff's “do not run tests” no longer applies after user's explicit authorization in later prompts.
- **Documentation:** use nine canonical MD files, **not** old per-interface documentation requirements.
- **Security:** request headers as actors are **development-only** and must not be mistaken for production-safe auth.
- **No pending instruction to actively fix more gaps:** user will identify additions next session.

---

## 12. Source provenance for this handoff

This summary consolidates, in chronological order:

1. `DCMS_Receptionist_Phase_Session_Handoff.md` — original product, business rules, implementation baseline and then-current testing policy.
2. `Chattiing.md` — previous ChatGPT/Antigravity coordination, Prompt 03 discussions, all 14 revised corrections, role/payment/referral decisions and changes in documentation/testing policy.
3. `Prompt_04_DCMS_Receptionist_Corrections_E2E_Documentation.md` — actual Prompt 04 requirements and verification/documentation contract.
4. `DCMS_RECEPTIONIST_CORRECTIONS_PLAYWRIGHT_REPORT.md` — Antigravity's 7 November 2026 implementation/test/migration report; **agent-reported** claims.
5. **User's newest message in this conversation** — Invoice Payment Status dropdown fixed and documented; remaining development okay; new additions to follow next session.

The four named materials may not be attached to the next chat; **this handoff is intended to stand alone**. If direct code inspection or a particular implementation diff becomes essential later, request **only that specific needed artifact**, or instruct Antigravity (which has repository access) to inspect it.

---

**End of master handoff — current pause point: Receptionist Phase accepted as working baseline, Payment Status dropdown fixed/documented, waiting for user-specified additions for Prompt 05.**
