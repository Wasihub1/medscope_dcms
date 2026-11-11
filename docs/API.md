# MedScope DCMS — REST API Specification

## 1. Specification Overview

The MedScope backend provides a RESTful JSON API rooted at `/api/v1`. All monetary values are serialized as whole Bangladeshi Taka integers (`int`).

### Endpoint & Operation Registration Count
- **Unique Paths:** 69 paths registered in FastAPI OpenAPI schema (`len(app.openapi()['paths']) == 69`).
- **Total Operations:** 79 HTTP operations across 15 modules.
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
| `POST` | `/business-day/close` | Reconcile and close the active business day. | **Admin, Owner** | 200, **403 (Receptionist, Cashier)** |

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

### 2.7 Invoices (`/api/v1/invoices`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/invoices` | List invoices with pagination, filters, and dynamic/persistent `refund_status`. Filter `status` accepts user-friendly event names (`All Payments`, `Paid`, `Unpaid`, `Partial Due`, `Partially Refunded`, `Fully Refunded`) masking PostgreSQL columns. | `q`, `status`, `date_from`, `date_to`, `limit` | 200 |
| `GET` | `/invoices/{id}` | Get full invoice detail with lines, payments, sample states, dynamic `refund_status`, and `refund_requests` list. | `id`: invoice integer ID | 200, 404 |
| `POST` | `/invoices` | Create and confirm diagnostic invoice. Supports distinct `prescribed_by_id` (doctor only) and `referrer_id`, duplicate test line prevention, synchronized %/৳ discounts, and default ৳0 initial payment. Returns full `InvoiceDetailResponse`. | Body: `{ patient_id, prescribed_by_id, referrer_id, lines: [{ test_id, discount_type, discount_value, urgent }], bill_discount_type, bill_discount_value, initial_payment_amount, initial_payment_method, cash_tendered }` | 201, 400 |
| `POST` | `/invoices/{id}/reprint` | Register reprint event in `reprint_logs` audit table and return `InvoiceDetailResponse` with duplicate watermark. | `reason`: query parameter justification | 200, 404 |

### 2.8 Payments & Dues (`/api/v1/payments`, `/api/v1/dues`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/dues` | List invoices with positive pending dues (`due > 0`). | `q`: search filter, `limit`: max results | 200 |
| `POST` | `/payments` | Collect payment against invoice due balance; updates business day drawer balance; validates against overpayment. | Body: `{ invoice_id, amount, channel, reference_no, cash_tendered }` | 201, 400 |

### 2.9 Workstation Assignments (`/api/v1/assignments`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/assignments/unassigned` | Queue of test orders needing workstation routing. | `department`: optional filter | 200 |
| `POST` | `/assignments/assign` | Assign single test order to a laboratory workstation. | Body: `{ test_order_id, destination_name, reason }` | 200, 404 |
| `POST` | `/assignments/bulk` | Bulk route multiple test orders to a destination. | Body: `{ order_ids: [int], destination_name }` | 200 |

### 2.10 Refund Requests (`/api/v1/refunds`)
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/refunds` | List pre-sample and D15 refund requests with joined patient and invoice metadata. | All | 200 |
| `POST` | `/refunds` | Submit pre-sample cancellation refund request; verifies sample has not been collected and line is not locked. | All | 201, 400 |
| `POST` | `/refunds/review/{id}` *(alias: `/refunds/{id}/review`)* | Approve or reject refund request (Admin/Owner). Enforces segregation of duties (`reviewer_id != requested_by_id`, 403 on violation). Approval moves request to `APPROVED` and invoice to `REFUND_APPROVED`. Does NOT prematurely record payout. | **Admin, Owner** | 200, **403 (Self-approval or Receptionist/Cashier)** |
| `POST` | `/refunds/disburse/{id}` *(alias: `/refunds/{id}/disburse`)* | Disburse approved refund to patient. Strictly enforces original payment channel validation, mandatory reference for non-cash, and per-channel balance capping; moves request to `COMPLETED`, invoice to `FULLY_REFUNDED`/`PARTIALLY_REFUNDED`, records disburser, updates drawer ledger, and reverses commission. | **Cashier, Receptionist, Admin, Owner** | 200, 400, 404 |

### 2.11 Reports & Deliveries (`/api/v1/reports`)
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/reports/deliverable` | List authorized reports with financial due status (`is_held_due_to_balance`). | All | 200 |
| `GET` | `/reports/{id}` | Get single deliverable report details. | All | 200, 404 |
| `POST` | `/reports/deliver/{id}` | Hand over report to patient or relation. Blocked if invoice has pending due. | All | 201, 400 (if due > 0) |
| `POST` | `/reports/{id}/override-hold` | Admin emergency release of report with mandatory recorded justification. | **Admin, Owner** | 201, 403 (if non-admin) |
| `GET` | `/reports/printable/{id}` | Retrieve formatted diagnostic report data and register print audit. | All | 200, 404 |
| `POST` | `/reports/{id}/print-events` | Log print or reprint audit event for diagnostic report. | All | 200 |

