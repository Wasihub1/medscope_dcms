# MedScope DCMS — REST API Specification

## 1. Specification Overview

The MedScope backend provides a RESTful JSON API rooted at `/api/v1`. All monetary values are serialized as whole Bangladeshi Taka integers (`int`).

### Endpoint & Operation Registration Count
- **Unique Paths:** 130 paths / 145 operations registered in FastAPI OpenAPI schema (Prompt 19B).
- **Total Operations:** 110 HTTP operations (Prompt 11; 98 after 10F, +12; the older breakdown follows) — was 94 HTTP operations across 16 modules (Prompt 10D added 3 invoice draft routes and 11 user-management operations (8 paths), and removed `POST /auth/acting-role`; Prompt 10E added `GET /worklist/rooms` and `POST /worklist/{id}/reassign`). **98 operations after Prompt 10F**, which added `GET /assignments/orders`, `GET /worklist/{id}/result-preview`, `GET /reports/ready` and `GET /reports/ready/{id}/preview` (all read-only).
- **Authorization (Prompt 10D):** every route requires a named permission key from `backend/app/core/permissions.py` (see §5). The "Roles" columns below show the default roles holding that key; per-user overrides can add or remove keys (never money keys for LAB_TECH or DOCTOR).
- **Prompt 10E field changes (summary):** invoice create/draft take `age_value`, `age_unit`, `gender` (Finalize requires age and gender), `initial_payment_channel_detail` (or `initial_payment.channel_detail`); invoice responses carry `urgent_fee` (computed by the backend), `age_value`, `age_unit`, `visit_gender`, and per line `line_urgent_fee`, `lab_section`; payments carry `channel_detail`; tests carry `lab_section`; patients carry `last_age_value`, `last_age_unit`; worklist items carry `requires_sample`, `is_imaging`, `lab_section`, `lab_section_label`, `report_ready`; the worklist summary carries `ready_count`, `unassigned_count`, `lab_section`.
- **Prompt 10F changes (summary):** 4 new read-only GET endpoints (above); no new permission key (35 keys, 20 money keys); `POST /worklist/{id}/reassign` now also returns **409** for cancelled and Not Performed orders; new **400** sample gates on `POST /worklist/{id}/culture-stage` and `POST /worklist/{id}/outsourced` (`SENT`); sample-gate messages are plain ("Take the sample before …"); the invoice line `sample_status` can be `Completed without sample` (legacy orders); `GET /worklist?status=READY`, `report_ready` and `ready_count` use the one shared Ready definition (ENTERED result, completion not required).
- **Prompt 10 Review:** Pure client-side UI/UX implementation; zero backend endpoint modifications or additions.
- **Convenience & Legacy Aliases:** Includes 10 duplicate/convenience alias operations preserved for frontend and client backward compatibility (e.g., `/refunds/review/{id}` and `/refunds/{id}/review`, `/refunds/disburse/{id}` and `/refunds/{id}/disburse`, `/worklist/{id}/result-template` and `/worklist/{id}/result` GET alias).

### Authentication & Stateful Session Transport (Prompt 09)
Stateless header-based identity switching (`X-Staff-Id`, `X-Staff-Role`) has been permanently decommissioned. All requests must present a verified server-side session token:
- **Browser/UI Transport:** Stateful `HttpOnly`, `SameSite=Lax`, `Path=/` cookie named `medscope_session`.
- **API/CLI Client Transport:** `Authorization: Bearer <session-token>` header.
- **CSRF Defense:** Mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`) require the `X-Requested-With: XMLHttpRequest` header.
- **Session Lifecycle:** 120-minute idle sliding window (`SESSION_IDLE_TIMEOUT_MINUTES=120`), 24-hour absolute maximum lifetime (`SESSION_ABSOLUTE_LIFETIME_HOURS=24`).
- **Password Security:** Argon2id hashing (`argon2-cffi`), 5 consecutive failed attempts lockout (`AUTH_MAX_FAILED_ATTEMPTS=5`), and generic authentication error messages.

---

## 2. API Endpoints by Module

### 2.1 Business Day (`/api/v1/business-day`)
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/business-day/status` | Get current drawer state, status (`OPEN`/`CLOSED`), opening float, collections today, and channel balances. | All | 200 |
| `POST` | `/business-day/open` | Open morning business day with opening float amount. | All | 200, 400 |
| `POST` | `/business-day/close` | Close the active business day with counted cash (`counted_cash` required; optional `counted_channels`, `variance_reason`, `notes`, `day_id` to re-close a reopened day). 400 when a variance above the tolerance has no reason. See section 13. | **Admin, Owner** | 200, 400, 422, **403 (Receptionist, Cashier)** |

### 2.2 Dashboard (`/api/v1/dashboard`)
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/dashboard/summary` | Today's key operational metrics: patients count, gross amount, net collected, pending dues, deliverable reports count. | All | 200 |
| `GET` | `/dashboard/recent-invoices` | List recent 10 invoices with live status tags for rapid counter access. | All | 200 |

### 2.3 Global Search (`/api/v1/search`)
| Method | Path | Summary | Query Params | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/search` | Global instant search across Patients, Invoices, Tests, Samples, and Reports. | `q`: search string (min 2 chars), `limit`: max results | 200 |

### 2.4 Patients (`/api/v1/patients`)
| Method | Path | Summary | Request / Query | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/patients` | Search patient directory by name, phone, or MRN. | `q`: search keyword, `limit`: int | 200 |
| `GET` | `/patients/{id}` | Retrieve patient demographics. | `id`: patient integer ID | 200, 404 |
| `POST` | `/patients` | Register new patient; validates phone duplication; generates monotonic MRN. | Body: `{ full_name, phone, gender, age_years, age_months, address, blood_group }` | 201, 400 |
| `GET` | `/patients/{id}/history` | Retrieve full history: demographic profile, visits list, invoices with tests summary, payments, lifetime spent, and lifetime due. | `id`: patient integer ID | 200, 404 |

### 2.5 Referrers (`/api/v1/referrers`)
| Method | Path | Summary | Request / Query | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/referrers` | Search active referrers. Supports `?type=Doctor` for medical prescriber list. | `q`: query, `type`: optional filter (`Doctor`), `limit`: int (default `100`, max `500`) | 200 |
| `POST` | `/referrers` | Register new referrer inline. Accepts confidential `commission_rate` (0-100%) and `commission_type` on write; response strictly strips commission fields for privacy. | Body: `{ name, degree, specialty, phone, type, commission_rate, commission_type }` | 201, 400 |

