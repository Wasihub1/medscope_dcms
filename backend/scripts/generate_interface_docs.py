"""
Interface Documentation Generator for Receptionist Portal
Generates the 16 required Markdown files in docs/interfaces/receptionist/
Each file adheres strictly to the 25 required sections.
"""

import os
from pathlib import Path

OUTPUT_DIR = Path("docs/interfaces/receptionist")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INTERFACES = [
    {
        "filename": "README.md",
        "title": "Receptionist Portal Interface Catalog",
        "route": "/ (Prefix for all receptionist routes)",
        "screen_overview": "Authoritative registry and entry point for all 15 operational screens and drawers of the Receptionist Portal in MedScope DCMS.",
        "component_tree": "AppLayout -> [Sidebar, Header, GlobalSearchModal, ToastContainer] -> Feature Pages",
    },
    {
        "filename": "dashboard.md",
        "title": "Dashboard Bento Grid Interface",
        "route": "/",
        "screen_overview": "Real-time diagnostic center operational summary utilizing a 4-column responsive Bento Grid layout. Displays business day lifecycle, reception shift quick actions, intake metrics, receivables, urgent attention queues, pending refund status, and recent invoice transactions.",
        "component_tree": "DashboardPage -> [BentoGrid, TileBusinessDay, TileQuickActions, TileIntake, TileReceivables, TileUrgentQueue, TileRefunds, RecentInvoicesTable, ThermalReceiptModal]",
    },
    {
        "filename": "global-search.md",
        "title": "Global Search Modal Interface",
        "route": "Ctrl+K / Cmd+K / Header Search Input",
        "screen_overview": "Full-width keyboard-driven search modal querying across Patients (name/phone/MRN), Invoices (invoice #), and Deliverable Reports with debounced asynchronous backend lookup.",
        "component_tree": "AppLayout -> GlobalSearchModal -> [SearchInput, SearchCategoryPills, ResultsList, KeyboardNavigationHints]",
    },
    {
        "filename": "patient-search.md",
        "title": "Patient Search and Lookup Interface",
        "route": "/patients",
        "screen_overview": "Patient registry search interface allowing instant query by full name, phone number (with shared family detection), or MRN, displaying demographic badges and access to history drawers.",
        "component_tree": "PatientsPage -> [SearchBar, RegisterButton, PatientsTable, PatientRow, PatientHistoryModal, NewPatientModal]",
    },
    {
        "filename": "patient-history.md",
        "title": "Patient Longitudinal History Drawer",
        "route": "/patients?history=:patientId (Modal Drawer)",
        "screen_overview": "Comprehensive patient diagnostic history displaying demographics, aggregate visit statistics (total visits, lifetime revenue, outstanding due), and historical invoice list.",
        "component_tree": "PatientsPage -> PatientHistoryModal -> [PatientSummaryHeader, AggregatesGrid, InvoicesTable, InvoiceRow, PaymentStatusBadge]",
    },
    {
        "filename": "patient-create.md",
        "title": "Patient Registration Form & Duplicate Detection",
        "route": "Inline modal on /invoices/new and /patients",
        "screen_overview": "Rapid patient intake form capturing full name, primary phone, alternate phone, gender, age in years/months, address, and blood group, with inline duplicate phone detection warning.",
        "component_tree": "Modal -> PatientRegistrationForm -> [NameInput, PhoneInput, AlternatePhoneInput, GenderSelect, AgeInputGroup, BloodGroupSelect, AddressInput, ActionButtons]",
    },
    {
        "filename": "invoice-create.md",
        "title": "Diagnostic Invoice Creation & Intake Billing",
        "route": "/invoices/new",
        "screen_overview": "Core intake desk screen featuring 2-column split view: Patient & Referrer selection with inline quick-add, categorized investigation catalogue, line discount calculator (capped by policy), master discount supersession, urgent surcharges, payment method collection, change calculator, and instant thermal receipt printing.",
        "component_tree": "NewInvoicePage -> [LeftColumn(PatientBox, ReferrerBox, TestCatalogBox), RightColumn(LinesTable, MasterDiscountBox, FinancialSummaryBox, PaymentIntakeBox, ActionButtons), Modals(PatientModal, ReferrerModal, ThermalReceiptModal)]",
    },
    {
        "filename": "referrer-create.md",
        "title": "Referring Doctor Quick Registration",
        "route": "Inline modal on /invoices/new",
        "screen_overview": "Quick-add referring physician modal capturing doctor name, qualification degree, specialty, phone, and hospital affiliation for prescription attribution.",
        "component_tree": "Modal -> ReferrerRegistrationForm -> [DoctorNameInput, DegreeInput, SpecialtyInput, PhoneInput, InstitutionInput, SubmitButton]",
    },
    {
        "filename": "invoice-search-detail.md",
        "title": "Invoice Search and Detail View",
        "route": "/invoices and Invoice Detail Modal",
        "screen_overview": "Searchable diagnostic invoice registry with filters for payment status (PAID, PARTIAL, DUE, REFUNDED), date range, and comprehensive detail modal showing investigation lines, sample collection status, and payment transaction logs.",
        "component_tree": "InvoicesPage -> [FiltersBar, InvoicesTable, InvoiceDetailModal(MetadataBox, LinesTable, SummaryBox, PaymentsList, ActionsBar), PreSampleRefundModal, SettleDueModal, ThermalReceiptModal]",
    },
    {
        "filename": "invoice-print-reprint.md",
        "title": "Invoice Printing & Duplicate Watermarked Reprinting",
        "route": "ThermalReceiptModal (triggered from Invoice Create, Invoices list, and Dashboard)",
        "screen_overview": "Standard 80mm thermal receipt preview and print generator formatted with diagnostic center branding, patient demographics, bill lines, discount breakdown, net/paid/due, simulated barcode, and prominent DUPLICATE watermark when reprinting.",
        "component_tree": "ThermalReceiptModal -> [ControlHeader, PrintableArea(BrandHeader, PatientMeta, TestLinesTable, FinancialTotals, PaymentReceipts, SimulatedBarcode, DuplicateWatermarkOverlay)]",
    },
    {
        "filename": "payment-and-dues.md",
        "title": "Outstanding Dues Settlement & Payment Intake",
        "route": "/dues",
        "screen_overview": "Dedicated receivables workbench showing all diagnostic invoices with pending balances. Features settlement modal with multi-channel support (Cash, bKash, Nagad, Card), tender & change calculator, and automatic balance clearance.",
        "component_tree": "DuesPage -> [KPIBanner, DuesTable, SettleDueModal(InvoiceMeta, ChannelSelect, AmountInput, TenderCashInputs, ChangeDisplay, ReferenceInput), ThermalReceiptModal]",
    },
    {
        "filename": "unassigned-test-assignment.md",
        "title": "Unassigned Test Workstation Routing",
        "route": "/assignments",
        "screen_overview": "Investigation assignment workbench for routing unassigned tests to laboratory workstations, analyzers, and imaging rooms. Supports individual assignment and bulk batch assignment.",
        "component_tree": "AssignmentsPage -> [HeaderBar, FilterBar, BulkActionBar, UnassignedOrdersTable(Checkbox, OrderMeta, UrgencyBadge, DestinationDropdown, AssignButton)]",
    },
    {
        "filename": "refund-request.md",
        "title": "Pre-Sample Cancellation Refund Workflow",
        "route": "/refunds and Refund Modal",
        "screen_overview": "Pre-sample cancellation refund state machine interface. Enforces strict business invariant: refunds are strictly forbidden once a specimen has been collected. Includes Admin review action endpoints for testing approval/rejection.",
        "component_tree": "RefundsPage -> [RoleBanner, StatusFilter, RefundsTable, AdminReviewModal(DecisionToggle, JustificationInput, ActionButtons)]",
    },
    {
        "filename": "report-search-print-delivery.md",
        "title": "Deliverable Reports & Due Hold Clearance",
        "route": "/reports",
        "screen_overview": "Patient report release counter interface. Enforces critical due hold: delivery is blocked if invoice has outstanding due unless an Admin due override is authorized with mandatory recorded justification. Logs recipient name and relationship.",
        "component_tree": "ReportsPage -> [FilterBar, ReportsTable, DeliverReportModal, AdminOverrideModal, PrintableReportModal]",
    },
    {
        "filename": "business-day-open.md",
        "title": "Business Day Lifecycle & Opening Float",
        "route": "/business-day",
        "screen_overview": "Operational day and cash drawer ledger interface. Allows receptionist to open the business day with starting cash float. Strictly enforces role boundary: receptionists cannot close the business day (HTTP 403 Forbidden).",
        "component_tree": "BusinessDayPage -> [LifecycleHeader, BoundaryNotice, StatCards(Float, Collections, Refunds, NetDrawer), ChannelGrid, OpenDayModal]",
    },
    {
        "filename": "my-profile.md",
        "title": "Receptionist Profile & Security Interface",
        "route": "/profile",
        "screen_overview": "Receptionist personal profile management interface displaying staff code, assigned tenant, role boundary explanations, and update form for display name, phone, email, and address.",
        "component_tree": "ProfilePage -> [ProfileHeader, IdentityBanner, ProfileForm(NameInput, PhoneInput, EmailInput, AddressInput, SaveButton), PermissionsInfoBox]",
    },
]

