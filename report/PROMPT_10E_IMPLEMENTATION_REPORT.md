# Prompt 10E — Room-Based Routing, Refund Rule, Invoice Payload, Payment Channels, Doctor Role and Worklist Fixes: Report

- **Date:** 2026-11-13. Uncommitted working tree on `main`. Nothing was committed or pushed.
- **Dev DB:** `medscope_dcms`. Backup taken first: `backups/medscope_dcms_pre_prompt10e.dump` (custom `pg_dump`, exit 0, git-ignored). Two additive migrations were applied, then the one-off re-route script (dry run first, then `--apply`).
- **Tests:** `pytest` ran only against `medscope_test`; the safety guard is unchanged.
- **Browser:** not used. Playwright was **not run**, because `MEDSCOPE_E2E_PASSWORD` is not set in this environment (standing rule 3).
- **Secrets:** no password, token or connection string was written or printed. New test users get passwords generated at runtime.

## 1. Summary

| Part | Status | Note |
|---|---|---|
| 0. Read-only investigation | **Done** | §2. Code reading and `SELECT`-only queries in `READ ONLY` transactions. |
| 1. Refund rule | **Done** | `refund = max(0, retained_paid − net_after)`; the 10D proportional allocation is removed. |
| 2. Sample "None" = no sample | **Done** | One helper, `requires_sample`, plus a data migration. Flag: 1,224 catalog tests have no sample type (A5). |
| 3. Age/gender in payload | **Done** | Required at Finalize, optional in a draft, no defaults. Infants in months or days. |
| 4. Payment channels | **Done** | Adds ROCKET and OTHER (with a typed name). Frontend uses exactly the backend values. Missing drawer rows are created safely. |
| 5. Backend urgent fee | **Done** | Same rule as the old UI (a **minimum** of ৳100, see A1). Stored, included in net, never refunded. |
| 6. Roles and permissions | **Done** | LAB_TECH can edit their own profile. CASHIER can no longer release a report with a due. New DOCTOR role. |
| 7. Room-based routing | **Done** | Mapping, routing at Finalize, room visibility, auto-release, reassign, Assign Tests fix, room required for technicians, re-route script applied. |
| 8. Bento tiles as filters | **Done** | Pure mapping module checked with a Node script; the frontend has no unit-test runner. |
| 9. Report preview and Ready | **Partial (by design)** | Preview Report action and a Ready filter/tile added. Issued reports for saved results are **Deferred** to Module 14 (§2.1). |
| 10. E2E specs | **Partial** | Both specs updated and they parse (`--list`: 12 tests). **Not run**: the password variable is not set, and the receptionist spec creates records. |
| 12. Docs | **Done** | All nine docs updated, with ADL-040 to ADL-047 added (§5). |
| 13. Report | **Done** | This file. |

## 2. Investigation findings (Part 0)

### 2.1 My Work (Lab): no report preview, and "Ready" reports cannot be found
- **Statuses that exist:**
  - `results.status`: `DRAFT` / `ENTERED` (`result_service.py`, `save_test_result`).
  - `test_orders.status`: UNASSIGNED, ASSIGNED, PENDING, SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, COMPLETED, CANCELLED, REJECTED, SPOILED.
  - `report_versions.status`: `FINAL_AUTHORIZED` (`DRAFT` is defined but never written), plus `authorized`.
  - `report_deliveries`: a row means delivered.
- **What "Ready" means in the code:**
  - The sidebar item "Ready Reports" (`Sidebar.tsx`) opens `/reports` ("Ready Reports & Delivery", `ReportsPage.tsx`).
  - That page calls `GET /reports/deliverable`, which is `report_service.list_deliverable_reports` (`report_service.py` lines 18–86). It lists **`report_versions` with `authorized = true`** only.
  - Opening it needs `report.view`, a front-desk/money key. LAB_TECH does not hold it.