### 2.6 Tests & Destinations (`/api/v1/tests`)
| Method | Path | Summary | Request / Query | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/tests` | Search and list active diagnostic investigations. Returns full catalog with prices, departments, turnaround hours, template types, and approval rules. | `q`: optional search string (name, code, short name), `department`: optional department filter, `limit`: optional max results (default `2500`, max `10000`) | 200 |
| `GET` | `/tests/destinations` | List active laboratory workstation benches/rooms. | None | 200 |

**Test Response Schema (`TestResponse`):**
- `id` (int), `code` (str), `name` (str), `short_name` (optional str), `alternate_names` (optional str), `department` (str)
- `price` (int, whole-Taka), `default_price` (int, populated from `price`), `sample_type` (optional str), `default_assignee` (optional str)
- `turnaround_hours` (optional int), `performing_role` (str, default `"LAB_TECH"`), `requires_doctor` (bool, default `False`)
- `report_template` (str, default `"NUMERIC_TABLE"`: `NUMERIC_TABLE`, `NARRATIVE`, `CULTURE_SENSITIVITY`, `HISTOPATHOLOGY`)
- `approval_rule` (str, default `"TECHNICIAN_FINAL"`: `TECHNICIAN_FINAL`, `DOCTOR_REQUIRED`, `BOTH_SIGNATURES`)
- `is_outsourced` (bool, default `False`), `active` (bool)
- `lab_section` (optional str, Prompt 10E): the lab room the test routes to (`HEMATOLOGY`, `BIOCHEMISTRY`, `MICROBIOLOGY`, `ULTRASONOGRAPHY`) or null (no room → routed as UNASSIGNED). There is no catalog create/edit endpoint; the value comes from the mapping in `backend/app/core/lab_sections.py`.

### 2.7 Invoices (`/api/v1/invoices`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/invoices` | List invoices with pagination, filters, and dynamic/persistent `refund_status`. Filter `status` accepts user-friendly event names (`All Payments`, `Paid`, `Unpaid`, `Partial Due`, `Partially Refunded`, `Fully Refunded`) masking PostgreSQL columns. | `q`, `status`, `date_from`, `date_to`, `limit` | 200 |
| `GET` | `/invoices/{id}` | Get full invoice detail with lines, payments, sample states, dynamic `refund_status`, and `refund_requests` list. | `id`: invoice integer ID | 200, 404 |
| `POST` | `/invoices/drafts` | **Prompt 10D.** Save the form as a DRAFT invoice: status `DRAFT`, placeholder number `DRAFT-xxxxxxxxxx`, no visit, lines, orders, payment or drawer change; form kept in `draft_payload`. Permission `invoice.create`. | Body: same as `POST /invoices` | 201, 400, 403, 404 |
| `PUT` | `/invoices/{id}/draft` | **Prompt 10D.** Update a DRAFT. 409 once finalized. Permission `invoice.create`. | Body: same as `POST /invoices` | 200, 404, 409 |
| `POST` | `/invoices/{id}/finalize` | **Prompt 10D.** Finalize a DRAFT in place: assigns the real `SD-` number, creates visit, lines, test orders/routing, payment, drawer update, `CONFIRM_INVOICE` audit. Optional body replaces the saved draft first. Not repeatable (409). Permission `invoice.finalize`. | Optional body | 200, 404, 409 |
| `POST` | `/invoices` | Create and finalize a new invoice in one step (Finalize pressed on an unsaved form). Permission `invoice.finalize`. Supports distinct `prescribed_by_id` (doctor only) and `referrer_id`, duplicate test line prevention, synchronized %/৳ discounts, and default ৳0 initial payment. **Prompt 10E:** Finalize requires `age_value` and `gender` (400 otherwise; drafts may omit them); the urgent fee is computed by the backend (`max(100, round(20% of the line price))` per urgent line, never discounted, included in `net`/`due`); client fee amounts are ignored; `initial_payment_method` must be one of the backend channels and `OTHER` needs `initial_payment_channel_detail`. Returns full `InvoiceDetailResponse` (includes `is_draft`, `finalized_at`, `draft_payload` while DRAFT, `urgent_fee`, `age_value`, `age_unit`, `visit_gender`). | Body: `{ patient_id, prescribed_by_id, referrer_id, age_value, age_unit (years/months/days), gender (Male/Female/Other), lines: [{ test_id, discount_type, discount_value, urgent }], bill_discount_type, bill_discount_value, initial_payment_amount, initial_payment_method, initial_payment_reference, initial_payment_channel_detail, cash_tendered }` | 201, 400, 422 |
| `POST` | `/invoices/{id}/reprint` | Register the reprint in the audit log (`INVOICE_REPRINTED`) and return `InvoiceDetailResponse` with duplicate watermark. | `reason`: query parameter justification | 200, 404 |

### 2.8 Payments & Dues (`/api/v1/payments`, `/api/v1/dues`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/dues` | List invoices with positive pending dues (`due > 0`). | `q`: search filter, `limit`: max results | 200 |
| `POST` | `/payments` | Collect payment against invoice due balance; updates business day drawer balance (a missing channel row is created); validates against overpayment. **Prompt 10E:** `channel` must be `CASH`, `BKASH`, `NAGAD`, `ROCKET`, `POS_CARD`, `BANK_TRANSFER` or `OTHER` (`CARD` is accepted as an alias of `POS_CARD`); `OTHER` requires `channel_detail` (the typed channel name), stored on the payment; non-cash needs a reference. | Body: `{ invoice_id, amount, channel, channel_detail, reference_no, cash_tendered }` | 201, 400 |
| `POST` | `/invoices/{id}/settle-due` | Same rules as `POST /payments`. | Body: `{ amount, method, channel_detail, reference, cash_tendered }` | 201, 400 |