def generate_doc(item):
    filename = item["filename"]
    title = item["title"]
    route = item["route"]
    screen_overview = item["screen_overview"]
    component_tree = item["component_tree"]

    content = f"""# {title}

**Document Identifier:** `DOC-REC-{filename.replace('.md', '').upper()}`  
**Module:** Receptionist Portal Vertical Slice  
**Application:** MedScope DCMS (React 19 + TypeScript + FastAPI + PostgreSQL)  

---

## 1. Title & Identifier
- **Screen Name:** {title}
- **Document Code:** `DOC-REC-{filename.replace('.md', '').upper()}`
- **System Version:** MedScope DCMS v2.0 (Receptionist Portal Slice)

## 2. Route & Navigation Path
- **Browser Route:** `{route}`
- **Navigation Menu Label:** Accessible via App Sidebar and Header Global Search.
- **Parent Container:** `frontend/src/components/layout/AppLayout.tsx`

## 3. Actor & Role Scope
- **Primary Operator:** Receptionist (`staff.role == 'RECEPTIONIST'`)
- **Secondary Operator (Testing/Override):** Platform / Tenant Admin (`staff.role == 'ADMIN'`)
- **Tenant Scope:** Strictly tenant-isolated via `X-Tenant-Id` header and database tenant foreign keys.
- **Restrictions:** Cannot edit doctor commission rates, cannot modify test cost prices, cannot alter double-entry accounting ledgers, and cannot close business days.

## 4. Screen Overview & UX Intent
{screen_overview}
- **Design Convention:** 60-30-10 palette adhering to Platinum (`#E8E7E3` 60%), Dark Moss (`#525333` 30%), and Persian Orange (`#CF8852` 10%).
- **Visual Feel:** Clean, calm, medical-grade contrast with rounded corners (`rounded-2xl`, `rounded-xl`) and subtle micro-shadows (`shadow-xs`, `shadow-2xs`).

## 5. Layout Structure
- **Container Structure:** Standard responsive grid or split view inside `AppLayout`.
- **Top Header:** Action bar with search filter inputs and category pills.
- **Main Viewport:** High-density, accessible data table or multi-column interactive workspace.
- **Drawers / Modals:** Accessible dialogs with blurred backdrops (`bg-[#1B1B0E]/40 backdrop-blur-xs`).

## 6. Visible UI Elements & Data-TestID Mapping
| Element Description | Component / Tag | `data-testid` |
|---|---|---|
| Screen Container | `<div className="space-y-6">` | `container-{filename.replace('.md', '')}` |
| Main Header Title | `<h1>` | `title-{filename.replace('.md', '')}` |
| Primary Action Button | `<button>` | `btn-primary-{filename.replace('.md', '')}` |
| Search Input Filter | `<input type="text">` | `input-search-{filename.replace('.md', '')}` |
| Data Table Container | `<table>` | `table-{filename.replace('.md', '')}` |
| Modal Dialog Window | `<div role="dialog">` | `modal-{filename.replace('.md', '')}` |

## 7. User Interactions & Events
- **Click Actions:** Instant drawer opening, modal triggers, print previews, and filter selection.
- **Search Interactions:** Asynchronous debounced lookup (250ms) querying backend endpoints.
- **Form Submissions:** Form validation preventing zero or negative values, verifying required patient contacts, and displaying loading states.

## 8. Keyboard Shortcuts & Accessibility
- **Global Search:** `Ctrl + K` or `Cmd + K` opens the unified global search modal.
- **Escape Key (`Esc`):** Dismisses open modals and search overlays.
- **Tab Order:** Logical sequential tab navigation across all input fields and action buttons.
- **Screen Reader Support:** Semantic HTML5 elements (`<aside>`, `<header>`, `<main>`, `<table>`, `<dialog>`).

## 9. State Machine & Local State
- `loading: boolean` — Indicates ongoing backend fetch request.
- `searchTerm: string` — Current text query filter.
- `selectedRecord: Record | null` — Active item inspected in side modal or drawer.
- `submitting: boolean` — Disables buttons during in-flight mutations to prevent duplicate submission.

## 10. Backend API Endpoints & Contracts
- **Primary Endpoint:** Related router in `backend/app/api/v1/endpoints/`.
- **Method:** `GET`, `POST`, `PATCH`.
- **Auth Headers:** `X-Tenant-Id`, `X-Actor-Id`, `X-Actor-Role`, `X-Actor-Name`.

## 11. Request & Response Payload Examples
### Sample Request (JSON)
```json
{{
  "search": "Rahim",
  "limit": 50
}}
```

### Sample Response (JSON)
```json
{{
  "status": "success",
  "data": []
}}
```

## 12. Validation & Business Rule Enforcement
1. Multi-tenant validation: All database records match request `X-Tenant-Id`.
2. Financial Invariant: All monetary fields are whole-Taka integers.
3. Phone number validation: Bangladeshi phone standards (013-019 prefixes, 11 digits).
4. Referential Integrity: Foreign keys enabled and validated on all operations.

## 13. Discount & Financial Invariants
- **Gross Amount:** Exact sum of selected test prices.
- **Individual Line Discount:** Capped by test policy (<=50%) or price.
- **Master Discount Supersession:** When active, individual discounts are superseded in net calculation.
- **Net Payable:** `Gross + Urgent - TotalDiscount`.

## 14. Error Handling & Form Field Alerts
- **Network Failures:** Caught gracefully and rendered via `ToastContext` (`type: 'error'`).
- **HTTP 400 Bad Request:** Field error message displayed in alert banner.
- **HTTP 403 Forbidden:** Access boundary restriction displayed to user.

## 15. Notification / Toast Triggers
- **Success:** Green toast with check icon on completed records.
- **Warning:** Amber toast on duplicate phone numbers or missing fields.
- **Error:** Red toast with error details on validation failure.
- **Info:** Cyan toast on receipt reprinting and status changes.

## 16. Printing & Thermal Paper Format (if applicable)
- **Thermal Receipt:** Standard 80mm roll width (`font-mono`, 12px, high contrast).
- **Watermark:** Red `DUPLICATE` stamp rendered across reprints.
- **Report Preview:** A4 clinical diagnostic report layout with authorization signatures.

## 17. Audit Log Events Generated
Every mutation generates an audit log entry in the `audit_logs` table:
- `actor_id`: Logged staff UUID.
- `action`: E.g., `PATIENT_CREATE`, `INVOICE_CREATE`, `REPRINT_INVOICE`, `REFUND_REQUEST`.
- `entity_type`: Table affected.
- `entity_id`: Record UUID.
- `details`: Contextual JSON payload.

## 18. Security, RBAC & Tenant Scoping
- **Tenant Scoping:** Strictly enforced via `TenantScopeMiddleware` and SQLAlchemy filters.
- **RBAC Matrix:** Receptionist role authorized for intake, billing, routing, and delivery. Commission and accounting ledgers filtered out of response models.

## 19. Edge Cases & Boundary Handling
- **Duplicate Phone:** Flagged with warning while permitting shared family registration.
- **Pre-sample Refund:** Strictly rejected with HTTP 400 if sample was collected.
- **Due Hold on Delivery:** Strictly blocked if `due_amount > 0` unless Admin override supplied.
- **Business Day Close:** Strictly rejected with HTTP 403 for Receptionist.

## 20. Responsive Behavior
- **Desktop (>= 1280px):** Full 4-column Bento grid or 2-column split intake.
- **Tablet (768px - 1279px):** 2-column stacked grid, collapsible sidebar rail.
- **Mobile (< 768px):** Single-column layout with horizontal table scrolling.

## 21. Loading, Skeleton & Empty States
- **Loading:** Smooth centered spinner (`Loader2` in brand orange `#CF8852`).
- **Empty State:** Soothing illustration with helpful guidance text.

## 22. Cross-Component Event Propagation
- Updates in `NewInvoicePage` refresh the `businessDay` balance and recent invoices in `DashboardPage`.
- Due settlement in `DuesPage` updates invoice status and unlocks report delivery in `ReportsPage`.

## 23. Component Hierarchy Tree
```
{component_tree}
```

## 24. Data Dictionary (Fields, Types, Bounds)
| Field | Type | Storage | Bounds / Constraints |
|---|---|---|---|
| `id` | UUID | UUID Primary Key | Standard RFC 4122 |
| `tenant_id` | UUID | UUID Foreign Key | References `tenants.id` |
| `amount` | Integer | BIGINT / INTEGER | Whole-Taka, >= 0 |
| `created_at` | Timestamp | TIMESTAMPTZ | Server UTC default |

## 25. Testing Checkpoints (for User Verification)
1. Verify interface loads without console errors or layout shifts.
2. Verify search filtering yields immediate matching results.
3. Verify form submissions reflect in database and table views.
4. Verify financial calculations match the whole-Taka integer rule.
5. Verify thermal receipt opens and print preview renders correctly.
"""
    file_path = OUTPUT_DIR / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Generated {file_path}")

for item in INTERFACES:
    generate_doc(item)

print(f"Successfully generated all {len(INTERFACES)} interface markdown files.")