- **Root cause 1 — nothing creates a report version.**
  - `ReportVersion(...)` is constructed only in `backend/scripts/seed.py` (lines 281, 320 and 417).
  - `save_test_result` (`result_service.py`, "4. Update TestOrder operational lifecycle") sets the order to COMPLETED for `TECHNICIAN_FINAL` tests but never issues a report.
  - Dev DB: 6 report versions, all from seed and all with 0 results. 4 orders that have results have no report version.
  - So a saved result never reaches the Ready list. Creating report versions is "report finalization", which `docs/SCOPE.md` §4.11 assigns to **Module 14 (Draft to Final)**. That part is **deferred**.
- **Root cause 2 — the grid hides everything after a save.**
  - In `TechnicianWorklistPage.tsx` (standard workflow block), every action is gated by `order.status !== 'COMPLETED'`.
  - After an ENTERED save the order becomes COMPLETED, so even "Edit Results" disappears. No preview action existed anywhere, and only the Timeline link remained.
  - The status tabs had no "Ready" filter.
- **Smallest fix (implemented):**
  - A **Preview Report** action on rows with a saved result. It uses the existing `GET /worklist/{id}/result` and is money-free.
  - A **Ready Reports** filter, tab and tile: `status=READY` means COMPLETED with an ENTERED result. Rows also get `report_ready` and a "Report Ready" chip.
  - `/reports` is unchanged. It still lists only issued reports until Module 14.

### 2.2 Routing, worklist visibility and Assign Tests (10D report §2) — confirmed unchanged before 10E
- **Routing:** `_confirm_invoice` step 9 (`invoice_service.py`): doctor → AWAITING_DOCTOR; outsourced → PENDING; `performing_role == 'LAB_TECH'` → the first LAB_TECH whose department matches exactly, else UNASSIGNED; otherwise the `default_assignee` text with no technician.
- **Visibility:** `get_technician_worklist` filtered technicians by `assigned_to_id == actor.id`.
- **Assign Tests page:** sent the destination **id** as its name (`AssignmentsPage.tsx`: `api.assignTest(order.id, destId)`).
- **Dev DB:** ids "6" (7 orders), "2" (3), "1" (3), "3" and "5" were stored in `assigned_destination`.

### 2.3 Payment channel storage
- **Database:** no enum or CHECK on channels. The only payment CHECK is `amount > 0`. `payments.method` and `business_day_channel_balances.channel` are `String(50)`.
- **Business-day rows:** created at day open from `STANDARD_CHANNELS` = CASH, BKASH, NAGAD, BANK_TRANSFER, POS_CARD. The open day had exactly those 5 rows.
- **Silent loss:** the invoice and due-payment code only added to the drawer `if channel_rec:`. A payment on a channel without a row (ROCKET, CARD) was **silently left out of the drawer**.
- **Schemas:** free strings, no validation.
- **Frontend:**
  - The `PaymentChannel` type was `CASH | BKASH | NAGAD | ROCKET | CARD | BANK_TRANSFER`.
  - The lists in New Invoice, Invoices (×2), Dues and Refunds offered ROCKET and CARD, and **not** POS_CARD.
- **Refunds:** disbursement validates against the channels used on the invoice (`refund_service.disburse_refund`).
- **Dashboards:** `dashboard_service` has no per-channel logic.
- **Dev DB payments:** CASH 13, BKASH 2, NAGAD 1.

### 2.4 Urgent fee (current UI rule, stated exactly)
- **Rule:** `NewInvoicePage.tsx` `handleToggleUrgent` (and the draft reopen) sets, per urgent line, `urgent_fee = Math.max(100, Math.round(line.price * 0.2))`.
- **Totals:** `netPayable = gross + Σ urgent_fee − totalDiscount`. Discounts are computed on the list price only, so the fee is never discounted.
- **Meaning:** 20% of the line's list price, rounded half up to whole taka, with a **minimum of ৳100**. "Max 100" refers to JavaScript's `Math.max`, which acts as a floor, not a cap.
- **Backend:** never charged it. The payload sent only `is_urgent`.

### 2.5 Age and gender
- **Where they are stored:**
  - `patients` stores `gender` only (no age and no date of birth). Its values are mixed case: Male/MALE, Female/FEMALE.
  - `visits` stores `age_value`, `age_unit`, `age_days` and `gender`.