### 2.9 Workstation Assignments (`/api/v1/assignments`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/assignments/unassigned` | Queue of `UNASSIGNED` test orders (each with its waiting room `lab_section` / `lab_section_label`, if any). | `department`: optional filter | 200 |
| `GET` | `/assignments/orders` | **Prompt 10F (Assigned Tests view).** Every test order, newest first: `test_order_id`, `invoice_id`, `invoice_no`, `patient_id`, `patient_name`, `patient_code`, `test_code`, `test_name`, `department`, `lab_section`, `lab_section_label`, `technician_names` (active LAB_TECH of the room; empty when unassigned), `assignment_state` (`ASSIGNED` / `UNASSIGNED`), `status` (`CANCELLED` when the line is cancelled), `urgent`, `result_status`, `worked_by_name`, `created_at`, `can_reassign`, `reassign_block_reason`. **No money field.** Permission `assignment.manage` (Receptionist/Cashier view only, Admin/Owner); `can_reassign` needs `worklist.reassign` and an order that is not COMPLETED, cancelled or Not Performed. | Query: `status` (`ALL`, `OPEN`, `UNASSIGNED`, `ASSIGNED`, `SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `PENDING`, `COMPLETED`, `CANCELLED`, `NOT_PERFORMED`), `lab_section` (room code, `NONE`, `ALL`), `q`, `limit` ≤ 500 | 200, 400 (unknown status), 403 |
| `POST` | `/assignments/assign` | **Prompt 10E:** assign a test order to a lab **room** (never a technician). Send `lab_section` (room key) or a room/destination name; a numeric `destination_id` is resolved to its room name — ids are never stored. `assignment.manage` may route `UNASSIGNED` orders; moving an already routed order needs `worklist.reassign` (403). | Body: `{ test_order_id, lab_section, reason }` | 200, 400, 403, 404, 409 |
| `POST` | `/assignments/{id}/assign`, `/assignments/bulk-assign` | Same rule (path form / several orders). | Body: `{ lab_section }` / `{ assignments: [{ test_order_id, lab_section }] }` | 200, 400, 403 |

### 2.10 Refund Requests (`/api/v1/refunds`)
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/refunds` | List pre-sample and D15 refund requests with joined patient and invoice metadata. | All | 200 |
| `POST` | `/refunds` | Submit pre-sample cancellation refund request; verifies sample has not been collected and line is not locked. | All | 201, 400 |
| `POST` | `/refunds/review/{id}` *(alias: `/refunds/{id}/review`)* | Approve or reject refund request (Admin/Owner). Enforces segregation of duties (`reviewer_id != requested_by_id`, 403 on violation). Approval cancels the line and moves the request to `APPROVED` (or `COMPLETED` when the refund is 0, so there is nothing to disburse). The amount is recomputed at approval with the Prompt 10E rule (see note below). Does NOT record payout. | **Admin, Owner** | 200, **403 (Self-approval or Receptionist/Cashier)** |
| `POST` | `/refunds/disburse/{id}` *(alias: `/refunds/{id}/disburse`)* | Disburse approved refund to patient. Strictly enforces original payment channel validation, mandatory reference for non-cash, and per-channel balance capping; moves request to `COMPLETED`, invoice to `FULLY_REFUNDED`/`PARTIALLY_REFUNDED`, records disburser, updates drawer ledger, and reverses commission. | **Cashier, Receptionist, Admin, Owner** | 200, 400, 404 |

> **Refund amount rule (Prompt 10E; replaces the Prompt 10D proportional allocation).** When a line is cancelled: `net_after = invoice net − line net price` (never below the invoice urgent fee, which is not refunded), `retained_paid = paid − (APPROVED + DISBURSED refunds)`, `refund = max(0, retained_paid − net_after)`, `due = max(0, net_after − (retained_paid − refund))`. Example A 600 + B 400, cancel B: paid 500 → refund 0, due 100; paid 800 → 200 / 0; paid 1000 → 400 / 0; paid 0 → 0 / 600. The server computes the amount at request time (`POST /refunds`, D15 request, `GET /refunds/eligibility`) and recomputes it at approval; any client `amount` is ignored. A refund and a due never coexist after a cancellation; refunds never exceed total paid. Disbursement is restricted to channels used on the invoice (incl. `ROCKET`, `OTHER`; non-cash needs a reference). Technicians and doctors never see amounts.

### 2.11 Reports & Deliveries (`/api/v1/reports`)
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/reports/deliverable` | List **issued** (authorized `report_versions`) reports with financial due status (`is_held_due_to_balance`). Since Prompt 16 it also lists every Final report created by Finalize (`has_snapshot`, `approval_rule` added to each item; the seeded pre-Module-14 reports have `has_snapshot = false`). | All | 200 |
| `GET` | `/reports/ready` | **Prompt 10F.** Ready results from all rooms (not issued reports): ENTERED result, order not cancelled, not Not Performed, not AWAITING_DOCTOR; completion not required (same definition as the Lab Ready tile/tab). Fields: `test_order_id`, `invoice_id`, `invoice_no`, `patient_id`, `patient_name`, `patient_code`, `patient_phone`, `test_code`, `test_name`, `department`, `lab_section`, `lab_section_label`, `order_status`, `urgent`, `result_status`, `result_entered_at` (last save of the submitted result), `result_entered_by_name`, and **only for actors allowed to see money** (not LAB_TECH/DOCTOR and holding `payment.view`) `has_due`, `invoice_due` (keys omitted otherwise). Query `q`, `lab_section` (room code, `NONE`, `ALL`), `limit` ≤ 200. Permission `report.view`. | Receptionist, Cashier, Admin, Owner | 200, 403 |
| `GET` | `/reports/ready/{test_order_id}/preview` | **Prompt 10F.** Read-only, money-free preview of a saved result (DRAFT or ENTERED) from the stored snapshots; same payload as `GET /worklist/{id}/result-preview`. Permission `report.view`. | Receptionist, Cashier, Admin, Owner | 200, 403, 404 (no saved result) |
| `GET` | `/reports/{id}` | Get single deliverable report details. | All | 200, 404 |
| `POST` | `/reports/deliver/{id}` | Hand over report to patient or relation. **Prompt 10E:** with a due, only `report.release_with_due` holders (Admin/Owner by default) may release, and only with `admin_due_override_reason` (400 without); RECEPTIONIST and CASHIER get 403 even with a reason. | All with `report.deliver` | 201, 400, 403 |
| `POST` | `/reports/{id}/override-hold` | Admin emergency release of report with mandatory recorded justification (same rule). | **Admin, Owner** | 201, 400, 403 |
| `GET` | `/reports/printable/{id}` | Retrieve formatted diagnostic report data and register print audit (`REPORT_REPRINTED`). | All | 200, 404 |
| `POST` | `/reports/{id}/print-events` | Log print or reprint audit event for diagnostic report. | All | 200 |

### 2.12 Staff Profile (`/api/v1/profile`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/profile` *(alias `/profile/me`)* | Get the caller's own profile. Permission `profile.manage` (Prompt 10E: now also LAB_TECH and DOCTOR). | Session actor | 200, 403 |
| `PUT` | `/profile` *(aliases `/profile/me`, `PATCH`)* | Update the caller's own personal fields (`display_name`, `phone`, `email`, `address`, `avatar_url`). Only the own record; role immutable. The `UPDATE_OWN_PROFILE` audit row is now committed with the change (Prompt 10E fix). | Body: `{ display_name, phone }` | 200, 403 |

### 2.13 Technician Worklist & Specimen Lifecycle (`/api/v1/worklist`) — Modules 11 & 12
> [!IMPORTANT] Strict Financial-Data Isolation (Section 5.4)
> All endpoints under `/worklist` enforce strict clinical/operational data separation. Response schemas explicitly omit all pricing, gross, net, dues, discounts, commissions, and reagent costs.

| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/worklist` | List laboratory tasks. Filterable by `status` (`ASSIGNED`, `UNASSIGNED`, `SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `REJECTED`, `CULTURE`, `IMAGING`, `OUTSOURCED`, `COMPLETED`, and since Prompt 10E `READY`, `LATE`). **Prompt 10F:** `READY` = ENTERED result on an order that is not cancelled, not Not Performed and not AWAITING_DOCTOR (completion not required; one shared definition with `ready_count`, `report_ready` and `/reports/ready`); `IMAGING` uses the same imaging definition as the sample rule, `department`, `urgent_only`, `q`, `staff_id` (Admin: that technician's room). **Prompt 10E visibility:** LAB_TECH sees every order of their room (`lab_section`), Admin/Owner (`worklist.view_all`) everything, DOCTOR (`worklist.doctor_queue`) the AWAITING_DOCTOR orders of all rooms plus completed doctor-routed orders. Items carry `requires_sample`, `is_imaging`, `lab_section`, `lab_section_label`, `report_ready`. | **Lab Tech, Doctor, Admin, Owner** | 200, 403 |
| `GET` | `/worklist/summary` | KPI tile counts with the same visibility as the list (Room Queue, Urgent STAT, Sample Pending, In Progress, Awaiting Doctor, Rejected, Late, Ready (`ready_count`), Unassigned (`unassigned_count`), Completed, Culture, Imaging, Outsourced). Before 10E an Admin's summary counted only orders assigned to the Admin. | **Lab Tech, Doctor, Admin, Owner** | 200, 403 |
| `GET` | `/worklist/rooms` | **Prompt 10E.** The four lab rooms with the number of active technicians. Any of `worklist.view`, `worklist.reassign`, `assignment.manage`. | Lab, front desk, Admin, Owner | 200, 403 |
| `POST` | `/worklist/{id}/reassign` | **Prompt 10E.** Move an order to another room any time before `COMPLETED` (409 after, or when cancelled; **Prompt 10F:** also 409 for Not Performed — REJECTED/SPOILED or outcome NOT_PERFORMED). Used by My Work and by the Assigned Tests view. Keeps samples/results; ASSIGNED/UNASSIGNED re-evaluated for the new room; audit `REASSIGN_ROOM`. Body `{ lab_section, reason? }`. Permission `worklist.reassign`. | **Admin, Owner** (grantable) | 200, 400, 403, 404, 409 |
| `POST` | `/worklist/{id}/sample-taken` | Specimen collection action (Quick & Full Route). Records collection timestamp in `samples` table, locks corresponding invoice line against ordinary cancellation/refund (`is_locked = True`), triggers reagent stock consumption boundary, logs `SAMPLE_COLLECTED` lifecycle event, and starts Lab Clock. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/reject-sample` | Record spoiled or rejected specimen (Section 5.3 & D15 rule). Requires mandatory rejection reason. Marks task as `REJECTED` or `SPOILED`, preserves invoice line lock, logs `SAMPLE_REJECTED` lifecycle event, and flags patient for contact follow-up. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/patient-contact` | Record patient call follow-up for spoiled/rejected specimen (`CALLED`, `RECOLLECTION_AGREED`, `REFUND_REQUESTED`). Enforces that recollection requires a new bill line; no free re-runs. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/imaging-performed` | Record radiology/imaging examination performed. **Prompt 12: does not lock the line** (it locks at result completion); transitions order to `AWAITING_DOCTOR`. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/culture-stage` | Progress culture test through multi-day stages (`INCUBATING`, `PRELIMINARY`, `FINAL`). Moving to `FINAL` decouples from order status (order remains `IN_PROGRESS`). Preserves timestamps and actor attribution in lifecycle history. **Prompt 10F:** 400 "Take the sample before this step" when the test needs a sample and none is collected. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/outsourced` | Record outside referral laboratory dispatch (`SENT`) or specimen receipt (`RECEIVED`) with tracking/reference number. **Prompt 10F:** `SENT` returns 400 "Take the sample before this step" when the test needs a sample and none is collected. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `GET` | `/worklist/{id}/events` | Retrieve full append-only operational lifecycle history and event timeline for a laboratory order. Monetary amounts (`Tk`, `৳`) are dynamically redacted for `LAB_TECH` callers. | **Lab Tech, Admin, Owner** | 200, 403, 404 |
| `GET` | `/worklist/{id}/barcode` | Generate Code 128 vector SVG barcode label payload for specimen tubes (50mm x 25mm / 50mm x 30mm thermal label printers). Strictly financial-free. | **Lab Tech, Admin, Owner** | 200, 403, 404 |
| `POST` | `/worklist/{id}/status` | Updates order lifecycle status. Enforces transition invariants: sample-based tasks cannot complete before specimen collection (Prompt 10F: 400 "Take the sample before completing this test…"; NULL `sample_type` on a non-imaging test now requires a sample); culture tests require `culture_stage == "FINAL"` before completion; doctor-required tests require physician authorization; rejected/spoiled tasks cannot complete. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `GET` | `/worklist/{id}/result-template` *(alias: `/worklist/{id}/result`)* | Retrieve result entry template, test component definitions with the reference range and critical limits of the band matching this patient (sex and age in days, §9), impossible bounds, and current draft/entered results. Sample requirement follows `requires_sample` (Prompt 10F rule: imaging and explicit `None`/`N/A`/`NA`/`No sample` are not blocked; NULL/empty `sample_type` on a non-imaging test is blocked with 400 "Take the sample before entering results…"). Since 10F the Preview Report no longer uses this endpoint. | **Lab Tech, Doctor, Admin, Owner** | 200, 400, 403, 404 |
| `GET` | `/worklist/{id}/result-preview` | **Prompt 10F.** Read-only, money-free preview of a saved result (DRAFT or ENTERED) built only from the stored snapshots: patient, test, room, sample code/type, `order_status`, `result_status`, `is_draft`, `is_ready`, findings/impression/comments, structured data, `items[]` (`component_name`, `component_code`, `value`, `unit`, `reference_range`, `ref_min`, `ref_max`, `critical_min`, `critical_max`, `flag`, `comment`). No result-entry guard (completed/rejected/legacy orders stay previewable). Permission `worklist.view` + room access. | **Lab Tech (own room), Doctor (doctor queue), Admin, Owner** | 200, 403, 404 (no saved result) |
| `POST` | `/worklist/{id}/result` | Save clinical result (draft or entered). Enforces impossible-limit validation (HTTP 400 rejection), completed order immutability (HTTP 409 Conflict), specimen collection prerequisite (HTTP 409 Conflict), automatic flag calculations (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`, `None`), and permanent reference range snapshotting (D24). Saving `DRAFT` preserves order status. Prompt 10F: the 409 sample prerequisite applies to DRAFT and ENTERED and now covers NULL `sample_type` on non-imaging tests (message "Take the sample before entering results…"). | **Lab Tech, Admin, Owner** | 200, 400, 403, 404, **409** |
| `POST` | `/worklist/{id}/d15-refund-request` | Submit D15 Not Performed refund request for spoiled or rejected specimen. Queues request to Admin under `PENDING_ADMIN_APPROVAL` with `request_type="D15_NOT_PERFORMED"`. Returns clinical response `D15RefundClinicalResponse` strictly omitting all monetary amounts. | **Lab Tech, Admin, Owner** | 201, 400, 403, 404 |

