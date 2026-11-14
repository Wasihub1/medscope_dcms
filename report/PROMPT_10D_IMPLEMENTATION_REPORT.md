# Prompt 10D — Routing Audit + Implementation of Decided Changes: Report

- **Date:** 2026-11-13. **Base commit:** `a6c0243` (branch `main`, uncommitted working tree; nothing was committed).
- **Dev DB:** `medscope_dcms`. A backup was taken first: `backups/medscope_dcms_pre_prompt10d.dump` (custom `pg_dump`, git-ignored). Two additive migrations were applied, and the section-user script was run with `--apply`.
- **Tests:** `pytest` ran only against `medscope_test`; the safety guard is unchanged.
- **Browser:** only the Part 7 grant was used (one read-only run of `test_modal_regression.spec.ts`; see §6).
- **Secrets:** no password, token or connection string was written to any file or printed.

## 1. Summary

| Part | Status | Note |
|---|---|---|
| 1. Read-only routing audit | **Done** | Code reading plus `SELECT`-only queries in a `READ ONLY` transaction (§2) |
| 2. D15 refund amount fix | **Done** | Refunds capped at money paid. Also fixed the missing ORM relationship that crashed disbursement. |
| 3. Invoice Draft / Finalize | **Done** | Backend, frontend and tests. Invoice number assigned at Finalize. |
| 4. One login = one role; Dashboard landing | **Done** | Switcher and endpoint removed, dual-role accounts split, role-safe Dashboard |
| 5. Central permission layer + Create User tab | **Done** | `core/permissions.py`, overrides table, `/users` API + UI, lab sections, section users |
| 6. Routing / "Awaiting Doctor" | **Deferred by instruction** | Not changed. Recommended fixes in §2.7. |
| 7. Playwright specs | **Partial** | Both specs updated. The read-only modal spec was run but cannot pass without the dev password in `MEDSCOPE_E2E_PASSWORD` (0/6, stops before login). The receptionist spec creates records, so it was **not run**. |
| 9. Docs | **Done** | All nine docs updated; labels flipped (§5) |
| Blocked | — | Only the real Playwright pass/fail, which needs the owner's credential (§7) |

## 2. Part 1 — Audit findings (read-only, before any change)

### 2.1 Room / section model
- **No section or room concept is used by routing or visibility.** Rooms exist only as:
  - `test_destinations` rows (seeded in `backend/scripts/seed.py` lines 89-92): id 1 "Hematology Room 101" (Room, Hematology), id 2 "Biochemistry Room 102" (Room, Biochemical Tests), id 3 "Ultrasonography Room 204" (Room, Ultrasonogram), id 4 "Microbiology Lab 105" (Lab, Microbiology), plus two "Technician" destinations.
  - free-text `tests.default_assignee` strings (seed lines 104-131). In the dev DB: 1,228 tests have none, 15 "Biochemistry Room 102", 3 "Hematology Room 101", 3 "Ultrasonography Room 204", 1 "Microbiology Lab 105".
  - `staff.department` (free text: "Hematology", "Biochemical Tests", "Front Desk", "Administration").
- Room 101/102/105/204 are not defined anywhere else in backend or frontend code. Prompt 10D added `backend/app/core/lab_sections.py` and `staff.lab_section`.

### 2.2 Routing rule (invoice confirmation, `backend/app/services/invoice_service.py`, in `_confirm_invoice` step 9)
Routing happens per invoice line, in this order:
1. `tests.requires_doctor` or `tests.performing_role == "DOCTOR"` → status `AWAITING_DOCTOR`, `assigned_destination` = `default_assignee` or "Doctor Chamber". No staff is assigned.
2. `tests.is_outsourced` → `PENDING`, destination "Outsourced Referral Lab".
3. `tests.performing_role == "LAB_TECH"` → the **first** active `Staff` with `role == "LAB_TECH"` and `department == tests.department` (exact string match) → `ASSIGNED` to that technician. Otherwise `UNASSIGNED` with `assigned_destination = default_assignee`.
4. Any other `performing_role` → `ASSIGNED` if `default_assignee` is set (destination text only, **no technician**), else `UNASSIGNED`.