- **Silent defaults:** `InvoiceConfirmRequest` defaulted to `age_value=30`, `age_unit="years"`, `gender="Male"`. Also, `age_days` treated any non-"years" unit as months.
- **What the UI collected:** the New Patient modal collects gender, `age_years` and `age_months`. `PatientCreate` maps them, but the patient table drops the age, and the invoice payload sent neither.
- **Dev DB:** 7 of 15 visits are 30 / years / Male.

## 3. Implementation details

### Migrations (single head throughout)
- **`e8b2f4a6c1d3` (Parts 2–5):**
  - `tests.sample_type` "None", "N/A" and "" → NULL.
  - Adds `payments.channel_detail`, `invoices.urgent_fee` (with CHECK ≥ 0) and `invoice_lines.urgent_fee`.
  - Adds zero-balance channel rows for missing channels on OPEN business days.
  - Additive.
- **`f3c9a1d7e5b2` (Part 7):**
  - Adds `tests.lab_section` (indexed, backfilled from the mapping) and `test_orders.lab_section` (indexed).
  - Gives LAB_TECH rows without a room one from their department when it maps.
  - Adds CHECK `chk_staff_lab_tech_has_section` only when every row complies. The migration prints the rows that block it otherwise.
  - The file bootstraps `sys.path` so `alembic heads` works without `env.py` (the first `heads` call failed before this fix).

### Part 1 — Refund rule (`backend/app/services/refund_service.py`)
- **New function:** `compute_cancellation_outcome(invoice, line)`:
  - `net_after = max(urgent_fee, net − line.net_price)`
  - `retained_paid = paid − Σ(APPROVED + DISBURSED)`
  - `refund = max(0, retained_paid − net_after)`
  - `due = max(0, net_after − (retained_paid − refund))`
- **Where it is used:**
  - Eligibility and request creation compute a server-side preview; any client `amount` is ignored.
  - Approval recomputes the amount, cancels the line, sets `net`, `due`, `payment_status` and `refund_due`, and recomputes `refund_status`.
  - A zero refund closes the request as `COMPLETED`.
- **Removed:** `compute_line_billed_share`, the proportional "line share" allocation and the "last line takes the remainder" logic.
- **Unchanged:** two-stage approval, self-approval block, original-channel disbursement and technician isolation.

### Part 2 — Samples (`backend/app/core/samples.py`)
- **Helpers:** `requires_sample(test, order)` and `is_imaging_test(test, order)`.
  - Imaging means: doctor-routed, NARRATIVE template, Ultrasonography room, or a department containing ultrasono/usg/x-ray/radiolog/imaging.
  - NULL, empty, "None" and "N/A" (any case) mean no sample.
  - The FULL sample route still requires a sample unless the test is imaging.
- **Used in:**
  - `update_order_status` (completion guard)
  - `get_result_template` and `save_test_result` (result-entry guard)
  - the invoice detail sample status (new value "No sample needed")
  - `record_imaging_performed`
  - the refund imaging lock
  - the worklist item fields `requires_sample` and `is_imaging`, which drive the badges and the Sample Taken action
- **Seed:** `seed.py` now writes `None` instead of "None".

### Parts 3–5 — Invoice payload, channels and urgent fee
- **Schema (`schemas/invoice.py`):**
  - `age_value` is Optional (no default); `age_unit` is years, months or days; `gender` is Optional and normalised to Male/Female/Other (M/F/O accepted).
  - Limits are 0–130 years, 0–1,560 months or 0–47,450 days; anything else gets 422.
  - New `initial_payment_channel_detail` field (`initial_payment.channel_detail` is also accepted).
- **Service (`invoice_service.py`):**
  - `validate_finalize_demographics` returns 400 at Finalize when age or gender is missing.
  - The visit stores the values, with `age_days` correct per unit.
  - The patient's stored gender is updated from the form.
  - `compute_invoice_totals` adds the urgent fee (`compute_urgent_fee` = `max(100, half-up(20% × price))`) after discounts.
  - `invoices.urgent_fee` and `invoice_lines.urgent_fee` are stored; drafts store the same total.
  - Percentage discounts round half up like the UI.
  - With a master discount active, line discounts are inactive in calculations (A3).