> **Prompt 10E access note:** every `/worklist` row above that lists "Lab Tech, Admin, Owner" is room based for LAB_TECH (403 for orders of another room). Endpoints guarded by `worklist.view`, `worklist.update` or `result.enter` (list, summary, events, barcode, status, imaging-performed, culture-stage, outsourced, patient-contact, result GET/POST) are also open to **DOCTOR**, limited to the doctor queue. `sample-taken`, `reject-sample` and `d15-refund-request` stay LAB_TECH/Admin/Owner (`sample.manage`, `refund.request_d15`). `assigned_to_id` now records who acted.

### 2.14 Authentication & Session Management (`/api/v1/auth`) — Prompt 09
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Authenticate user with username and password. Prompt 10D: the response carries the single `role`, `permissions` (effective keys), `lab_section`, and `home_route` = `/dashboard` for every role; an optional `role` that differs from the user's role gets 403. On success, issues `medscope_session` HttpOnly cookie or bearer token, resets failed attempts, and returns user profile with active business day. | Public | 200, 400, 401, 423 |
| `POST` | `/auth/logout` | Revoke active session on server side, clearing cookie and marking session revoked in database. | Authenticated | 200 |
| `GET` | `/auth/me` | Retrieve current authenticated staff profile, assigned roles, acting role, and active business day. Automatically slides idle expiration. | Authenticated | 200, 401 |
| `POST` | `/auth/change-password` | Self-service password change. Validates old password, enforces 8+ character complexity, hashes via Argon2id, and revokes all active sessions. | Authenticated | 200, 400, 401 |
| `POST` | `/auth/users/{user_id}/reset-password` *(legacy; prefer `/users/{id}/reset-password`)* | Administrative password reset for staff member. Hashes new password, resets lockout counters, and revokes all staff sessions. | **Admin, Owner** | 200, 400, 401, 403, 404 |
| `POST` | `/auth/users/{user_id}/unlock` | Administratively unlock a locked staff account, resetting failed attempts counter to 0 and clearing lock timestamp. | **Admin, Owner** | 200, 401, 403, 404 |

---