So the deciding fields are `requires_doctor`, `performing_role`, `is_outsourced`, `department` and `default_assignee`. Specimen type and section are not used. Assignment goes to a specific technician only in case 3; otherwise it is a destination string. Manual assignment (`/assignments/assign`, `AssignmentsPage.tsx`) sets only `assigned_destination` (the page sends the destination **id** as the name, e.g. "6") and never `assigned_to_id`.

### 2.3 Technician view
- **Rule:** `get_technician_worklist` filtered LAB_TECH to `TestOrder.assigned_to_id == actor.id` (no section or room filter). Admin/Owner saw everything. Technicians do **not** all see everything; they see only orders assigned to their own id.
- **Snapshot (dev DB, before 10D changes):**
  - `tech_kamal`: 6 orders (Biochemical Tests 2 REJECTED, Ultrasonogram 1 REJECTED, Clinical Pathology 1 AWAITING_DOCTOR, X-Ray & Radiology 1 COMPLETED, Hematology 1 COMPLETED).
  - `tech_nasrin`: 3 orders (Biochemical Tests 2 ASSIGNED, 1 COMPLETED).
  - **43 of 52 orders have no `assigned_to_id`.** That includes ASSIGNED orders for "Biochemistry Room 102", "Microbiology Lab 105", destination ids "6"/"2"/"1", and others. They are invisible to every technician and visible only to Admin/Owner.

### 2.4 Microbiology Room 105 — root cause
- **Catalog:**
  - 1 test in department "Microbiology": `URINE_C_S`, `performing_role` LAB_TECH, template CULTURE_SENSITIVITY, `default_assignee` "Microbiology Lab 105", active.
  - 187 tests in "Microbiology & Parasitology": `performing_role` "Microbiologist" (free text), template NUMERIC_TABLE, no `default_assignee`, all active.
- **Why nothing reaches Room 105:**
  1. For `URINE_C_S`, rule 3 looks for a LAB_TECH with `department == "Microbiology"`. None exists (`tech_kamal` is Hematology, `tech_nasrin` is Biochemical Tests), so the order becomes `UNASSIGNED` with destination text "Microbiology Lab 105" and no technician.
  2. The 187 imported microbiology tests use `performing_role` "Microbiologist", so they fall to rule 4 with no `default_assignee` → `UNASSIGNED`.
  3. Nothing links the room/destination to any staff member, and worklist visibility is by `assigned_to_id` only. The 4 dev-DB orders "ASSIGNED" to "Microbiology Lab 105" (via the Assign Tests page) have no `assigned_to_id`, so no technician sees them.
- **Evidence query:** active LAB_TECH-routable departments vs staff gave Biochemical Tests ✓, Hematology ✓, Clinical Pathology ✗, **Microbiology ✗**, Serology ✗.
- The same mismatch hits other departments: "Biochemistry" (265 tests) never matches staff "Biochemical Tests"; "Ultrasonography (USG)" never matches "Ultrasonogram".

### 2.5 "Awaiting Doctor"
- **Where it is produced:**
  - invoice confirm, rule 1 (`invoice_service.py`)
  - `record_imaging_performed` (`worklist_service.py`): any test with `requires_doctor`, `performing_role == "DOCTOR"` or template NARRATIVE → `AWAITING_DOCTOR`, line locked
  - `save_test_result` with status ENTERED on a doctor-routed test (`result_service.py`, "4. Update TestOrder operational lifecycle")
  - manual `POST /worklist/{id}/status` with target `AWAITING_DOCTOR`
- **Where it is displayed:**
  - `TechnicianWorklistPage.tsx`: "Doctor Queue" status tab, KPI tile, "Doctor Queue" badge. No action button is offered for it.
  - `GET /worklist/summary` `awaiting_doctor_count`
  - invoice detail sample status "PERFORMED"
  - refund eligibility (imaging lock)