- **Channels (`backend/app/core/payment_channels.py`):**
  - `validate_channel` checks the list and requires a name for OTHER; CARD is accepted as an alias of POS_CARD.
  - Used by invoice confirmation and `settle_invoice_due`. `normalize_channel` is used in refund disbursement.
- **Drawer (`business_day_service.py`):**
  - `STANDARD_CHANNELS` is now the full list.
  - `get_or_create_channel_balance` and `add_to_channel_balance` make sure no payment is skipped.
  - The status endpoint lists every channel.
- **Patients:** `PatientResponse.last_age_value` and `last_age_unit` (from the latest visit) are used for prefill.
- **Frontend:**
  - New `utils/paymentChannels.ts` (option list, labels, OTHER check and urgent-fee preview).
  - `NewInvoicePage.tsx`:
    - Age (+ unit) and Gender fields on the patient card, prefilled through `choosePatient` or from the New Patient form.
    - The payload carries age, gender and channel detail.
    - Finalize is guarded on the client too.
    - Shared channel list plus a Channel Name field.
  - `DualCopyInvoiceModal.tsx`: shows the backend urgent fee, discount and age/gender, plus a "Paid via" line.
  - Invoices, Dues and Refunds use the shared list plus a Channel Name field. Invoice payment history shows the channel label.

### Part 6 — Roles and permissions (`backend/app/core/permissions.py`)
- **Roles:** `ROLES` now ends with `DOCTOR`, and `MONEY_RESTRICTED_ROLES` = {LAB_TECH, DOCTOR}.
- **New keys:** `worklist.reassign` and `worklist.doctor_queue`. That makes 35 keys, 20 of them money keys.
- **Default changes:**
  - LAB_TECH gains `profile.manage`.
  - CASHIER loses `report.release_with_due`; CASHIER now equals RECEPTIONIST.
  - DOCTOR gets `worklist.view`, `worklist.doctor_queue`, `worklist.update`, `result.enter`, `result.complete_doctor_routed` and `profile.manage`.
  - ADMIN/OWNER gain the two new keys.
- **Report release with a due (`report_service.py`):** only holders of `report.release_with_due` may release, and only with an override reason (400 without one). Others get 403 even with a reason.
- **New helper:** `require_any_permission(*keys)`.
- **Profile:** the profile endpoint now commits its audit row. It was previously written after the commit and lost.
- **CLI:** `manage_users.py` accepts DOCTOR and requires `--lab-section` for LAB_TECH.
- **Frontend:**
  - The Reports override button is shown by permission, so Owner now sees it too.
  - The Header avatar colour and Sidebar label support DOCTOR.
  - The role picker comes from `/users/meta`, so DOCTOR appears automatically.

### Part 7 — Room-based routing
- **Mapping (one place, `backend/app/core/lab_sections.py`):**
  - `SECTION_KEYWORDS`, `section_for_test_fields(department, default_assignee, performing_role)` and `section_for_test(test)`.
  - Evidence order is `default_assignee` → `department` → `performing_role`, so it never depends on `performing_role == "LAB_TECH"`.
  - Mapping examples:

    | Catalog value | Room |
    |---|---|
    | Hematology, Hematopathologist | HEMATOLOGY |
    | Biochemistry, Biochemical Tests, Clinical Biochemist | BIOCHEMISTRY |
    | Serology with "Biochemistry Room 102" | BIOCHEMISTRY |
    | Microbiology, Microbiology & Parasitology, Microbiologist | MICROBIOLOGY |
    | Ultrasonography (USG), Ultrasonogram, USG Technician | ULTRASONOGRAPHY |

- **Routing service (new, `services/routing_service.py`):**
  - `route_new_order` is used at Finalize.
  - Doctor-routed and outsourced orders keep their status, with the room recorded.
  - Otherwise the order is ASSIGNED when the room has an active LAB_TECH, else UNASSIGNED.
- **Visibility:**
  - `visibility_clause` and `can_access_order` replace every `assigned_to_id == actor.id` check (list, sample, reject, contact, imaging, culture, outsourced, events, barcode, status, result template and save).
  - `record_actor` stores who acted.