## 3. Dynamic & Persistent Refund Status Specification

The `refund_status` field on `Invoice` and `InvoiceResponse` is persisted in PostgreSQL as a dedicated column and updated across the refund lifecycle:

| Status Code | Meaning |
| :--- | :--- |
| `NO_REFUND` | Clean invoice with zero cancellation activity. |
| `REFUND_PENDING` | Cancellation or D15 request submitted; awaiting Admin review. |
| `REFUND_APPROVED` | Cancellation or D15 request approved by Admin; awaiting cashier disbursement. |
| `PARTIALLY_REFUNDED`| One or more tests refunded and disbursed, active tests remain. |
| `FULLY_REFUNDED` | All tests on the invoice have been cancelled, refunded, and disbursed. |
| `REFUND_REJECTED` | Request was reviewed and rejected by Admin. |

---

## 4. Status Filter Event Masking Specification

The `GET /api/v1/invoices` endpoint accepts user-friendly event names in the `status` query parameter and masks the underlying PostgreSQL columns:

| User-Friendly Filter Event | Target PostgreSQL Column & Condition |
| :--- | :--- |
| **All Payments** | No condition applied (returns all invoices). |
| **Paid** | `invoices.payment_status = 'PAID' AND (invoices.refund_status IS NULL OR invoices.refund_status != 'FULLY_REFUNDED')` |
| **Unpaid** | `invoices.payment_status = 'UNPAID' OR (invoices.paid = 0 AND invoices.due > 0)` |
| **Partial Due** | `invoices.payment_status = 'PARTLY_PAID' OR (invoices.paid > 0 AND invoices.due > 0)` |
| **Partially Refunded** | `invoices.refund_status = 'PARTIALLY_REFUNDED'` |
| **Fully Refunded** | `invoices.refund_status = 'FULLY_REFUNDED' OR invoices.payment_status = 'REFUNDED'` |

---

## 5. User Management (`/api/v1/users`) — Prompt 10D

All routes require `user.manage` (ADMIN, OWNER by default). Roles: OWNER, ADMIN, RECEPTIONIST, CASHIER, LAB_TECH, DOCTOR (Prompt 10E). A LAB_TECH needs a `lab_section` (400 without, on create and on role change); creating, reactivating or moving a LAB_TECH into a room releases that room's UNASSIGNED orders. There is no delete endpoint (Prompt 11). Passwords are write-only: hashed with Argon2id, never returned or logged. Every action writes an audit row (`USER_CREATED`, `USER_UPDATED`, `USER_ROLE_CHANGED`, `USER_DEACTIVATED`, `USER_REACTIVATED`, `USER_PASSWORD_RESET`, `USER_PERMISSIONS_CHANGED`).