- **Transitions:**
  - Confirm → AWAITING_DOCTOR (doctor-routed)
  - SAMPLE_PENDING / ASSIGNED → (imaging performed) → AWAITING_DOCTOR
  - IN_PROGRESS → (result ENTERED) → AWAITING_DOCTOR
  - AWAITING_DOCTOR → COMPLETED only via `POST /worklist/{id}/status`, which refuses LAB_TECH (403 "Visiting physician or radiologist authorization required"). Before 10D only ADMIN/OWNER could complete; now it is the `result.complete_doctor_routed` permission, which defaults to the same roles.
- **Who should act next:** a doctor/radiologist. **There is no DOCTOR role, no doctor user and no doctor sign-off screen**, so the status is effectively orphaned. Only Admin/Owner can move it on, through the generic status endpoint. `tests.approval_rule` values DOCTOR_REQUIRED / BOTH_SIGNATURES are stored but drive no workflow.
- **Dev DB:** 5 orders AWAITING_DOCTOR: 2 × `USG_L_A` and 2 × `XRAY_CHEST`, with no technician (invisible to every technician), and 1 × `TC-410` (Clinical Pathology, `requires_doctor` true) assigned to `tech_kamal`, who cannot complete it.

### 2.6 Related defects and gaps (not fixed, except where noted)
1. **Fixed (needed for Part 2):** `Invoice` had no `refund_requests` relationship, but `disburse_refund` read `invoice.refund_requests`, so every disbursement crashed with a 500 at the amount check. Fixed with an ORM-only relationship (no schema change).
2. The Assign Tests page sends the destination **id** as the destination name ("6", "2", "1" stored in `assigned_destination`) and never sets `assigned_to_id`.
3. 1,225 imported tests use free-text `performing_role` values ("Microbiologist", "Clinical Biochemist", ...). The code treats only "LAB_TECH" / "DOCTOR" as meaningful.
4. Department naming mismatches between catalog and staff (Biochemistry vs Biochemical Tests, and so on).
5. USG/X-ray seed tests store `sample_type` as the string "None", so `update_order_status` treats them as sample-required.
6. The New Invoice UI adds an "urgent fee" (max 100, 20%) to its preview totals that the backend never charges, so preview and saved totals can differ.
7. The New Invoice payload sends no age/gender, so every visit is stored as age 30, Male (backend defaults).
8. The frontend payment channel list has ROCKET/CARD, but the backend uses POS_CARD (refund disbursement validates against the backend names).
9. `/profile` was gated to front-desk roles, so LAB_TECH cannot open My Profile. Kept identical (`profile.manage` is not in the LAB_TECH defaults); the owner may want to grant it.
10. CASHIER could release a report with a due without an override reason, because the old check blocked only RECEPTIONIST. Kept as the `report.release_with_due` default for CASHIER (flagged for review).
11. ADMIN and OWNER had identical permissions in code; `docs/SCOPE.md` claims Owner-only commission/accounting rights that the modern stack does not enforce. Kept identical; only Owner-account management is now Owner-only.
12. `get_worklist_summary` counts imaging by department names ("Radiology", "Imaging", "Ultrasonogram", "X-Ray") that mostly don't match the catalog.
13. Business-day/drawer balances are stale after the 10B cleanup (from the 2026-11-12 audit; unchanged).

### 2.7 Recommended routing fixes (for a later prompt; nothing implemented)
1. Normalize `tests.performing_role` to an enum (LAB_TECH / DOCTOR / OUTSOURCED) with an Alembic data migration, keeping the free-text label in a new column.
2. Add a department → lab-section mapping (one table, or a dict next to `LAB_SECTIONS`) and route LAB_TECH tests to the section's default technician (`staff.lab_section`) instead of an exact department string. Then Room 105 receives `URINE_C_S` and the 187 microbiology tests.
3. Let a technician's worklist include unassigned orders for their own section ("section queue") in addition to orders assigned to them.
4. Fix the Assign Tests page to send the destination name, and resolve destination → section → default technician so `assigned_to_id` is set.
5. "Awaiting Doctor": either add a DOCTOR role with `result.complete_doctor_routed` and a sign-off screen, or let the section technician for Ultrasonography/Radiology (e.g. `tech_usg`) record the doctor's report. Also fix the `sample_type = "None"` strings.
6. Re-route existing UNASSIGNED / no-technician orders once (data migration with an audit row per order).