- **Auto-release:** `release_unassigned_orders_for_section` runs when a LAB_TECH is created, reactivated, moved into a room, or changes role into LAB_TECH. It writes audit `ORDER_ROOM_RELEASED`, an assignment history row and an event.
- **Reassign:**
  - `move_order_to_room` is used by `POST /worklist/{id}/reassign` (`worklist.reassign`) and by the Assign Tests endpoints.
  - It returns 409 after COMPLETED or when cancelled.
  - It keeps samples and results, clears `assigned_to_id`, and writes audit `REASSIGN_ROOM` or `ASSIGN_TEST_ORDER`.
  - New `GET /worklist/rooms`.
- **Assign Tests:**
  - The backend resolves a room key, a room name or a legacy id to a room name, and returns 400 if nothing matches.
  - Front desk may route only UNASSIGNED orders.
  - The page lists rooms and sends `lab_section`.
- **Technician needs a room:** the user service returns 400 on create or role change without a room. The Create User tab marks it required.
- **Summary:** same visibility as the list. Before, an Admin's summary counted only orders assigned to the Admin.
- **Re-route script:** `backend/scripts/reroute_orders_to_rooms.py`. It is a dry run by default and writes one audit row per changed order with `--apply`. A legacy-destination fallback is used **only for non-imaging tests**.

### Parts 8 and 9 — Worklist UI
- **Tile mapping:** `features/worklist/worklistTiles.ts` (pure).
- **Tiles:** buttons with `aria-pressed` and a focus ring.
- **Tabs:** "Late" and "Ready Reports" added.
- **Rows:** Room label, "Worked by", "Report Ready" chip, Preview Report button and Reassign Room button.
- **Preview modal:** `components/common/ResultReportPreviewModal.tsx`.
- **Backend:** worklist filters `READY` / `LATE` / `UNASSIGNED`, plus `ready_count` and `unassigned_count`.

### Part 10 — E2E specs
- **`test_modal_regression.spec.ts`** (all read-only):
  - A6 checks the room in the header, that a tile click sets `aria-pressed`, that a second click clears it, and that there is no Unassigned tile for technicians.
  - A4 checks that choosing OTHER shows the Channel Name field.
- **`receptionist_corrections.spec.ts`:** fills age/gender before Finalize, checks the exact channel list, and checks the OTHER field.
- **New test ids:** `payment-method-select` and `dues-payment-method-select`.
- **Passwords:** still only from `MEDSCOPE_E2E_PASSWORD`.

### Tests (new and changed)
- **`tests/test_prompt10d_refunds.py`** — rewritten, 10 tests (was 6):
  - the four worked cases
  - repeated cancellations
  - cancellation after a disbursed refund
  - a due turning into a refund
  - client amount ignored
  - urgent fee not refunded
  - technician isolation
- **`tests/test_prompt10e_invoice_payment_samples.py`** (new) — 16 tests across Parts 2, 3, 4 and 5.
- **`tests/test_prompt10e_rooms_roles_worklist.py`** (new) — 10 tests across Parts 6, 7 and 9.
- **Updated existing tests:**
  - Invoice payloads now send age and gender (5 files).
  - `test_receptionist_e2e.py::test_04` now expects the urgent fee.
  - In `test_prompt10d_roles_permissions.py`, the defaults test now covers 10E and the LAB_TECH it creates gets a room.

### Files
- **New (backend):**
  - `backend/app/core/samples.py`, `backend/app/core/payment_channels.py`
  - `backend/app/services/routing_service.py`
  - `backend/scripts/reroute_orders_to_rooms.py`
  - the two migrations
- **New (frontend):** `frontend/src/utils/paymentChannels.ts`, `frontend/src/features/worklist/worklistTiles.ts`, `frontend/src/components/common/ResultReportPreviewModal.tsx`
- **New (tests and report):** the two 10E test files; this report.
- **Modified (backend):**
  - core: `lab_sections.py`, `permissions.py`
  - models: invoice, payment, test, test_order, user, patient, business_day
  - schemas: invoice, payment, refund, business_day, worklist, assignment, patient, test
  - services: invoice, refund, payment, business_day, worklist, result, report, assignment, user_admin
  - endpoints: invoices, payments, worklist, assignments, profile
  - scripts: `seed.py`, `manage_users.py`
