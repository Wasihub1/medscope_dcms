# MedScope DCMS — Database & Schema Specification

## 1. Engine & Topology

- **Engine:** PostgreSQL 18 (`127.0.0.1:5432`)
- **Database:** `medscope_dcms`
- **User:** `medscope_app`
- **Migration Engine:** Alembic (SQLAlchemy 2.0 ORM)
- **Current Alembic Head:** `a7d834bc912e` (`prompt07_module13_result_entry_and_module12_fixes.py`)
- **Table Count:** Exactly 26 tables (25 domain entities + 1 `alembic_version` tracking table)

```mermaid
flowchart TD
    Tenant[tenants] --> Staff[staff]
    Tenant --> Patients[patients]
    Tenant --> Referrers[referrers]
    Tenant --> Catalog[tests & destinations]
    Tenant --> Days[business_days & balances]

    Catalog --> Components[test_components]

    Patients --> Visits[visits]
    Visits --> Invoices[invoices]
    Referrers -->|prescribed_by_id| Invoices
    Referrers -->|referrer_id| Invoices

    Invoices --> Lines[invoice_lines]
    Invoices --> Payments[payments]
    Invoices --> Refunds[refund_requests]

    Lines --> Orders[test_orders]
    Orders --> Samples[samples]
    Orders --> Events[test_order_events]
    Orders --> Results[results]
    Results --> ResultItems[result_items]
    Orders --> Reports[report_versions]
    Reports --> Deliveries[report_deliveries]

    Tenant --> Audit[audit_logs & reprint_logs]
    Tenant --> Seq[sequence_counters]
```

---

## 2. Table Catalog (21 Domain Entities)

### Platform & Organization
1. `tenants`: Primary multi-tenant accounts (`id` UUID PK, `slug` UK, `name`, `active`, `default_sample_route` [`QUICK`, `FULL`], `created_at`).
2. `staff`: Clinic employees (`id` PK, `tenant_id` FK, `username` UK, `display_name`, `role` enum [`RECEPTIONIST`, `ADMIN`, `LAB_TECH`, `CASHIER`, `OWNER`], `department` [`Hematology`, `Biochemical Tests`, `Administration`, `Front Desk`], `email`, `phone`, `address`, `active`).

### Patient Intake & Clinical Referrers
3. `patients`: Permanent patient registry (`id` PK, `tenant_id` FK, `patient_code` UK, `name`, `phone`, `alternate_phone`, `gender`, `address`, `created_at`).
4. `visits`: Encounter visits (`id` PK, `tenant_id` FK, `patient_id` FK, `visit_number` UK, `age_value`, `age_unit`, `age_days`, `gender`, `created_by_id` FK, `created_at`).
5. `referrers`: Referring physicians and third-party contacts (`id` PK, `tenant_id` FK, `name`, `degree`, `designation`, `institution`, `phone`, `specialty`, `referrer_type` [`Doctor`, `Consultant`, `Professor`, `Institution`, `Clinic`, `Agent`], `commission_rate` [confidential write-only], `commission_type` [`PERCENTAGE`, `AMOUNT`], `active`).

### Laboratory Catalog & Workstations
6. `test_destinations`: Workstations / rooms (`id` PK, `tenant_id` FK, `name`, `destination_type` [`Technician`, `Room`, `Lab`], `department`, `active`).
7. `tests`: Diagnostic investigation catalog (`id` PK, `tenant_id` FK, `code` UK, `name`, `short_name`, `alternate_names`, `department`, `price`, `sample_type`, `default_assignee`, `turnaround_hours`, `performing_role` [`LAB_TECH`, `DOCTOR`], `requires_doctor` [boolean], `report_template` [`NUMERIC_TABLE`, `NARRATIVE`, `CULTURE_SENSITIVITY`, `HISTOPATHOLOGY`], `approval_rule` [`TECHNICIAN_FINAL`, `DOCTOR_REQUIRED`, `BOTH_SIGNATURES`], `is_outsourced` [boolean], `active`). **Scale:** 1,250 active clinical tests under tenant `center-seba-01` across 10 diagnostic departments.
8. `test_components`: Individual measurable components/analytes belonging to a test profile (`id` PK, `tenant_id` FK, `test_id` FK, `name`, `unit`, `ref_min`, `ref_max`, `critical_min`, `critical_max`, `impossible_min`, `impossible_max`, `sort_order`, `active`).