## 3. Implementation details

### Part 2 — Refund amount (`backend/app/services/refund_service.py`)
- **New helpers:** `compute_line_refundable_amount`, `compute_line_billed_share`, `_recompute_invoice_after_line_cancel`, `recompute_invoice_refund_status`.
- **Rule:** refundable = `floor(invoice.paid × line.net_price ÷ Σ net_price of all lines)`. The last remaining active line takes everything still uncommitted. The amount is always capped by `paid − Σ(APPROVED + DISBURSED refunds)` and by the line's billed share. Whole taka; the sum over lines can never exceed total paid.
- **Where it applies:** eligibility, pre-sample request, D15 request and approval. At approval the amount is `min(requested, refundable now)`.
- **Approval effects:**
  - The line is cancelled and `refund_due += amount`.
  - `net -= billed share`; the last active line absorbs the remainder, so `net` reaches exactly 0 when everything is cancelled.
  - `due = max(0, net − (paid − committed refunds))`.
  - `payment_status` is recomputed from paid/due.
  - If amount = 0 (unpaid), the request is closed as `COMPLETED`; there is nothing to disburse.
- **Unchanged:** the two-stage approval, self-approval block (`enforce_segregation_of_duties`), original-channel rule and amount-free technician events.
- **Models:** `Invoice.refund_requests` ↔ `RefundRequest.invoice` (`back_populates`; ORM only).
- **Tests:** `tests/test_prompt10d_refunds.py` (6) — unpaid, partially paid, fully paid + disbursement, multiple lines with repeated refunds (Σ = paid exactly), requested amount capped, technician has no access to refund amounts.

### Part 3 — Draft / Finalize
- **Migration `c3d10a7f2b61`:** `invoices.visit_id` nullable; new `invoices.draft_payload` (JSON) and `invoices.finalized_at`. Additive.
- **Service (`invoice_service.py`):**
  - `save_invoice_draft` creates or updates a DRAFT: placeholder number `DRAFT-<10 hex>`, no visit, lines, orders, payment or drawer change; `due` = 0; audit `SAVE_INVOICE_DRAFT` / `UPDATE_INVOICE_DRAFT`.
  - `finalize_invoice_draft` locks the row (`FOR UPDATE`), returns 409 if not DRAFT, then runs the existing confirmation in place (`_confirm_invoice`).
  - `create_and_confirm_invoice` remains for finalizing an unsaved form.
  - Totals are computed by the shared `compute_invoice_totals`.
- **Endpoints:**
  - `POST /invoices/drafts`
  - `PUT /invoices/{id}/draft` (409 after finalize)
  - `POST /invoices/{id}/finalize` (optional body, not repeatable)
  - Reprint is refused for drafts.
- **Drafts excluded from:** dues, dashboard totals and recent invoices, patient history, global search, and the payment filters on the invoice list. A new "Draft" filter shows them. Payments on a draft are refused.
- **UI:**
  - `DualCopyInvoiceModal.tsx`: draft tag shows "Unsaved Draft" or "Saved Draft DRAFT-…"; a "Save Draft" button sits beside it; "Finalize" / "Finalize & Print" replace "Save Invoice" / "Save & Print".
  - `NewInvoicePage.tsx`: shared payload builder, save/update draft, finalize the draft in place, reopen via `?draft_id=`.
  - `InvoicesPage.tsx`: Draft badge, "Continue Draft" action, Drafts filter.
- **Tests:** `tests/test_prompt10d_drafts.py` (5) — draft has no side effects (counts of lines/orders/payments unchanged, not in dues/worklist/payment filters, payment and reprint refused); edit then finalize creates exactly the expected lines/orders/payment and one `CONFIRM_INVOICE`; finalize not repeatable (409); edit after finalize blocked (409); direct finalize still works; technician cannot create drafts.