- **Modified (frontend):** `client.ts`, `types/index.ts`, NewInvoicePage, DualCopyInvoiceModal, InvoicesPage, DuesPage, RefundsPage, ReportsPage, AssignmentsPage, TechnicianWorklistPage, UserManagementPage, Header, Sidebar, and both e2e specs plus `support/auth.ts`.
- **Modified (tests):** the 6 files listed above.
- **Modified (docs):** the nine docs.

## 4. Assumptions and design choices (please confirm or reverse)

| # | Choice | Why / how to change |
|---|---|---|
| A1 | **Urgent fee = `max(100, round(20% × price))`, i.e. a minimum of ৳100**, replicating the UI code exactly. "Max 100" in the prompt is read as JavaScript `Math.max`, which is a floor. | The prompt said to replicate the UI rule. If you meant a **cap** of ৳100, change `compute_urgent_fee` and `urgentFeePreview` (two lines). |
| A2 | The urgent fee stays on the invoice even when **all** lines are cancelled (`net_after` never drops below the fee), so it is never refunded. | "Fee belongs to the invoice, not to a line." Reverse by removing the floor in `compute_cancellation_outcome`. |
| A3 | With a Master Discount active, line discounts are now **inactive in calculations**: line `net_price` = list price, and their type/value stay saved, as in the UI preview. Percentage discounts now round half up like the UI. | Before, a preserved line discount could lower `net_price` while the invoice used the master discount. That mattered once refunds use `line.net_price`. With a master discount, `net_after = net − list price`, which favours the patient. |
| A4 | Refund amounts from the client are **ignored entirely**. The server value is a preview at request time and is binding at approval. | "Must NOT trust client-supplied money amounts." Before, a smaller requested amount was accepted. |
| A5 | **Sample rule as instructed:** NULL `sample_type` = no sample required. **1,224 imported catalog tests have no sample type**, so results and completion for them no longer wait for a sample. The worklist still offers "Sample Taken" for non-imaging tests, but it is optional. | Following the prompt literally. **Recommended:** fill `sample_type` in the catalog for blood/urine/stool tests; that restores the block per test. |
| A6 | "Imaging" = doctor-routed, NARRATIVE template, Ultrasonography room, or a department containing ultrasono/usg/x-ray/radiolog/imaging. | Covers USG/X-ray in the catalog. Edit `_IMAGING_DEPARTMENT_HINTS` in `samples.py`. |
| A7 | **DOCTOR defaults:** money-free Dashboard, doctor queue = AWAITING_DOCTOR from all rooms **plus completed doctor-routed orders**, `worklist.update` (needed to use the existing completion endpoint), and `result.enter` (to read and write findings). No lab room. | The prompt's assumption, made concrete. Adjust `ROLE_DEFAULTS["DOCTOR"]`. No DOCTOR user was created in the dev DB. |
| A8 | `worklist.reassign`: ADMIN and OWNER by default, grantable per user. Front desk (`assignment.manage`) can route **only UNASSIGNED** orders from the Assign Tests page. | Keeps "move to another room" with supervisors. Grant the key per user if the front desk should reassign. |
| A9 | **Release with a due now always needs an override reason**, even for Admin/Owner. Before, holders of the key could release without one. | Matches "may still release with an override reason" and AGENTS.md. |
| A10 | **Re-route script:** the room comes from the test. Only for non-imaging tests that map to no room is the existing destination (room name or legacy id) used. Cancelled orders are untouched. `assigned_to_id` is kept as history. | Keeps front-desk choices (for example Clinical Pathology urine sent to Room 105 or 102) and does not push X-rays into a lab room through a legacy id. |
| A11 | If a room loses its last technician, its ASSIGNED orders **stay ASSIGNED** (Admin/Owner still see them and can reassign). | Not required by the prompt. Could be added as a "demote to UNASSIGNED" rule. |
| A12 | **Mapping choices:** an explicit room in `default_assignee` wins (so Serology tests with "Biochemistry Room 102" go to Biochemistry); "usg" counts as an Ultrasonography keyword; 671 tests map to no room (Clinical Pathology, Endocrinology, Histopathology, X-ray, Serology & Immunology, Cardiology). | Edit `SECTION_KEYWORDS` in one place. A new room needs an entry in `LAB_SECTIONS`. |
| A13 | "Ready" (worklist) = order COMPLETED with an ENTERED result. It is **not** an issued report. | Issuing reports is Module 14 (deferred). |
| A14 | The patient's stored gender is updated from the invoice form at Finalize. Earlier visits keep their snapshot. | "Prefill and let the form update them." |
| A15 | The staff CHECK is added only where every row complies. Dev DB: **added**. Test DB: **not added**, because 5 leftover LAB_TECH test users have no room; the service rule applies. | Prompt rule 7.7. Give those test users a room, or remove them in Prompt 11, and re-run the migration step. |
| A16 | Migration `f3c9a1d7e5b2` imports the mapping from the app (one place) instead of keeping a frozen copy. | "Editable in one place." The migration bootstraps `sys.path`. |