### Billing, Payments & Ledgers
9. `invoices`: Master invoice charges (`id` PK, `tenant_id` FK, `invoice_no` UK, `patient_id` FK, `visit_id` FK, `prescribed_by_id` FK [Doctor only], `referrer_id` FK [Doctor/Third Party], `status`, `payment_status`, `refund_status` [`NO_REFUND`, `REFUND_PENDING`, `PARTIALLY_REFUNDED`, `FULLY_REFUNDED`, `REFUND_REJECTED`], `gross`, `discount`, `net`, `paid`, `due`, `refund_due`, `urgent`, `created_at`, `created_by_id` FK).
10. `invoice_lines`: Line items (`id` PK, `tenant_id` FK, `invoice_id` FK, `test_id` FK, `test_code_snapshot`, `test_name_snapshot`, `department_snapshot`, `unit_price_snapshot`, `discount_type`, `discount_value`, `discount_amount`, `net_price`, `urgent`, `status`, `is_locked` [boolean, Module 12 sample lock], `locked_at`, `locked_reason`).
11. `payments`: Payment receipts (`id` PK, `tenant_id` FK, `invoice_id` FK, `amount`, `method`, `reference`, `change_amount`, `business_day_id` FK, `received_at`, `received_by_id` FK).

### Laboratory Operations & Workflow
12. `test_orders`: Diagnostic lab orders (`id` PK, `tenant_id` FK, `invoice_line_id` FK UK, `status` [`UNASSIGNED`, `ASSIGNED`, `PENDING`, `SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `COMPLETED`, `CANCELLED`, `REJECTED`, `SPOILED`], `outcome` [`NOT_PERFORMED` under D15, null], `urgent` [boolean], `department`, `performing_role`, `turnaround_hours`, `sample_route` [`QUICK`, `FULL`], `patient_followup_required`, `patient_contact_status`, `patient_contacted_at`, `patient_contact_notes`, `culture_stage`, `outsourced_status`, `outsourced_lab_name`, `outsourced_sent_at`, `outsourced_received_at`, `outsourced_ref_no`, `assigned_destination`, `assigned_to_id` FK, `assigned_at`, `assigned_by_id` FK, `created_at`).
13. `assignment_history`: Workstation and staff routing audit (`id` PK, `tenant_id` FK, `test_order_id` FK, `previous_assignee`, `new_assignee`, `reason`, `changed_by_id` FK, `changed_at`).
14. `samples`: Specimen collection records (`id` PK, `tenant_id` FK, `test_order_id` FK UK, `sample_code` UK, `temp_sample_id` [offline barcode], `sample_type`, `status` [`COLLECTED`, `REJECTED`, `SPOILED`], `collected_at`, `collected_by_id` FK, `rejected_at`, `rejected_by_id` FK, `rejection_reason`, `rejection_notes`).
15. `test_order_events`: Append-only operational lifecycle history (`id` PK, `tenant_id` FK, `test_order_id` FK, `event_type`, `stage`, `description`, `notes`, `actor_id` FK, `actor_name`, `actor_role`, `created_at`).
16. `results`: Master clinical result record (`id` PK, `tenant_id` FK, `test_order_id` FK UK, `status` [`DRAFT`, `ENTERED`], `entered_by_id` FK, `entered_at`, `findings`, `impression`, `comments`, `ultrasound_data` JSON, `created_at`, `updated_at`).
17. `result_items`: Individual component results snapshotted at time of entry (`id` PK, `result_id` FK, `test_component_id` FK, `component_name_snapshot`, `numeric_value`, `text_value`, `unit_snapshot`, `ref_min_snapshot`, `ref_max_snapshot`, `critical_min_snapshot`, `critical_max_snapshot`, `flag` [`LOW`, `HIGH`, `CRITICAL`, `NORMAL`, null], `sort_order`).
18. `report_versions`: Final diagnostic reports (`id` PK, `tenant_id` FK, `test_order_id` FK, `report_no` UK, `version`, `status`, `authorized`, `findings_summary`, `issued_at`, `issued_by_id` FK).
19. `report_deliveries`: Handover events (`id` PK, `tenant_id` FK, `report_version_id` FK, `delivered_to_name`, `delivered_to_phone`, `delivered_to_relation`, `delivered_with_due`, `due_release_reason`, `delivered_at`, `delivered_by_id` FK).

### Financial Gating & Drawer Lifecycle
20. `refund_requests`: Pre-sample and D15 Not Performed refund requests (`id` PK, `tenant_id` FK, `invoice_id` FK, `invoice_line_id` FK, `request_type` [`PRE_SAMPLE_CANCELLATION`, `D15_NOT_PERFORMED`], `amount`, `reason`, `status` [`PENDING_ADMIN_APPROVAL`, `APPROVED`, `REJECTED`, `COMPLETED`], `requested_by_id` FK, `requested_at`, `reviewed_by_id` FK, `reviewed_at`, `review_notes`, `disbursed_at`, `disbursed_by_id` FK, `disbursement_method`, `disbursement_reference`).
21. `business_days`: Operational day status (`id` PK, `tenant_id` FK, `day_number`, `business_date`, `status`, `opening_float`, `opening_balance`, `total_received_today`, `total_refunds`, `current_balance`, `opened_at`, `opened_by_id` FK, `closed_at`, `closed_by_id` FK).
22. `business_day_channel_balances`: Balances by channel (`id` PK, `business_day_id` FK, `channel`, `opening_balance`, `received_amount`, `current_balance`).

### Concurrency & Audit Control
23. `sequence_counters`: Concurrency-safe monotonic numbers (`id` PK, `tenant_id`, `seq_type`, `year_month`, `current_val`, `updated_at`).
24. `audit_logs`: Detailed system audit ledger (`id` PK, `tenant_id`, `actor_id`, `acting_role`, `action`, `entity_type`, `entity_id`, `before_value`, `after_value`, `created_at`).
25. `reprint_logs`: Invoice/report reprint audit records (`id` PK, `tenant_id`, `entity_type`, `entity_id`, `reprinted_by_id` FK, `reason`, `reprinted_at`).

---

## 3. Migration History & Alembic Evolution

| Revision ID | Description | Operations Performed | Reversibility |
| :--- | :--- | :--- | :--- |
| `5e7d6e556c9d` | Initial Receptionist Slice | Created initial 21 domain tables, indexes, constraints, and sequences. | Full downgrade |
| `c94589ffc4ee` | Add `prescribed_by_id` to Invoices | Added `prescribed_by_id` nullable integer column with foreign key to `referrers(id)` and index `ix_invoices_prescribed_by_id`. | Full downgrade |
| `bdc0201a1170` | Add `refund_status` to Invoices | Added `refund_status` VARCHAR(50) column with server default `NO_REFUND`, index `ix_invoices_refund_status`, and automated data backfill for existing partially and fully refunded invoices. | Full downgrade |
| `e05b9b1a2c3d` | Prompt 05 Catalog Routing & Worklist | Added Test Catalog readiness fields (`turnaround_hours`, `performing_role`, `requires_doctor`, `report_template`, `approval_rule`, `is_outsourced`) to `tests`; added `department` and index to `staff`; added `default_sample_route` to `tenants`; added operational tracking (`urgent`, `department`, `performing_role`, `turnaround_hours`, `sample_route`) to `test_orders`. | Full downgrade |
| `f16c024d3e4a` | Prompt 06 Specimen Lifecycle & Line Locks | Added line locks (`is_locked`, `locked_at`, `locked_reason`) to `invoice_lines`; added specimen audit fields (`temp_sample_id`, `rejected_at`, `rejected_by_id`, `rejection_reason`, `rejection_notes`) to `samples`; added tracking & extensions (`patient_followup_required`, `patient_contact_status`, `culture_stage`, `outsourced_status`, etc.) to `test_orders`; created append-only `test_order_events` table. | Full downgrade |
| `a7d834bc912e` | Prompt 07 Module 13 Results & Module 12 Fixes | Created `test_components`, `results`, `result_items` tables with indexes and unique constraints; added `outcome` column to `test_orders`; added `request_type`, `disbursed_at`, `disbursed_by_id`, `disbursement_method`, `disbursement_reference` to `refund_requests`. | Full downgrade |

### Safe Migration Command:
```powershell
python -m alembic -c backend/alembic.ini upgrade head
```

---

## 4. Key Indices & Database Constraints

1. **Single Open Business Day:**
   ```sql
   CREATE UNIQUE INDEX idx_business_day_single_open ON business_days(tenant_id) WHERE status = 'OPEN';
   ```
2. **Prescribed By Foreign Key:**
   ```sql
   ALTER TABLE invoices ADD CONSTRAINT fk_invoices_prescribed_by_id FOREIGN KEY (prescribed_by_id) REFERENCES referrers (id);
   CREATE INDEX ix_invoices_prescribed_by_id ON invoices (prescribed_by_id);
   ```
3. **Monotonic Sequence Uniqueness:**
   ```sql
   CREATE UNIQUE INDEX uq_seq_tenant_type_ym ON sequence_counters(tenant_id, seq_type, year_month);
   ```
4. **High-Speed Search Indices:**
   - `idx_patients_phone_name ON patients(phone, name);`
   - `idx_invoices_status_created ON invoices(tenant_id, payment_status, created_at);`
   - `idx_test_orders_status ON test_orders(tenant_id, status);`
   - `idx_reports_authorized_status ON report_versions(tenant_id, authorized, issued_at);`

---

## 5. Active Data Volume & Diagnostic Catalog Scale

As of November 2026, the primary operational tenant `center-seba-01` hosts **1,250 active clinical tests** in PostgreSQL, fully indexed by `(tenant_id, code)` and `(tenant_id, name)`:

| Department | Active Tests | Typical Turnaround | Primary Template |
| :--- | :---: | :---: | :--- |
| **Clinical Pathology** | 469 | 2 - 6 hours | `NUMERIC_TABLE` |
| **Biochemistry** | 265 | 4 - 8 hours | `NUMERIC_TABLE` |
| **Microbiology & Parasitology** | 187 | 24 - 48 hours | `CULTURE_SENSITIVITY` |
| **Endocrinology & Immunology** | 136 | 6 - 24 hours | `NUMERIC_TABLE` |
| **Hematology** | 71 | 2 - 4 hours | `NUMERIC_TABLE` |
| **Histopathology & Cytopathology** | 45 | 48 - 72 hours | `NARRATIVE` |
| **Ultrasonography (USG)** | 34 | 1 - 2 hours | `NARRATIVE` (Requires Doctor) |
| **X-Ray & Radiology** | 13 | 2 - 4 hours | `NARRATIVE` |
| **Serology & Immunology** | 3 | 4 - 6 hours | `NUMERIC_TABLE` |
| **Cardiology & Neuro Diagnostics** | 2 | 1 - 2 hours | `NARRATIVE` |
| **Total Active Catalog** | **1,250** | | |

### Multi-Tenant Isolation Invariant
All test catalog items, staff, patients, invoices, test orders, and financial transactions enforce strict tenant scoping via `tenant_id = 'center-seba-01'`. The database layer strictly validates that all queries and joins are scoped to `actor.tenant_id`. Any manually imported records must specify the active tenant ID (`center-seba-01`) to be accessible in the user interface.