### Part 4 — One login = one role; Dashboard landing
- **Removed:** `POST /auth/acting-role`, `switch_acting_role`, `SwitchActingRoleRequest`, frontend `switchActingRole` / `switchRole` and the header switcher.
- **Backend:**
  - `get_current_actor` now uses `staff.role` (stale session `acting_role` values are ignored).
  - Login with a different `role` → 403.
  - `get_staff_roles` returns one role.
  - `home_route` = `/dashboard` for all roles; `getRoleHomeRoute` returns `/dashboard`.
- **Migration `d7e5a91c4f02` (data step):**
  - Resyncs the id sequences (the first attempt failed on a lagging `staff_id_seq` and rolled back cleanly; fixed and re-run).
  - Splits multi-role accounts by **moving** the extra `staff_roles` row (UPDATE, no delete) to a new account with the copied password hash, and writes an `ACCOUNT_SPLIT_SINGLE_ROLE` audit row.
  - Adds `uq_staff_roles_staff_id`.
  - **Dev result:** `reception_fatima` RECEPTIONIST + new `cashier_fatima` (id 5) CASHIER; `admin_tariq` ADMIN + new `owner_tariq` (id 6) OWNER; audit rows 861 and 862.
- **Dashboard:** a welcome bar with main-work buttons for every role.
  - `dashboard.view` holders see the financial Bento dashboard.
  - Others (LAB_TECH) see money-free tiles from `/worklist/summary` only.
  - `GET /dashboard` stays 403 for LAB_TECH.
  - The business-day fetch in `AuthContext` now runs only with `business_day.view`.
- **CLI (`manage_users.py`):**
  - `assign-role` sets the single role.
  - `remove-role` is disabled.
  - `create-user` accepts exactly one role.
  - `init-staff-passwords` covers the new usernames.
- **Tests:**
  - `test_prompt09_auth.py` test 01 updated; test 08 rewritten (acting-role → 404, role mismatch → 403).
  - In `tests/test_prompt10d_roles_permissions.py`: split accounts each have exactly one role; acting-role 404; DB rejects a second role row (IntegrityError); LAB_TECH dashboard/summary has no money and `/auth/me` holds no money keys.

### Part 5 — Central permission layer + Create User
- **`backend/app/core/permissions.py`:**
  - `ROLES` (the five roles, in one place).
  - 33 permission keys derived from the old guards and inline checks, each flagged `exposes_money`.
  - `ROLE_DEFAULTS` equal to the old behavior; CASHIER has its own explicit set.
  - `effective_permissions` (defaults then overrides; money keys always removed for LAB_TECH), `has_permission`, `require_permission(key)`.
- **Routes and services:**
  - All 58 guarded routes (55 existing + the 3 new draft routes) now use `require_permission` (the mapping script failed on any unmapped guard). 20 of the 33 keys are flagged `exposes_money`.
  - The old `require_*` guards were deleted.
  - Inline service checks were converted: worklist scoping → `worklist.view_all`; doctor-routed completion → `result.complete_doctor_routed`; business-day close → endpoint `business_day.close`; report release with due → `report.release_with_due`; technician money redaction stays role-based (`is_money_restricted`).
- **Migration `d7e5a91c4f02` (schema):** `staff.lab_section` (+ index); table `staff_permission_overrides` (unique `staff_id, permission_key`).
- **`/api/v1/users`** (11 operations; all `user.manage`):
  - meta, list, create, get, patch, set role, deactivate, reactivate, reset password, get/set overrides.
  - No delete.
  - Every action is audited (`USER_*`); passwords are never returned or logged.
- **Safety rules (server side):**
  - no self-change of role, permissions or active state;
  - OWNER-only creation/modification of OWNER;
  - no granting a key you do not hold;
  - last active `user.manage` holder protected (409);
  - LAB_TECH can never get money keys (400; a direct DB override is ignored);
  - `lab_section` only for LAB_TECH;
  - role change and deactivation revoke sessions.