## 5. Docs changed and labels flipped

All nine docs were updated: `README.md`, `project-context.md` (new Prompt 10E section), `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md` and `docs/TESTING.md`.

| Item | Before | Now |
|---|---|---|
| ADL-036 (10D refund allocation) | Implemented | **Superseded by ADL-040** (rule text in ADL-019 replaced) |
| ADL-013 (Module 10 routing) | department → technician | Marked **superseded by ADL-041** |
| ADL-014 (technician filter) | `assigned_to_id == actor.id` | Room filter (10E); DOCTOR is also isolated |
| ADL-038 quirk (CASHIER release with due) | Kept on purpose | **Reversed in 10E** |
| New ADLs | — | ADL-040 refund rule, ADL-041 rooms/reassign, ADL-042 channels, ADL-043 urgent fee, ADL-044 age/gender, ADL-045 DOCTOR, ADL-046 sample rule, ADL-047 tiles / Ready / preview |
| SCOPE §5.1 "Known routing gaps" | Not fixed | Rewritten as "implemented behavior and remaining gaps": doctor sign-off screen, `performing_role` normalization, 671 tests without a room, a room left without technicians |
| SCOPE roles and matrix | 5 roles | DOCTOR row and column; CASHIER/LAB_TECH changes; Reassign and My Profile rows; new §4.17 invariants |

- **Counts updated:** API 81 paths / 94 operations; head `f3c9a1d7e5b2`; 29 tables (28 domain); 35 permission keys (20 money); pytest 110.
- **Still labelled as not implemented:** the reduced-motion "Pause animations" decision, Prompt 11 soft delete, the doctor sign-off screen, Module 14 (Draft to Final), and the pre-go-live credential cleanup (TESTING §12).
- **Docs-to-code consistency check:** a grep sweep for stale facts found four mismatches, all fixed:
  - README API count
  - SCOPE §4.9 technician filter
  - the API worklist rows: a DOCTOR access note was added
  - a project-context Prompt 05 line: annotated as historical

  The remaining mentions of `assigned_to_id == actor.id`, 79/92, 80 passed or `d7e5a91c4f02` are inside clearly historical Prompt 05–10D sections. No other contradiction was found.

## 6. Real command results (2026-11-13)

| Command | Result |
|---|---|
| `python -m pytest -q` (`medscope_test`) | **110 passed**, 0 failed (was 80: the 6 old refund tests were replaced by 10, plus 16 and 10 new tests) |
| `tsc -b` | exit 0 |
| `npm run lint` (oxlint) | exit 0, **0 errors**, 120 warnings (unchanged baseline; I removed the 3 warnings my first draft added) |
| `vite build` (output to scratchpad) | built; the usual >500 kB chunk warning |
| Tile mapping check (Node 24, scratchpad script) | `tile mapping checks passed (10 tiles)` |
| `alembic heads` | `f3c9a1d7e5b2 (head)` — single head |
| `alembic current` (dev DB) | `f3c9a1d7e5b2 (head)` |
| `alembic check` | `No new upgrade operations detected.` |
| OpenAPI | **81 paths / 94 operations** (+`GET /worklist/rooms`, +`POST /worklist/{id}/reassign`) |
| ORM tables | 28 domain + `alembic_version` = 29 |
| Playwright `--list` | 12 tests in 2 files (specs parse) |
| Playwright run | **Not run**: `MEDSCOPE_E2E_PASSWORD` is not set; the receptionist spec also creates records |
| Dev DB backup | `pg_dump` exit 0, `backups/medscope_dcms_pre_prompt10e.dump` (git-ignored) |