| Method | Path | Summary | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/users/meta` | Roles, permission keys (label, group, `exposes_money`), role defaults, money-restricted roles, lab sections. | 200, 403 |
| `GET` | `/users` | List users (role, lab section, active, locked, override count). | 200, 403 |
| `POST` | `/users` | Create a user with exactly one role; `lab_section` only for LAB_TECH; optional `permission_overrides`. | 201, 400, 403, 409 |
| `GET` | `/users/{id}` | Detail with role defaults, overrides and effective permissions. | 200, 404 |
| `PATCH` | `/users/{id}` | Update details (name, phone, email, department, lab section). | 200, 400, 403, 404 |
| `PUT` | `/users/{id}/role` | Set the single role (+ lab section for LAB_TECH); revokes the user's sessions. | 200, 400, 403, 404, 409 |
| `POST` | `/users/{id}/deactivate` / `/users/{id}/reactivate` | Deactivate (revokes sessions) or reactivate. No delete. | 200, 403, 404, 409 |
| `POST` | `/users/{id}/reset-password` | Set a new password; revokes the user's sessions. | 200, 400, 403, 404 |
| `GET` / `PUT` | `/users/{id}/permissions` | Get / set per-user overrides: `{"overrides": {"key": true \| false \| null}}` (null = back to role default). | 200, 400, 403, 404, 409 |

**Safety rules (server side):** no self-change of role, permissions or active state (403); only an OWNER may create, modify or assign OWNER (403); nobody can grant a permission they do not hold (403); money permissions can never be granted to LAB_TECH or DOCTOR (400); the last active user with `user.manage` cannot be deactivated, demoted or lose `user.manage` (409).

### 5.1 Permission keys and default roles

| Key | Default roles |
| :--- | :--- |
| `dashboard.view`, `search.use`, `patient.view`, `patient.create`, `referrer.view`, `referrer.create`, `test_catalog.view`, `invoice.view`, `invoice.create`, `invoice.finalize`, `invoice.reprint`, `payment.view`, `payment.take`, `refund.view`, `refund.request`, `refund.disburse`, `assignment.manage`, `business_day.view`, `business_day.open`, `report.view`, `report.deliver` | RECEPTIONIST, CASHIER, ADMIN, OWNER |
| `profile.manage` | RECEPTIONIST, CASHIER, ADMIN, OWNER, LAB_TECH, DOCTOR (LAB_TECH and DOCTOR since Prompt 10E) |
| `report.release_with_due` | ADMIN, OWNER (CASHIER removed in Prompt 10E) |
| `refund.approve`, `business_day.close`, `user.manage`, `worklist.view_all`, `worklist.reassign` (10E) | ADMIN, OWNER |
| `result.complete_doctor_routed` (also gates doctor sign-off, Prompt 15), `worklist.doctor_queue` (10E) | ADMIN, OWNER, DOCTOR |
| `worklist.view`, `worklist.update`, `result.enter` | LAB_TECH, DOCTOR, ADMIN, OWNER |
| `sample.manage`, `refund.request_d15` | LAB_TECH, ADMIN, OWNER |

35 keys; the 20 keys marked `exposes_money` in `backend/app/core/permissions.py` can never be effective for LAB_TECH or DOCTOR. **Prompt 10F added no key:** the Assigned Tests view reuses `assignment.manage` (view) and `worklist.reassign` (move); Ready Results reuse `report.view`; the due on `/reports/ready` is shown only with `payment.view` to non-restricted roles.

## 6. Prompt 11 — Soft Delete, Restore, Draft Discard, Audit Log

Counts after Prompt 11: **96 paths / 110 operations** (+11 paths, +12 operations); **38 permission keys, 21 money keys** (3 new: `referrer.manage`, `test_catalog.manage`, `audit.view`). **After Prompt 12: 97 paths / 111 operations; 39 permission keys, 21 money keys** (1 new: `invoice.line_unlock`).

**Default of `audit.view`: OWNER = yes, ADMIN = no (the Owner can grant it to an Admin per user), every other role = no.** This is intended and matches the permission-matrix convention for owner-controlled, grantable keys (like "Pay commission / hand over visit fee"). An Admin who does not see **Audit Log** in the sidebar by default is correct, not a defect.

| Method & path | Permission | Notes |
|---|---|---|
| `POST /users/{id}/delete` body `{reason}` | `user.manage` | 400 no reason; 403 self / Owner by non-Owner; 409 already deleted or last active user-manager |
| `POST /users/{id}/restore` | `user.manage` | 409 not deleted; user stays inactive |
| `GET /users/deleted` | `user.manage` | Deleted view list |
| `PATCH /referrers/{id}` body any of `{name, referrer_type, phone, registration_no, specialty, chamber_address}` (Prompt 19) | `referrer.manage` | Edits the existing row in place; only fields sent change; commission is not editable here and is never returned. 400 for an empty name or type, 404, 409 for a deleted record (restore first), 403 for other roles. Audited (`UPDATE_REFERRER`, old and new values). Saved bills, doctor approvals and reports are not rewritten. |
| `POST /referrers/{id}/delete` body `{reason}` | `referrer.manage` | Doctors and 3rd parties; 400 / 404 / 409 |
| `POST /referrers/{id}/restore`, `GET /referrers/deleted` | `referrer.manage` | |
| `POST /tests/{id}/delete` body `{reason}` | `test_catalog.manage` | 400 / 404 / 409 |
| `POST /tests/{id}/restore`, `GET /tests/deleted` | `test_catalog.manage` | |
| `DELETE /invoices/{id}/draft` | `invoice.create` + creator or ADMIN/OWNER | Hard delete; 409 non-DRAFT or draft with operational rows; 403 other staff; 404 |
| `GET /audit-logs` (`domain`, `action`, `entity_type`, `actor_id`, `acting_role`, `q`, `date_from`, `date_to`, `page`, `size`) | `audit.view` | Read only, newest first; items include `domain` and `reason` (parsed from delete rows). `q` is free text over action, entity type / id and the before / after text (a typed `%` or `_` is literal). `domain` is a key from `/audit-logs/meta` (bills, discounts, payments, reports, stock, accounting, settings, permissions, lab, catalog, audit, other) |
| `GET /audit-logs/meta` | `audit.view` | Distinct actions, entity types, acting roles and people, plus the domain list, for the filters |
| `GET /audit-logs/export` (same filters as the list, no paging) | `audit.view` | **Prompt 19B.** CSV (UTF-8 BOM, `audit-log.csv`) of every matching row; cells that start with `=`, `+`, `-` or `@` are prefixed with an apostrophe. Writes one `AUDIT_LOG_EXPORTED` audit row (who, filters, row count). 403 without `audit.view` |

Existing lists (`GET /tests`, `GET /referrers`, global search, assignment technician list, routing, invoice create/draft/finalize) now exclude soft-deleted rows; creating an invoice with a deleted test or referrer returns 400. `POST /auth/login` and session validation refuse a deleted user. Audit actions added: `USER_SOFT_DELETED`, `USER_RESTORED`, `REFERRER_SOFT_DELETED`, `REFERRER_RESTORED`, `TEST_SOFT_DELETED`, `TEST_RESTORED`, `INVOICE_DRAFT_DISCARDED`.

## 7. Prompt 12 — Line Unlock and Imaging Lock

| Method & path | Permission | Notes |
|---|---|---|
| `POST /invoices/lines/{line_id}/unlock` body `{reason}` | `invoice.line_unlock` (OWNER only by default) | D14: reason required (400), line must be locked (409), same business day only (409), 404 unknown line, 403 any other role. Audit `INVOICE_LINE_UNLOCKED`. |

Behavior changes: `POST /worklist/{id}/imaging-performed` no longer locks; `POST /worklist/{id}/status` = `COMPLETED` and a technician-final result save lock no-sample (imaging) lines; `GET /refunds/eligibility/{line}` and the invoice detail `is_eligible_for_pre_sample` no longer have an imaging-specific block (an unlocked imaging line is eligible; a completed one is locked). `audit.view` default is stated above (OWNER yes, ADMIN grantable, others no) and is unchanged.

## 8. Cancellation, Refunds and Business Day State

| Method & path | Permission | Notes |
|---|---|---|
| `POST /refunds/request` (aliases `/refunds`, `/refunds/`) body `{invoice_id, invoice_line_id, reason?}` | `refund.request` | Cancels ONE unlocked line **at once, with no approval and no payout**. `invoice_line_id` is required (400). Any `amount`, `request_type` or payout field in the body is ignored. Returns 201 with the refund record: `status` `APPROVED` (refund due, awaiting payout) or `COMPLETED` (amount 0). 409 `detail: {code, message}`: `SAMPLE_ALREADY_TAKEN` (line locked, including rejected/spoiled specimens), `REQUEST_PENDING`, `ALREADY_CANCELLED`. |
| `GET /refunds/preview/{invoice_line_id}` | `refund.request` | Read-only breakdown: `invoice_total, paid_total, line_price, retained_amount, refund_amount, due_after, net_after, can_request, blocker`. |
| `GET /refunds/preview-invoice/{invoice_id}` | `refund.request` | Read-only whole-invoice breakdown: `can_cancel`, `blocker`, `blocker_message`, `invoice_total`, `paid_total`, `lines[{invoice_line_id, test_name, line_price, refund_amount}]`, `total_refund`, `retained_amount`, `due_after`, `net_after`. A blocked invoice answers 200 with `can_cancel=false`. |
| `POST /refunds/cancel-invoice` body `{invoice_id, reason?}` | `refund.request` | Cancels every remaining line together (201, one refund record per line), only when no line is locked or pending; otherwise **409** (`SAMPLE_ALREADY_TAKEN`, `REQUEST_PENDING`, `ALREADY_CANCELLED`) and nothing changes. All lines, invoice figures and audit rows commit in one transaction; no payout. |
| `GET /refunds/requests/{request_id}/breakdown` | `refund.view` | Approval view of a pending request: live breakdown plus `snapshot_refund_amount` and `differs_from_snapshot`. |
| `GET /refunds/eligibility/{line_id}` | `refund.view` | Same checks as the cancellation; includes `reason_code`. |
| `POST /refunds/review/{id}` (alias `/{id}/review`) | `refund.approve` | Approve/reject a request that waits for approval (D15 requests). Approving a `PRE_SAMPLE_CANCELLATION` request that is still pending needs a non-blank `review_notes` (400) and is refused with 409 `SAMPLE_ALREADY_TAKEN` once the sample was taken. |
| `POST /refunds/disburse/{id}` (alias `/{id}/disburse`) | `refund.disburse` | The only way money is paid out (original payment channel; reference required for non-cash). |
| `GET /invoices/{id}` | `invoice.view` | Each line carries `cancellation_state` (`NONE`, `CANCELLATION_REQUESTED`, `CANCELLED_REFUND_PENDING`, `CANCELLED`, `CANCELLED_REFUNDED`), `display_status` (a cancellation/refund state wins over the sample label) and `can_request_cancellation`; `d15_refund_status` reflects the **newest** request. |
| `GET /business-day/state` | any authenticated role (no permission key) | `{is_open, day_number, business_date}` only; no money field. Same source as `/business-day/status`, which keeps `business_day.view` and its money figures (403 for Lab Tech). |

## 9. Reference Range Versions (D24)

All endpoints need `test_catalog.manage` (Admin and Owner by default; not a money key; no new key). Rows are never edited or deleted.

| Method & path | Notes |
|---|---|
| `GET /reference-ranges/tests/{test_id}` | Components of a test with every band version (`sex`, `age_days_min`, `age_days_max` (null = no limit), `ref_min`, `ref_max`, `critical_min`, `critical_max`, `reference_range_text`, `version_no`, `is_current`, `effective_from`, `retired_at`, `change_note`). |
| `POST /reference-ranges/components/{component_id}/bands` | New band (201). 400 on invalid values (sex not ANY/MALE/FEMALE, min above max, no reference value, critical inside the reference range); 409 `BAND_OVERLAP` when a current band of the same sex overlaps the age span. |
| `POST /reference-ranges/versions/{version_id}/new-version` | New version of the same band (sex and age span unchanged), `version_no + 1`; the old row is marked not current. 409 `NOT_CURRENT` if that version is already superseded or retired. |
| `POST /reference-ranges/versions/{version_id}/retire` body `{reason}` | Retires a band (reason required). Saved results keep their snapshot. |

Result entry (`GET /worklist/{id}/result-template`, `POST /worklist/{id}/result`): each component carries the band chosen for **this patient** (`ref_min`, `ref_max`, `critical_min`, `critical_max`, `reference_range_text`, `reference_range_version_id`, `range_match` = `MATCHED` / `FALLBACK_ANY` / `NO_BAND`). The server picks the band; a client-sent range for a known component is ignored. Saved result items return the same two fields (null on results saved before the versioning).

**Counts: 129 paths / 144 operations; 43 permission keys, 24 money keys.**

## 10. Doctor Sign-off (D22, `/api/v1/doctor-approvals`)

All four endpoints use the existing key `result.complete_doctor_routed` (Admin, Owner, Doctor by default; not a money key; no new key). On top of the key the service checks the role: **Admin/Owner = Path A** (on a doctor's behalf, attestation), **DOCTOR = Path B** (own assigned orders only); any other role gets 403 even if a per-user override granted the key. Responses carry no money field. There is no reject/send-back endpoint.

| Method & path | Notes |
|---|---|
| `GET /doctor-approvals/queue?doctor_id=&q=` | Pending = test approval rule `DOCTOR_REQUIRED` or `BOTH_SIGNATURES`, result `ENTERED`, no approval row yet, order not cancelled / rejected / spoiled / not performed. Response `{scope: 'OWN' or 'ALL', my_doctor, items[]}`. DOCTOR: only orders whose `assigned_doctor_id` is their own doctor profile (the `doctor_id` filter cannot widen it). Admin/Owner: all, optionally filtered by `doctor_id`. |
| `GET /doctor-approvals/{test_order_id}` | One item: `approval_rule`, `path` (`DOCTOR_OWN` / `STAFF_ATTESTATION`), `can_approve` + `blocked_reason`, `technician_name` + `technician_signed_at` (the Module 13 sign-off), `assigned_doctor`, `my_doctor`, existing `approval` (if any) and `preview` (the same read-only result preview object as `GET /worklist/{id}/result-preview`, with the stored reference-range snapshot). 403 for a DOCTOR on an order not assigned to them; 409 for a technician-final test. |
| `POST /doctor-approvals/{test_order_id}/approve` body `{doctor_id?, attestation?, notes?}` | 201 `{id, doctor{id,name,registration_no}, approved_by_user_id, approved_by_name, approved_by_role, is_attestation, notes, approved_at}`. Path A needs `doctor_id` and `attestation: true` (400 otherwise); the doctor must be an active, non-deleted individual doctor (not Agent / Clinic / Institution / Other) with a registration number (409 without). Path B ignores `doctor_id` / `attestation`: the doctor is the login's own linked profile (409 if none linked). 409 when an approval exists, the result is not `ENTERED`, or the order is cancelled / not performed. On success the approval row, a `TestOrderEvent` and an audit row are written in one transaction and the order moves `AWAITING_DOCTOR` / `IN_PROGRESS` -> `COMPLETED` (line locked for no-sample tests); culture tests stay open until the culture stage is FINAL. |
| `POST /doctor-approvals/{test_order_id}/assign-doctor` body `{doctor_id}` (null clears) | Admin/Owner only (403 for DOCTOR). Puts the order in one doctor's queue; audit `DOCTOR_APPROVAL_ASSIGNED`. 409 once approved. |

Audit actions (visible in the Audit Log viewer, entity `TEST_ORDER`): `DOCTOR_APPROVED_OWN_RESULT` (the doctor logged in and approved), `DOCTOR_APPROVAL_RECORDED_BY_STAFF` (staff recorded it on the doctor's behalf; `actor_id` is the staff member, the text names the doctor and registration number) and `DOCTOR_APPROVAL_ASSIGNED`.

User management additions: `POST /users` and `PATCH /users/{id}` accept `doctor_profile_id` (a referrers row of the tenant; only for a DOCTOR user, 400 otherwise); user responses carry `doctor_profile_id` and `doctor_profile_name`. Changing the role away from DOCTOR clears the link; a change is audited as `USER_DOCTOR_PROFILE_CHANGED`.

## 11. Final Reports (Module 14, Prompt 16)

No new permission key. Draft = a result with status DRAFT (no report row). Final = a `report_versions` row with `status = FINAL_AUTHORIZED`, `version = 1`.

| Method & path | Permission | Notes |
|---|---|---|
| `POST /worklist/{test_order_id}/finalize-report` | `result.enter` + room / doctor-queue access to the order | Creates the Final report (201 `{report_version_id, report_no, version, status, finalized_at, finalized_by_name, test_order_id}`). **409** with the reason when: already Final, cancelled / rejected / spoiled / not performed, sample rejected, result missing or still DRAFT, doctor-required or both-signature test without a doctor approval, culture not yet at stage FINAL. 403 for roles without `result.enter` (Receptionist, Cashier). Needed for technician-final tests; doctor-required and both-signature tests are finalized automatically by `POST /doctor-approvals/{id}/approve` (and by the culture FINAL step when the approval came first). |
| `GET /reports/{report_version_id}/snapshot` | `report.view` | The stored, immutable content of a Final report, in the same shape as the result preview plus `report_status = FINAL`, `report_no` and `signatures` (`technician` name / role / time; `doctor` name, registration number, approval time, `is_attestation`). Money-free. 404 for a seeded report that has no snapshot. |
| `GET /reports/ready` (changed) | `report.view` | Rows now carry `approval_rule`, `doctor_approved`, `can_finalize`, `finalize_blocker`. An order with a Final report no longer appears here. |
| `GET /worklist/{id}/result-preview`, `GET /reports/ready/{id}/preview` (changed) | existing | Also return `approval_rule`, `doctor_approved`, `report_status` (`NONE` / `FINAL`), `report_version_id`, `report_no`, `can_finalize`, `finalize_blocker`. |
| `POST /worklist/{id}/result` (changed) | `result.enter` | New optional body field `expected_updated_at` (the `updated_at` of the result when it was opened): a different stored value returns **409** naming who changed it. New 409s: the order has a Final report, or a doctor approval is recorded. `GET .../result-template` and the saved result carry `updated_by_name`. |

Audit actions (entity `REPORT_VERSION`): `REPORT_FINALIZED` (says whether it was explicit or automatic on approval) and `REPORT_READY_NOTIFICATION_DUE`. A `notification_log` row (`REPORT_READY_SMS`, `PENDING_INTEGRATION`) is written; no SMS gateway exists and nothing is sent. No endpoint changes or deletes a Final report's content.

## 12. Handover, Dues, Write-off, Settings and Doctor Balances (Prompt 17)

New permission keys (3): `settings.manage` (Owner), `due.writeoff` (Admin, Owner; money), `doctor_balance.view` (Admin, Owner; money). Existing keys cover the rest.

| Method & path | Permission | Notes |
|---|---|---|
| `GET /settings` | any signed-in role | `{report_hold_when_due, writeoff_admin_limit}`; defaults `true` and `500`. |
| `PUT /settings` body `{report_hold_when_due?, writeoff_admin_limit?}` | `settings.manage` (Owner) | 403 for Admin and others; 422 for a negative limit; each changed value audited (`SETTING_CHANGED`). |
| `GET /reports` (`/reports/deliverable`) `?q=&search=&has_due=&delivery_status=` (changed) | `report.view` | The search now also matches patient number, test name / code and the temporary bill number (plus bill no., report no., name, mobile). `has_due=true/false` works (it was ignored before). `is_held_due_to_balance` and `can_deliver` follow the hold setting (a due with the setting off is not held). |
| `POST /reports/deliver/{id}` (changed) | `report.deliver` | Hold on and a due: 403 for roles without `report.release_with_due`, 400 without a reason for Admin/Owner, logged with the reason. Hold off: no block, no reason needed; audit says "hold setting off". The delivery row (staff, time, recipient, `delivered_with_due`, reason) is the handover log. |
| `GET /reports/printable/{id}` (changed) | `report.deliver` | Reprint: the log row is now **committed** (it was lost before); `is_duplicate` is true after a handover or an earlier print and `reprint_count` counts prints. |
| `GET /dues?q=&bucket=&limit=` (changed) | `payment.view` | Items add `age_days`, `age_bucket` (`0-7`, `8-30`, `31-90`, `90+`), `written_off`. `q` also matches patient number and temporary bill number and is a partial, case-insensitive match on name and phone (it was exact before). `bucket` filters by age. |
| `GET /dues/call-list?bucket=&q=` | `payment.view` | `{bucket_totals, total_due, patients[]}`: patients with unpaid balances, oldest first, each with `total_due`, `oldest_age_days`, `age_bucket`, `invoices[]`. 400 for an unknown bucket. Derived on every call. |
| `POST /invoices/{id}/write-off` body `{amount, reason}` | `due.writeoff` | 201 write-off record. Owner or Admin within the limit (written off so far + amount <= limit): `APPLIED`, due reduced, `written_off` raised, audit `DUE_WRITTEN_OFF` ("Not a discount"). Admin above the limit: `PENDING_OWNER`, nothing changes, audit `DUE_WRITEOFF_REQUESTED`. 400 amount above the due or blank reason; 409 no due / one request already pending; 403 other roles; 404. |
| `GET /dues/write-offs?status=` | `due.writeoff` | Records and requests, newest first. |
| `POST /dues/write-offs/{id}/approve`, `.../reject` body `{note?}` | `due.writeoff` + Owner role | 403 for Admin; 409 when already decided or when the due is now below the requested amount; approving applies it (`DUE_WRITTEN_OFF`), rejecting changes nothing (`DUE_WRITEOFF_REJECTED`). |
| `GET /doctor-balances` | `doctor_balance.view` | `{items[{referrer_id, name, registration_no, wholesale_receivable, professional_fee_payable, last_entry_at}], entry_count, note}`. The two figures are separate and never summed. Empty until Modules 20 / 28 write source rows. |
| `GET /doctor-approvals/queue` (changed) | existing | Optional `limit` (default 200, max 1000). |

## 13. Accounting and Day Close (Modules 21 and 22, Prompt 18)

Reports use the new key `accounting.view` (Admin, Owner; money). Report endpoints take optional `from` / `to` dates (Dhaka dates) and `format=csv` for an Excel-friendly CSV of the same rows.

| Endpoint | Permission | Behavior |
|---|---|---|
| `GET /accounting/cash-book?channel=CASH` | `accounting.view` | One money account: `opening_balance`, rows (`date`, `entry_id`, `event`, `memo`, `money_in`, `money_out`, running `balance`), totals, `closing_balance`. |
| `GET /accounting/income-expense` | `accounting.view` | Per day: test revenue, urgent fee revenue, discount given, income, operating expense, bad debt, cash variance, expense, net, plus totals. Billing basis. |
| `GET /accounting/dues` | `accounting.view` | The Prompt 17 dues list filtered by bill date, with age; `total_due`. |
| `GET /accounting/cost-by-referrer` | `accounting.view` | Per referrer: bills, net billed, cost. Cost is 0 until commission exists; the response carries a `note` saying so. |
| `GET /accounting/journal?business_day_id=&limit=` | `accounting.view` | Entries with their lines, newest first (read only). |
| `GET /business-day/day-screen` | `business_day.close` | Current (or latest) day: status, expected cash terms (`cash`: opening cash, cash collections, cash refunds, bank deposits, owner withdrawals, expenses, `deferred_payouts` all 0, `expected_cash`), per-channel lines (opening, collections, refunds, expected, counted, variance), `movements`, `tolerance`, `unsynced_items` (always 0). |
| `POST /business-day/movements` body `{kind, amount, note?}` | `business_day.close` | `kind` is `BANK_DEPOSIT` or `EXPENSE` (Admin or Owner; expense needs a note) or `OWNER_WITHDRAWAL` (Owner only, else 403). 201; 409 with no open day; 400 above the expected cash or a non-positive amount. Posts the journal entry. |
| `POST /business-day/{id}/reopen` body `{reason}` | `business_day.close` + Owner role | 403 for Admin; 400 without a reason; 409 unless the day is CLOSED. Status becomes `REOPENED`. |
| `POST /business-day/{id}/adjustments` body `{reason, reverse_entry_id?}` or `{reason, lines[{account, debit?, credit?}]}` | `business_day.close` + Owner role | Adjusting entry on a REOPENED day only (409 otherwise). A reversal must reference an entry of that day and can be done once (409); manual lines must balance (400). |
| `PUT /settings` (changed) | `settings.manage` | Also accepts `cash_variance_tolerance` (whole Taka, 0 or more); `GET /settings` returns it. |

Payments, bill confirmation, line cancellation, refund disbursement and write-off keep their contracts; each now also writes its journal entry in the same transaction.

**Prompt 18B behavior changes:** `POST /payments`, `POST /invoices/{id}/settle-due`, `POST /invoices` and `POST /invoices/{id}/finalize` and `POST /refunds/disburse/{id}` return **409** when no day is OPEN and the latest day is CLOSED or REOPENED, and **400** when no day was ever opened (nothing is recorded). `POST /business-day/open` returns **400** while a day is OPEN or REOPENED. `adjusting_entries` in the day screen's `cash` and in each channel line is the net effect of adjusting entries on that account (excluding variance entries).

## 14. Audit Trail (Module 23, Prompt 19B)

The audit log is append-only (database trigger) and is the only audit store; `reprint_logs` no longer exists. New audit actions: `INVOICE_DISCOUNT_CHANGED` and `INVOICE_DISCOUNT_CONFIRMED` (entity `INVOICE`, before / after discount setup: master and per-line mode and value), `INVOICE_INITIAL_PAYMENT` (entity `PAYMENT`, written at confirm next to `CONFIRM_INVOICE`), `INVOICE_REPRINTED` / `REPORT_REPRINTED`, `REPORT_VIEWED` (entity `REPORT`, id = report version), `REPORT_PREVIEW_VIEWED` (entity `REPORT`, id = **test order**) and `AUDIT_LOG_EXPORTED`.

`GET /reports/{id}`, `GET /reports/{id}/snapshot` and `GET /reports/ready/{test_order_id}/preview` now each write one audit row per successful call (permission `report.view`, unchanged); a 404 writes nothing. `POST /reports/{id}/print-events` and `GET /reports/printable/{id}` write `REPORT_REPRINTED`.