- **Lab sections:**
  - `backend/app/core/lab_sections.py` (HEMATOLOGY 101, BIOCHEMISTRY 102, MICROBIOLOGY 105, ULTRASONOGRAPHY 204).
  - `backend/scripts/provision_prompt10d_users.py` (dry run by default; `--apply` used) set `tech_kamal` → HEMATOLOGY and `tech_nasrin` → BIOCHEMISTRY, and created `tech_micro` (MICROBIOLOGY) and `tech_usg` (ULTRASONOGRAPHY).
  - New users have no `department`, so **routing is unchanged**; their password hash is copied from `tech_kamal` (existing dev password, not printed).
- **Frontend:**
  - `features/users/UserManagementPage.tsx` (`/users`): Users list cards with Edit / Reset password / Deactivate-Reactivate, plus confirm dialogs for deactivate and reset.
  - Create User tab: details, initial password, single role, lab section for LAB_TECH, active flag, and a permission editor (defaults vs overrides, money keys locked for LAB_TECH, own account locked).
  - The sidebar shows items by permission and adds "User Management".
- **Tests (in `tests/test_prompt10d_roles_permissions.py`):**
  - defaults equal the old gates, plus a 12-case endpoint access matrix;
  - create with lab section, plus an invalid section rejected;
  - override revoke/grant enforced by real endpoints, and removal restores defaults;
  - LAB_TECH money grant rejected, and a DB override ignored;
  - no self-change and no OWNER escalation (ADMIN → 403, OWNER → 201);
  - cannot grant a key you don't hold;
  - deactivate/reactivate/reset (sessions revoked, password never echoed);
  - last-admin protection (409 for deactivate, demote and revoke).
- 24 tests in this file.

### Part 7 — Playwright specs
- **New `frontend/e2e/support/auth.ts`:** `loginAs` / `openAs` sign in through `login-username` / `login-password` / `login-submit-btn`, wait for `/dashboard`, then open the page. Usernames are dev accounts; the password comes **only** from `MEDSCOPE_E2E_PASSWORD`.
- **`test_modal_regression.spec.ts`:** `selectDevRole` removed; the hard-coded test password removed.
- **`receptionist_corrections.spec.ts`:**
  - logs in per test;
  - test 02 checks the admin button by signing in as Admin (switcher code and comment removed);
  - the invoice flow does Save Draft → Finalize with the new test ids;
  - the status list allows "Draft";
  - a header note says it creates records.

### Files
- **New:**
  - `backend/app/core/permissions.py`, `backend/app/core/lab_sections.py`
  - `backend/app/api/v1/endpoints/users.py`, `backend/app/schemas/user_admin.py`, `backend/app/services/user_admin_service.py`
  - `backend/scripts/provision_prompt10d_users.py`
  - migrations `c3d10a7f2b61_prompt10d_invoice_drafts.py`, `d7e5a91c4f02_prompt10d_single_role_permissions.py`
  - `frontend/src/features/users/UserManagementPage.tsx`, `frontend/e2e/support/auth.ts`
  - `tests/test_prompt10d_refunds.py`, `tests/test_prompt10d_drafts.py`, `tests/test_prompt10d_roles_permissions.py`
  - this report
- **Modified:** 15 endpoint modules + router; `core/security.py`; models (`invoice`, `refund`, `user`, `__init__`); schemas (`auth`, `invoice`); services (auth, business_day, dashboard, invoice, patient, payment, refund, report, result, search, worklist); `scripts/manage_users.py`; frontend (`App`, `client`, `types`, `AuthContext`, `Header`, `Sidebar`, `DashboardPage`, `InvoicesPage`, `NewInvoicePage`, `DualCopyInvoiceModal`, `navigation`); both e2e specs; `tests/conftest.py` (single-role fixtures; guard unchanged); `tests/test_prompt09_auth.py`; the nine docs.

## 4. Assumptions and design choices (please confirm or reverse)