### 2.12 Staff Profile (`/api/v1/profile`)
| Method | Path | Summary | Details | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/profile` | Get current logged-in staff profile information and active role. | Header actor context | 200 |
| `PUT` | `/profile` | Update permitted personal profile fields (`display_name`, `phone`, `avatar_url`). Role remains strictly immutable. | Body: `{ display_name, phone }` | 200 |

### 2.13 Technician Worklist & Specimen Lifecycle (`/api/v1/worklist`) — Modules 11 & 12
> [!IMPORTANT] Strict Financial-Data Isolation (Section 5.4)
> All endpoints under `/worklist` enforce strict clinical/operational data separation. Response schemas explicitly omit all pricing, gross, net, dues, discounts, commissions, and reagent costs.

| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/worklist` | List assigned laboratory operational tasks. Filterable by `status` (`ASSIGNED`, `SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `REJECTED`, `CULTURE`, `IMAGING`, `OUTSOURCED`, `COMPLETED`), `department`, `urgent_only`, `q` (barcode/sample code/MRN). Technicians receive only their own tasks (`assigned_to_id == actor.id`). | **Lab Tech, Admin, Owner** | 200, 403 |
| `GET` | `/worklist/summary` | Aggregate workbench KPI summary tiles (Assigned, Urgent STAT, Sample Pending, In Progress, Awaiting Doctor, Late, Completed, Rejected, Culture, Imaging, Outsourced). | **Lab Tech, Admin, Owner** | 200, 403 |
| `POST` | `/worklist/{id}/sample-taken` | Specimen collection action (Quick & Full Route). Records collection timestamp in `samples` table, locks corresponding invoice line against ordinary cancellation/refund (`is_locked = True`), triggers reagent stock consumption boundary, logs `SAMPLE_COLLECTED` lifecycle event, and starts Lab Clock. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/reject-sample` | Record spoiled or rejected specimen (Section 5.3 & D15 rule). Requires mandatory rejection reason. Marks task as `REJECTED` or `SPOILED`, preserves invoice line lock, logs `SAMPLE_REJECTED` lifecycle event, and flags patient for contact follow-up. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/patient-contact` | Record patient call follow-up for spoiled/rejected specimen (`CALLED`, `RECOLLECTION_AGREED`, `REFUND_REQUESTED`). Enforces that recollection requires a new bill line; no free re-runs. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/imaging-performed` | Record radiology/imaging examination performed. Locks line for doctor interpretation and transitions order to `AWAITING_DOCTOR`. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/culture-stage` | Progress culture test through multi-day stages (`INCUBATING`, `PRELIMINARY`, `FINAL`). Moving to `FINAL` decouples from order status (order remains `IN_PROGRESS`). Preserves timestamps and actor attribution in lifecycle history. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `POST` | `/worklist/{id}/outsourced` | Record outside referral laboratory dispatch (`SENT`) or specimen receipt (`RECEIVED`) with tracking/reference number. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `GET` | `/worklist/{id}/events` | Retrieve full append-only operational lifecycle history and event timeline for a laboratory order. Monetary amounts (`Tk`, `৳`) are dynamically redacted for `LAB_TECH` callers. | **Lab Tech, Admin, Owner** | 200, 403, 404 |
| `GET` | `/worklist/{id}/barcode` | Generate Code 128 vector SVG barcode label payload for specimen tubes (50mm x 25mm / 50mm x 30mm thermal label printers). Strictly financial-free. | **Lab Tech, Admin, Owner** | 200, 403, 404 |
| `POST` | `/worklist/{id}/status` | Updates order lifecycle status. Enforces transition invariants: sample-based tasks cannot complete before specimen collection; culture tests require `culture_stage == "FINAL"` before completion; doctor-required tests require physician authorization; rejected/spoiled tasks cannot complete. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404 |
| `GET` | `/worklist/{id}/result-template` *(alias: `/worklist/{id}/result`)* | Retrieve result entry template, test component definitions with reference ranges, critical and impossible bounds, and current draft/entered results. | **Lab Tech, Admin, Owner** | 200, 404 |
| `POST` | `/worklist/{id}/result` | Save clinical result (draft or entered). Enforces impossible-limit validation (HTTP 400 rejection), completed order immutability (HTTP 409 Conflict), specimen collection prerequisite (HTTP 409 Conflict), automatic flag calculations (`LOW`, `HIGH`, `CRITICAL`, `NORMAL`, `None`), and permanent reference range snapshotting (D24). Saving `DRAFT` preserves order status. | **Lab Tech, Admin, Owner** | 200, 400, 403, 404, **409** |
| `POST` | `/worklist/{id}/d15-refund-request` | Submit D15 Not Performed refund request for spoiled or rejected specimen. Queues request to Admin under `PENDING_ADMIN_APPROVAL` with `request_type="D15_NOT_PERFORMED"`. Returns clinical response `D15RefundClinicalResponse` strictly omitting all monetary amounts. | **Lab Tech, Admin, Owner** | 201, 400, 403, 404 |

### 2.14 Authentication & Session Management (`/api/v1/auth`) — Prompt 09
| Method | Path | Summary | Roles | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Authenticate user with username and password. On success, issues `medscope_session` HttpOnly cookie or bearer token, resets failed attempts, and returns user profile with active business day. | Public | 200, 400, 401, 423 |
| `POST` | `/auth/logout` | Revoke active session on server side, clearing cookie and marking session revoked in database. | Authenticated | 200 |
| `GET` | `/auth/me` | Retrieve current authenticated staff profile, assigned roles, acting role, and active business day. Automatically slides idle expiration. | Authenticated | 200, 401 |
| `POST` | `/auth/acting-role` | Switch current acting role for multi-role staff. Updates session acting role; returns updated profile. | Authenticated | 200, 400, 401, 403 |
| `POST` | `/auth/change-password` | Self-service password change. Validates old password, enforces 8+ character complexity, hashes via Argon2id, and revokes all active sessions. | Authenticated | 200, 400, 401 |
| `POST` | `/auth/users/{user_id}/reset-password` | Administrative password reset for staff member. Hashes new password, resets lockout counters, and revokes all staff sessions. | **Admin, Owner** | 200, 400, 401, 403, 404 |
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