**Migration effects (dev DB):**
- 4 "None" sample types became NULL.
- The open business day got `OTHER` and `ROCKET` rows.
- The staff CHECK was added.
- Catalog rooms:

  | Room | Tests |
  |---|---|
  | Biochemistry | 280 |
  | Hematology | 74 |
  | Microbiology | 188 |
  | Ultrasonography | 37 |
  | No room | 671 |

  `URINE_C_S` is in MICROBIOLOGY.

**Re-route script (dev DB):**
- Dry run, then `--apply`: 40 open orders considered, **34 changed**.
- Audit rows `ORDER_REROUTED_TO_ROOM` ids 884–917.
- Status moves:

  | From → to | Orders |
  |---|---|
  | ASSIGNED → ASSIGNED | 24 |
  | ASSIGNED → UNASSIGNED | 2 |
  | UNASSIGNED → ASSIGNED | 1 |
  | AWAITING_DOCTOR kept | 4 |
  | REJECTED kept | 3 |

- 0 raw destination ids remain in open orders.

**Per-room order counts after the re-route (dev DB, open = not COMPLETED / CANCELLED):**

| Room | Open orders (by status) | Active technicians |
|---|---|---|
| Biochemistry (102) | 17 (15 ASSIGNED, 2 REJECTED) | 1 (`tech_nasrin`) |
| Hematology (101) | 3 ASSIGNED | 1 (`tech_kamal`) |
| Microbiology (105) | 5 ASSIGNED (incl. `URINE_C_S` ×2) | 2 (`tech_micro`, `tech_boss`) |
| Ultrasonography (204) | 5 (2 ASSIGNED, 2 AWAITING_DOCTOR, 1 REJECTED) | 1 (`tech_usg`) |
| No room | 10 (7 UNASSIGNED, 3 AWAITING_DOCTOR: 2 × X-ray, 1 × Clinical Pathology) | — (Admin/Owner and the doctor queue) |

## 7. Deferred items, blocked items and new risks

- **Deferred:**
  - Module 14: issuing `report_versions` from saved results, so `/reports` shows them.
  - Doctor sign-off screen and approval records.
  - `performing_role` normalization.
  - Rooms for the 671 unmapped tests.
  - Prompt 11 soft delete.
  - The reduced-motion decision.
  - The pre-go-live credential cleanup.
- **Blocked:** a real Playwright result. To run the read-only spec (with servers on 5173/8000):
  `$env:MEDSCOPE_E2E_PASSWORD = '<dev password>'; cd frontend; npx playwright test e2e/test_modal_regression.spec.ts`
- **Risks:**
  - **Sample requirement (A5):** 1,224 catalog tests have no `sample_type`, so a technician can enter results for them without a sample, and their invoice line is not locked by a sample. Filling the catalog closes this.
  - **Technician view is wider now:** technicians see every order of their room, not only their own. Room 102 (Biochemistry) now has 17 open orders for one technician.
  - **Admin worklist summary:** it now counts all rooms. Before, it counted only orders assigned to the Admin, so the dashboard numbers for Admin/Owner changed.
  - **Saved drafts:** drafts saved before 10E have no age/gender, so Finalize asks for them.
  - **Old CARD payments:** any old payment stored as `CARD` (none in the dev DB) can still be refunded through "Card" (POS_CARD) thanks to the alias.
  - **Test DB:** keeps 5 LAB_TECH users without a room and has no staff CHECK (A15).
  - **Uncommitted 10D work:** the working tree still holds the uncommitted 10D changes under these 10E changes. Nothing was committed.
- **Tracked-but-deleted files:** `git status` still shows the 13 files deleted before 10D. They were not restored, moved or deleted further. `master_context_all_harness.md` and past reports were not edited.