| # | Choice | Why / how to reverse |
|---|---|---|
| A1 | **Invoice number at Finalize.** Drafts use a unique placeholder `DRAFT-<hex>` in `invoice_no` and `temp_invoice_id`; the `SD-` number comes from the sequence at Finalize. | Your preferred option; no gaps from drafts. Kept `invoice_no` NOT NULL by using a placeholder instead of NULL. |
| A2 | Drafts keep the form in `draft_payload` (JSON) and create **no** invoice lines; the visit is created at Finalize (hence `visit_id` nullable). | Guarantees zero operational effect. Draft list rows show totals only. |
| A3 | `POST /invoices` still exists and finalizes an unsaved form in one step. | Pressing "Finalize" without saving a draft first; keeps existing tests and integrations working. |
| A4 | **Refund allocation:** proportional to the line's share of Σ line net prices, floored to whole taka; the last active line takes the remainder; capped by uncommitted paid money. Approval re-caps at `min(requested, refundable now)`. | Simple, deterministic, never exceeds paid. A "first-paid-first-allocated" rule would be the alternative. |
| A5 | Zero-amount approval closes the request as `COMPLETED` (an existing documented status); invoice `refund_status` returns to `NO_REFUND` when no money was refunded. | Avoids requests stuck "awaiting disbursement" of ৳0. |
| A6 | After a cancellation, `due = net − (paid − committed refunds)`, and `payment_status` follows paid/due. | Previously `due` was never reduced on cancellation (it overstated money owed). |
| A7 | **Split accounts:** the primary role keeps the username; new usernames are `cashier_fatima` and `owner_tariq`, display name suffixed "— Cashier" / "— Owner", password hash copied, email left empty (no duplicate). | Your rule "keep usernames for primary roles". Change the names with User Management if wanted. |
| A8 | Kept the `staff_roles` table and `auth_sessions.acting_role` (always = the single role); added `uq_staff_roles_staff_id`; `staff.role` is authoritative. | Minimal schema change, as allowed. |
| A9 | Permission defaults **exactly** reproduce the old behavior, including two quirks: CASHIER may release reports with a due (`report.release_with_due`), and LAB_TECH has no `profile.manage`. ADMIN and OWNER are identical except that only OWNER can manage OWNER accounts. | "No accidental permission change". Adjust per user via overrides, or change `ROLE_DEFAULTS`. |
| A10 | Escalation rules added: no granting keys you don't hold; OWNER-only management of OWNER accounts. | Prevents an Admin or a delegated manager from raising privileges. |
| A11 | New section technicians (`tech_micro`, `tech_usg`) have **no `department`**. | Setting "Microbiology" would have silently changed routing (`URINE_C_S` would start auto-routing), which the prompt forbids. |
| A12 | New dev users reuse the existing dev password by copying the hash of a reference account (`tech_kamal`, or the split source). | "Existing dev-password mechanism" without reading or printing the value. |
| A13 | The Dashboard for roles without `dashboard.view` uses only `/worklist/summary`; no new dashboard endpoint. | Keeps content minimal and money-free. |
| A14 | LAB_TECH/ADMIN worklist scoping is now `worklist.view_all` (ADMIN/OWNER default) instead of a role name. | Same default behavior; can be granted per user. |

## 5. Docs changed and labels flipped

All nine docs were updated: `README.md`, `project-context.md` (new Prompt 10D section; earlier 10C decisions marked implemented), `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`.

| Label | Before | Now |
|---|---|---|
| ADL-032 one fixed role | Decided — not yet implemented | **Implemented (10D)**; ADL-028 marked superseded |
| ADL-033 Dashboard landing | Decided — not yet implemented | **Implemented (10D)**; ADL-030 per-role routes marked superseded |
| ADL-034 roles / users / Create User | Decided — not yet implemented | **Implemented (10D)** |
| ADL-035 Draft / Finalize | Decided — not yet implemented | **Implemented (10D)** |
| ADL-036 refund cap | Decided — not yet implemented / Known issue | **Implemented (10D)**; known-issue notes in API, ARCHITECTURE (ADL-019), WORKFLOWS and SCOPE replaced by the rule |
| ADL-037 work order | Decided | Prompt 11 still **not implemented** |
| New | — | ADL-038 central permission layer; ADL-039 invoice number at Finalize |
| SCOPE §5, WORKFLOWS §6, DESIGN §5.1, README, project-context | "not yet implemented" | Implemented; the current-behavior sections were rewritten |

**Left open as before:** the reduced-motion "Pause animations" decision, Prompt 11, routing fixes (new SCOPE §5.1 "Known routing gaps"), and the pre-go-live credential list (TESTING §12; the e2e spec password item is marked done).

Counts updated in the docs: API 79 paths / 92 operations; 29 tables (28 domain); head `d7e5a91c4f02`; pytest 80.

**Final docs-to-code check:** the remaining mentions of acting-role / multi-role / per-role landing routes are inside clearly historical Prompt 09/10 logs or superseded ADLs. No contradiction with the code was left in current-state sections.

## 6. Real command results (2026-11-13)

| Command | Result |
|---|---|
| `python -m pytest -q` (`medscope_test`) | **80 passed**, 0 failed, 8 warnings (pytest collection warnings on ORM classes named `Test*`, and an httpx deprecation) |
| `tsc -b` | exit 0 |
| `npm run lint` (oxlint) | exit 0, **0 errors**, 120 warning lines (same count as the 2026-11-12 audit baseline; I removed the 2 new unused-import warnings I introduced) |
| `vite build` (output to scratchpad; `dist/` untouched) | built in 808 ms; the usual >500 kB chunk warning |
| `alembic heads` | `d7e5a91c4f02 (head)` — single head |
| `alembic current` (dev DB) | `d7e5a91c4f02 (head)` |
| `alembic check` | `No new upgrade operations detected.` |
| OpenAPI | **79 paths / 92 operations** (was 69 / 79: +3 draft routes, +8 paths / 11 ops for users, −1 acting-role) |
| ORM tables | 28 domain tables (+ `alembic_version` = 29) |
| Playwright `test_modal_regression.spec.ts` (read-only grant, servers on 5173/8000 running the new code) | **0 passed, 6 failed.** Every test stopped at `MEDSCOPE_E2E_PASSWORD is not set` right after opening `/login`, before any credential was typed, so no failed-login rows were written. Not a UI result. |
| Playwright `receptionist_corrections.spec.ts` | **Not run**: it creates patients, doctors, referrers and invoices |
| Dev DB backup | `pg_dump` exit 0, `backups/medscope_dcms_pre_prompt10d.dump` |
| Dev DB data changes | 2 split accounts (audit 861/862); lab sections on `tech_kamal` and `tech_nasrin`; `tech_micro` and `tech_usg` created (USER_CREATED audit rows) |

## 7. Deferred, blocked and new risks

- **Blocked — real Playwright result:** to get one, set the dev password and run the read-only spec:
  `$env:MEDSCOPE_E2E_PASSWORD = '<dev password>'; cd frontend; npx playwright test e2e/test_modal_regression.spec.ts`
- **Deferred by instruction:** all routing / Room 105 / "Awaiting Doctor" fixes (§2.7); Prompt 11 soft delete (only user deactivate/reactivate exists); pre-go-live credential cleanup (TESTING §12).
- **Not done (out of scope):** deleting/discarding drafts (Prompt 11); a DOCTOR role.
- **Risks:**
  - Sessions issued before 10D for the split accounts now act as the account's single role. A user who was working as CASHIER under `reception_fatima` must log in as `cashier_fatima`.
  - Drafts accumulate until Prompt 11 adds discard.
  - The `staff_id_seq` lag in the dev DB was corrected by the migration; seeds that insert explicit ids can cause it again (the seed script still does).
  - Two quirks are preserved on purpose (A9) and should get an owner decision.
  - `tests/conftest.py` deletes all `staff_permission_overrides` rows in the **test** DB at session start (`medscope_test` only, guard unchanged).
- **Tracked-but-deleted files:** `git status` still shows the 13 files deleted before this prompt (6 under `prompt/`, 7 under `report/`). They were not restored, moved or deleted further.
- Nothing was committed or pushed.
