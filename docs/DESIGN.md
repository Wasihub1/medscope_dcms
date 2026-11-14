# MedScope DCMS — UI/UX Design System Specification

## 1. Executive Visual Philosophy

MedScope's user interface is purposefully engineered for busy diagnostic center front-desk environments in Bangladesh. A receptionist operates in a high-stress, interrupt-driven atmosphere: registering patients, answering calls, handling cash, explaining test instructions, and delivering sensitive medical reports.

### Four Core Tenets
1. **Eye-Soothing Comfort:** Warm, organic, low-glare color tokens that reduce ocular fatigue during 8- to 12-hour shifts under clinical lighting.
2. **Super Friendly & Reassuring:** Softly rounded geometry (`rounded-2xl`, `rounded-xl`), generous breathing room, polite micro-copy, clear status badges, and crystal-clear feedback loops.
3. **Information Density with Hierarchy (Uneven Bento Grid):** Structured visual partitioning that groups operational data logically so receptionists can glance and act without hunting for controls.
4. **Resilient Bilingual Typography:** Flawless coexistence of Bangla Unicode and English text with balanced baselines and optical alignment.

---

## 2. Brand Color Tokens & Palette Hierarchy

The design system is strictly anchored around three primary brand pillars: **Platinum**, **Dark Moss**, and **Persian Orange**. These colors follow a calibrated 60-30-10 surface-hierarchy ratio:

```
┌────────────────────────────────────────────────────────┐
│                      60% PLATINUM                      │
│             Quiet, Neutral, Soothing Canvas            │
├──────────────────────────┬─────────────────────────────┤
│      30% DARK MOSS       │     10% PERSIAN ORANGE      │
│ Structural Contrast,     │ High-Value Focus, Primary   │
│ Nav, Deep Anchors        │ Actions, Active Selection   │
└──────────────────────────┴─────────────────────────────┘
```

### The Three Core Brand Pillars
| Pillar Name | Hex Code | Role in Hierarchy | Mandated Usage |
| :--- | :--- | :--- | :--- |
| **Platinum** | `#E8E7E3` | **60% Surface Foundation** | Main background canvas, neutral container fills, table header fills, muted borders, input backgrounds, and structural separators. |
| **Dark Moss** | `#525333` | **30% Structural Emphasis** | Primary navigation sidebar, active page headers, high-contrast headings, primary text body, structural card borders, and anchoring elements. |
| **Persian Orange** | `#CF8852` | **10% Action Accent** | Primary call-to-action buttons, key positive confirmations, active state indicators, focus highlights, and badge accents. |

### Derived CSS Token System
```css
:root {
  /* Core Pillars & Prompt 10 Tokens */
  --color-accent: #CF8852;
  --color-brand-orange: #CF8852;
  --color-brand-platinum: #E8E7E3;
  --color-brand-moss: #525333;
  --color-brand-ink: #26270F;
  --color-brand-secondary: #3D3E1F;

  /* Persian Orange Scale */
  --color-orange-50:  #FAF3EC;
  --color-orange-100: #F3E4D6;
  --color-orange-200: #E6C4A7;
  --color-orange-300: #DCA77C;
  --color-orange-400: #D69766;
  --color-orange-500: #CF8852; /* Base Persian Orange */
  --color-orange-600: #B7703B;
  --color-orange-700: #96572A;

  /* Platinum Scale */
  --color-platinum-25:  #FAF9F6; /* Card backgrounds, dialog surfaces */
  --color-platinum-50:  #F4F3F0; /* Secondary surface, container wells */
  --color-platinum-100: #E8E7E3; /* Base Platinum — Application Canvas */
  --color-platinum-200: #DCDAD4; /* Subdued card borders, input borders */
  --color-platinum-300: #CAC7BE; /* Structural dividing lines */
  --color-platinum-400: #B1ADA2; /* Disabled button fills */
  --color-platinum-500: #8E8A7E; /* Placeholder text */
  --color-platinum-600: #6D6A60; /* Secondary body copy */
  --color-platinum-700: #54524A; /* High-readability tertiary text */

  /* Dark Moss Scale */
  --color-moss-50:  #F2F3EC;
  --color-moss-100: #E2E4D4;
  --color-moss-500: #525333; /* Base Dark Moss — Sidebar, Headings */
  --color-moss-600: #444529;
  --color-moss-700: #373720;
  --color-moss-900: #1B1B0E; /* Deepest black-moss for high-emphasis titles */

  /* Semantic Functional Colors */
  --color-success-bg:     #EDF7EE;
  --color-success-border: #C3E6C7;
  --color-success-text:   #1E6327;
  --color-danger-bg:      #FDF2F0;
  --color-danger-border:  #F8CBC6;
  --color-danger-text:    #9C2417;
  --color-warning-bg:     #FEF7EC;
  --color-warning-border: #FCDCA7;
  --color-warning-text:   #8F5605;
}
```

---

## 3. Typography & Dual-Script Standards

- **Primary Font Family:** Manrope (self-hosted via `@fontsource/manrope`), system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif.
- **Bangla Font Fallback:** 'Noto Sans Bengali' (self-hosted via `@fontsource/noto-sans-bengali`), 'SolaimanLipi', 'Kalpurush', sans-serif.
- **Monospace Numbers & IDs:** 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, monospace.
- **Self-Hosting Policy:** Fonts are bundled locally without runtime Google Fonts or external CDN requests, guaranteeing uninterrupted rendering on low-bandwidth clinical connections.
- **Weight Cap:** Allowed weights: 400 (regular), 500 (medium), 600 (semibold), 700 (bold). Zero italics, zero ultra-bold/black weights.
- **Contrast Requirement:** Button text on Persian Orange `#CF8852` uses ink `#26270F` (contrast ratio ~7:1, exceeding WCAG AAA). Flat backgrounds only; no background gradients.
- **Hierarchy Scale:**
  - Page Titles / Hero: `text-6xl font-bold text-[#26270F]` (60px, leading 1)
  - Card Titles: `text-3xl font-semibold text-[#26270F]` (30px)
  - Section Headings: `text-xl font-bold text-[#26270F]` (20px)
  - Standard Labels / Inputs: `text-sm font-semibold text-[#26270F]` (14px)
  - Secondary Copy / Microcopy: `text-sm text-[#3D3E1F]` (14px) / `text-xs text-[#6D6A60]` (12px)

---

## 4. Uneven Bento Grid Layout & Visual Containers

MedScope avoids rigid, uniform box grids in favor of the **Uneven Bento Grid** layout:
- **New Invoice Intake Screen:** Features a rebalanced `lg:grid-cols-[48%_1fr]` grid (48% left column, 52% right column). Truncating the left column by 10% provides generous horizontal space for itemized test lines, line discount inputs (% and ৳), urgent toggles, master discounts, and payment intake in the right column.
- **Distinct Line Discount Controls (% and ৳):** Eliminates `<select>` dropdowns in selected investigations in favor of distinct, side-by-side numerical inputs: `[ % ] %` and `[ ৳ ] ৳`. Inputs feature custom rounded badge containers (`border-[#CAC7BE] rounded px-1.5 py-0.5 focus-within:border-[#CF8852]`) with unselectable unit suffixes, hidden native spinners, and real-time bidirectional synchronization.
- **Consolidated Referral Container:** Prescriber (`2. Prescribed By (Doctor Only)`) and Referrer (`3. Referred By (Doctor / Third Party / Broker)`) are merged into a single consolidated card container using an internal 2-column responsive subgrid (`grid grid-cols-1 md:grid-cols-2 gap-4 items-start`), saving ~130px of vertical height.
- **Aligned Input & Action Controls:** Each sub-form features an independent header row (`h-5`) and a dedicated control row (`h-9` / 36px). In the unselected search state, the Search input (`flex-1`) and the Add modal trigger button (`shrink-0`) sit side-by-side on the exact same baseline. In the selected state, the card container is also `h-9` with name, badge, and Clear button. This guarantees 100% horizontal and vertical alignment across columns regardless of whether either sub-form is in selected or unselected state.
- **Investigation Catalog Positioning & Relief:** Bringing the catalog up allows expanding its test list container height to `max-h-80` (320px), facilitating easy browsing and rapid autocomplete across 1,250 active diagnostic tests.
- Card containers use `bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl shadow-xs`.
- Form inputs feature `bg-white border border-[#CAC7BE] rounded-xl px-3 py-2 text-xs text-[#1B1B0E] focus:border-[#CF8852] focus:ring-1 focus:ring-[#CF8852] outline-none`.

---

## 5. Inline Global Search & Keyboard Navigation

The previous modal-based search has been eliminated in favor of an **Inline Anchored Search Bar**:
- **Search Element:** `<input id="medscope-global-search">` embedded permanently in the main application header.
- **Keyboard Shortcut:** `Ctrl+F` (replaces `Ctrl+K`). Scoped to prevent hijacking browser find during native print operations.
- **Visual Feedback:** A subtle badge `Ctrl+F` appears inside the input field.
- **Dropdown Anchor:** Dropdown matches appear directly anchored beneath the search input with categories:
  - Patients (MRN, Name, Phone)
  - Invoices (Invoice Number, Date, Amount)
  - Tests (Test Code, Name, Department, Price)
  - Reports (Report Number, Status)
- **Key Navigation:** Supports `ArrowDown`, `ArrowUp`, `Enter` to select, and `Escape` to close the dropdown.

---

## 5.1 Header User Profile Menu (Prompt 09; role switcher removed in Prompt 10D)

The development role switcher (`toggleRole` pill and header spoofing) has been permanently eliminated in favor of an **Authenticated User Profile Menu**:
- **Location:** Anchored in the top-right header region.
- **Avatar Trigger:** Displays a circular badge with the user's uppercase initials (`staff.name.slice(0, 2).toUpperCase()`) and an active acting-role badge (`bg-[#525333] text-white text-[10px] font-semibold px-2 py-0.5 rounded-full`).
- **Anchored Dropdown:** Clicking the profile trigger opens a floating dropdown container (`bg-[#FAF9F6] border border-[#DCDAD4] rounded-xl shadow-lg p-3 w-64`):
  - **User Identity Card:** Displays user's full name, staff ID (`#<id>`), and active acting role.
  - **Sign Out Action:** A dedicated sign-out button with `LogOut` icon dispatches `POST /api/v1/auth/logout`, clears active session state, and redirects the client to `/login`.

> **Implemented in Prompt 10D (ADL-032):** one login = one fixed role. The menu shows a `Role: <ROLE>` badge only; the multi-role switcher is removed.

## 5.2 Permission-Driven Navigation, Dashboard & User Management (Prompt 10D)
- **Sidebar:** each item is shown only when the user holds its permission (e.g. Invoices → `invoice.view`, My Work → `worklist.view`, User Management → `user.manage`).
- **Dashboard landing (`/dashboard`, every role):** a Platinum/white welcome bar with the role and Persian Orange buttons to the main work page(s). Holders of `dashboard.view` see the financial Bento dashboard below it; LAB_TECH and DOCTOR (Prompt 10E) see money-free worklist count tiles (from `/worklist/summary`) and a note that prices, payments and dues are not shown.
- **User Management (`/users`):** two tabs, **Users** (cards with role badge, Inactive/Locked chips, section label, override count; Edit, Reset password, Deactivate/Reactivate with confirm dialogs) and **Create User** (form + permission editor). In the permission editor, overridden rows have an orange border (`border-[#CF8852] bg-[#FDF6EF]`) and say "added/removed for this user"; money keys are locked off for LAB_TECH and DOCTOR. Prompt 10E: the role picker includes DOCTOR; for LAB_TECH the **Lab room \*** select is required (placeholder "Select a room…", `required`/`aria-required`) on Create and Edit. Your own role, permissions and active toggle are disabled. Single-column layout at 390px (no horizontal page scroll).
- **Invoice preview (Draft / Finalize):** the left header shows the draft tag ("Unsaved Draft" or "Saved Draft DRAFT-…") with a white **Save Draft** button beside it; the right side shows **Back & Correct**, **Finalize** (Dark Moss) and **Finalize & Print** (Persian Orange). The Invoices list shows draft rows with an amber "Draft" badge and a **Continue Draft** button instead of View/Reprint.

---

## 6. A4 Landscape Dual-Copy Print Specification

Invoices are formatted for laser and ink-jet printing on standard A4 paper in landscape orientation:

```
┌──────────────────────────────────────┬─┬──────────────────────────────────────┐
│             PATIENT COPY             │✂│          OFFICE / LAB COPY           │
│                                      │ │                                      │
│  MedScope Diagnostic Center          │C│  MedScope Diagnostic Center          │
│  Invoice #: INV-202611-0001          │U│  Invoice #: INV-202611-0001          │
│  Patient: Fatima (MRN-0001)          │T│  Patient: Fatima (MRN-0001)          │
│  Prescribed By: Dr. Rafiq            │ │  Prescribed By: Dr. Rafiq            │
│  Referred By: Kabir (Agent)          │H│  Referred By: Kabir (Agent)          │
│                                      │E│                                      │
│  Tests: CBC, Lipid Profile           │R│  Tests: CBC, Lipid Profile           │
│  Subtotal: ৳1,500   Discount: ৳200   │E│  Subtotal: ৳1,500   Discount: ৳200   │
│  Net: ৳1,300   Paid: ৳1,300 (PAID)   │ │  Net: ৳1,300   Paid: ৳1,300 (PAID)   │
└──────────────────────────────────────┴─┴──────────────────────────────────────┘
```

### Layout Specifications
- **CSS Rule:**
  ```css
  @page {
    size: A4 landscape;
    margin: 8mm;
  }
  ```
- **Structure:** Two equal `flex-1` panels partitioned by a vertical border with a dashed cut line (`border-l-2 border-dashed border-gray-400`).
- **Watermark Overlay:** For reprint events (`reprint_count > 0`), both panels render a bold diagonal `DUPLICATE` watermark:
  ```css
  pointer-events-none select-none text-red-600/15 text-5xl font-black uppercase rotate-[-30deg]
  ```
- **Thermal 80mm Compatibility:** Thermal slip generation is preserved for fast receipt roll printers via standard slip print styling.

---

## 7. Standardized Badge & Status Tokens

### Payment Status Tokens
| Presentation Label | Condition | Token Style |
| :--- | :--- | :--- |
| **Unpaid** | `paid_amount == 0` | `bg-red-50 text-red-700 border-red-200` |
| **Partial Due** | `paid_amount > 0 && due_amount > 0` | `bg-amber-50 text-amber-700 border-amber-200` |
| **Paid** | `due_amount == 0` | `bg-emerald-50 text-emerald-700 border-emerald-200` |

### Refund Status Tokens
| Presentation Label | Status Code | Token Style |
| :--- | :--- | :--- |
| **No Refund** | `NO_REFUND` | `bg-gray-50 text-gray-600 border-gray-200` |
| **Refund Pending** | `REFUND_PENDING` | `bg-amber-50 text-amber-700 border-amber-200` |
| **Partially Refunded**| `PARTIALLY_REFUNDED`| `bg-blue-50 text-blue-700 border-blue-200` |
| **Fully Refunded** | `FULLY_REFUNDED` | `bg-purple-50 text-purple-700 border-purple-200` |
| **Refund Rejected** | `REFUND_REJECTED` | `bg-rose-50 text-rose-700 border-rose-200` |

---

## 8. In-Context Patient History Nested Overlay & In-Place Modal Patterns

MedScope enforces bidirectional in-place modal overlays so that inspecting cross-linked entities never causes unexpected route switches or state loss:

### 8.1 Patients Page -> Invoice Detail Overlay
When accessing past invoices from the **Patient History** view (`/patients`):
- The invoice detail is opened as a **nested modal overlay** (`DualCopyInvoiceModal`) over the active patient history drawer.
- **Route Preservation:** The application route remains strictly `/patients`. No redirection to `/invoices` occurs.
- **State Preservation:** Closing the invoice overlay returns the user directly to the patient's active tab (e.g. *Invoices & Tests*), preserving scroll position, active search terms, and selected patient context.

### 8.2 Invoices Page -> Patient History Overlay (Prompt 08)
When accessing patient details from the **Invoice Detail** view (`/invoices`):
- The patient history is opened as an **in-place modal overlay** (`PatientHistoryModal`) directly over the Invoices view.
- **Route Preservation:** The application route remains strictly `/invoices`. No redirection to `/patients` occurs.
- **State Preservation:** Table search filters, status filter dropdowns, pagination, and scroll positions are 100% preserved. Closing the modal dismisses the overlay without re-rendering or navigating away from the active invoices table.
- **Shared Component:** Encapsulated in `frontend/src/components/common/PatientHistoryModal.tsx`, reusing the identical 4-tab clinical profile (Overview, Invoices & Tests, Payments, Dues) across both `/invoices` and `/patients`.

---

## 9. Stable Test Selectors (`data-testid`)

Key selectors implemented across the application for reliable automated Playwright verification:
- `#medscope-global-search`: Inline global search input.
- `[data-testid="selected-prescriber-name"]`: Prescribed By doctor badge.
- `[data-testid="selected-referrer-name"]`: Referred By contact badge.
- `[data-testid="due-status-indicator"]`: Live outstanding due balance indicator.
- `[data-testid="generate-preview-btn"]`: Stage 1 preview trigger button.
- `[data-testid="back-and-correct-btn"]`: Stage 2 correction back button.
- `[data-testid="save-invoice-btn"]`: Stage 2 final persistence trigger.
- `[data-testid="save-and-print-btn"]`: Stage 2 save and immediate print trigger.
- Prompt 10E: `visit-age-input`, `visit-age-unit`, `visit-gender-select` (New Invoice visit demographics); `payment-method-select`, `channel-detail-input` (New Invoice), `dues-payment-method-select`, `dues-channel-detail-input`, `settle-channel-detail-input`; `worklist-tile-<ID>` (ALL, URGENT, SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, REJECTED, LATE, READY, UNASSIGNED, COMPLETED) with `aria-pressed`; `preview-report-<orderId>`, `result-report-preview`, `reassign-room-<orderId>`, `reassign-room-select`, `order-room-<orderId>`; `assign-room-select-<orderId>`; `invoice-payment-channel` (receipt "Paid via").
- Prompt 10F: `preview-draft-banner`, `preview-entered-note` (preview modal); `last-saved-result`, `last-saved-preview-<orderId>`, `sample-first-hint-<orderId>` (My Work); `assignments-tab-UNASSIGNED`, `assignments-tab-ASSIGNED`, `assigned-tests-panel`, `assigned-row-<orderId>`, `assigned-reassign-<orderId>`, `assigned-reassign-room-select`, `assigned-room-filter`, `assigned-status-filter` (Assign Tests); `reports-tab-READY`, `reports-tab-ISSUED`, `ready-results-panel`, `ready-row-<orderId>`, `ready-preview-<orderId>`, `ready-results-empty`, `issued-reports-card` (Ready Reports).

---

## 10. Technician Worklist & Turnaround Clocks Design Conventions (Module 11)

### Dual Turnaround Clocks
- **Patient Clock:** Displays elapsed real time from invoice confirmation to the present moment. Color changes to vivid red when elapsed time exceeds the test's configured turnaround hours.
- **Laboratory Clock:** Displays elapsed real time from specimen collection event (`sample.status == 'COLLECTED'`) to the present moment. Renders 'Not Collected' until a phlebotomist or technician draws the sample.

### Priority & Alert Tokens
| Indicator | State / Condition | Design Token & Styling |
| :--- | :--- | :--- |
| **STAT Urgent** | `order.urgent == true` | `bg-[#F9E2D2] text-[#B05B20] border-[#E9BD9E]` with animated pinging beacon |
| **LATE** | `order.is_late == true` | `bg-[#FEE2E2] text-[#B91C1C] border-[#FCA5A5]` with `AlertTriangle` icon |
| **Awaiting Doctor** | `order.status == 'AWAITING_DOCTOR'` | `bg-amber-100 text-amber-800 border-amber-300` with `Stethoscope` icon |
| **In Progress** | `order.status == 'IN_PROGRESS'` | `bg-blue-100 text-blue-800 border-blue-300` with `FlaskConical` icon |
| **Completed** | `order.status == 'COMPLETED'` | `bg-emerald-100 text-emerald-800 border-emerald-300` with `CheckCircle2` icon |

### Strict Financial Secrecy Invariant
In accordance with Module 11 Section 5.4, the technician UI never contains monetary figures, discounts, test prices, payments, or commission indicators anywhere on the workbench (Prompt 10E: the same for DOCTOR).

### Prompt 10E Worklist UI
- **Bento tiles are filters:** each KPI tile is a `<button>` with `aria-pressed`, a visible focus ring (`focus-visible:ring-2 focus-visible:ring-[#CF8852]`) and the brand tokens. The active tile turns Dark Moss (`bg-[#525333]`, white text); clicking it again clears the filter. Tiles: Room Queue, Urgent STAT (toggles STAT only), Sample Pending, In Progress, Doctor Queue, Rejected / Spoil, Late Tasks (rose alert when > 0), **Ready Reports**, **Unassigned** (Admin/Owner only), Completed. Grid: 2 columns on phones, 3 on small, 5 on medium and up. Tabs gained **Late** and **Ready Reports**; tiles and tabs share one filter state.
- **Room label:** the header chip shows the technician's room (e.g. "Hematology — Room 101"); each row shows "Room: …", "Worked by: …" (who acted) and a green **Report Ready** chip when the result is Ready (10F: submitted, order not cancelled / not performed / awaiting doctor; completion not required).
- **Sample action:** "Sample Taken" appears only when the test needs a sample (`requires_sample`); imaging rows show "Imaging Procedure (No Biological Specimen)"; results and Complete are available once a sample is collected or when none is needed.
- **Preview Report:** a white button with blue text (`text-[#2B547E] border-[#B9C9DA]`, `Eye` icon) on rows with a saved result opens a modal with patient, age/gender, test, sample code, the result table (flags coloured: CRITICAL rose, HIGH/LOW amber) and findings/impression/comments. *(10E had a "Print preview" button; removed in 10F, see below.)*
- **Reassign Room:** a small outline button (`MoveRight` icon) for `worklist.reassign` holders until COMPLETED; modal with the room select (other rooms, "— no technician" when empty) and an optional reason.

### Prompt 10F Worklist UI (owner findings #2, #3; decision A5)
- **Preview modal (`ResultReportPreviewModal.tsx`):** title "Report Preview", subtitle "Saved result, preview only. This is not the issued report." A **DRAFT** shows a dashed amber banner (`border-2 border-dashed border-amber-400 bg-amber-50`, `AlertTriangle`, `role="status"`): **"DRAFT, not a final report"** + "These values are saved as a draft and may still change." A submitted result shows a quiet blue note ("Result submitted and Ready. It becomes a Final report when it is finalized (no printing here yet)."); a Final report shows a green note with the report number, the technician and the doctor (name, registration number, how it was recorded). The table adds a **Critical** column from the saved limits (e.g. "< 6 or > 20"); USG structured findings are listed by organ. **No print button**, only Close. Read-only and money-free.
- **Just-saved strip:** after Save Draft or Submit, a blue strip at the top of the grid card (`bg-[#EEF3F8] text-[#2B547E]`, `role="status"`) reads "Result saved as DRAFT / (submitted) for order #… : test" with **Preview Report** and **Dismiss**. It keeps Preview one click away even when the saved row leaves the active tab (e.g. Sample Pending → Completed).
- **Ready Reports tile/tab:** same tile style; the count comes from the shared Ready definition and equals the rows shown; click again clears. Empty state when filtered on Ready: "No Ready Reports Yet — A result appears here as soon as it is submitted (Submit Results). Drafts are not Ready. Click the Ready Reports tile again to clear the filter."
- **Sample first:** rows that still need a sample show the Sample Taken button and a small amber hint "Take the sample before entering results" (`text-[10px] text-[#8B6B23]`); Enter Results and Complete appear only after Sample Taken (or for imaging / explicit no-sample tests). Backend refusals show the plain message in an error toast.
- **Reassign Room (My Work):** also hidden for Not Performed (rejected/spoiled) rows, matching the backend rule.
- **Refresh:** My Work, Assigned Tests and Ready Results refetch on window focus (throttled to one call per 2 s) and on navigation.

### Prompt 10F Front-Desk UI (owner finding #1, #3)
- **Assign Tests page:** two tabs (Dark Moss active pill, `role="tab"`, `aria-selected`): **Unassigned (n)** (the existing routing table) and **Assigned Tests**. The Assigned Tests table: Invoice # (mono), Patient (+ code), Investigation (+ code, red **URGENT** badge), Room ("No room" in grey), Technician(s) (names, or an amber **UNASSIGNED** badge; "Worked by" below), Status badge (+ "Result: DRAFT/ENTERED"), Created (en-GB date-time), Action. Filters: search, room (All rooms / each room / No room), status (All, Open, Unassigned, Assigned, Sample pending, In progress, Awaiting doctor, Pending, Completed, Not performed, Cancelled), refresh icon. Intro line says "View only …" for front desk. Admin/Owner rows show an outline **Reassign Room** button (`MoveRight`) or, when blocked, a grey lock with the short reason ("Completed", "Cancelled", "Not performed"). Reassign modal = the My Work modal (other rooms, "— no technician", optional reason). No money anywhere.
- **Ready Reports page (`/reports`):** two tabs, **Ready Results** (default) and **Issued Reports**. Ready Results: search, room filter, refresh; table Invoice #, Patient (+ phone), Investigation, Room, Result entered (time + "by …"), **Payment** (red "Due ৳…" or green "Paid"; the column appears only when the API returns due fields, i.e. for money roles), and a **Preview Report** button. Empty states: "No results are ready yet. A result appears here as soon as the lab submits it; drafts are not shown." / "No ready results match these filters." Issued Reports keeps the existing table; its empty state now reads "No issued reports yet. Finalize a submitted result (Ready Results tab) to issue its report." The search/due filter in the header shows only on the Issued tab.

### Prompt 10E Front-Desk UI
- **New Invoice:** the selected-patient card has **Age \*** (number + years/months/days) and **Gender \*** fields, prefilled from the patient; Finalize without them shows an amber toast ("You can still Save Draft"). The payment method list is Cash, bKash, Nagad, Rocket, Card, Bank Transfer, Other (type the name); choosing Other shows a **Channel Name \*** input. The urgent preview uses the backend rule (minimum ৳100, 20% of price).
- **Receipts (dual copy):** after Finalize the saved receipt shows the backend totals (urgent fee, discount), the visit age/gender and a "Paid via" line (e.g. "Other (Upay)").
- **Dues / Invoices settle / Refund disburse:** same channel list and Channel Name field; invoice payment history shows the channel label incl. the typed name.
- **Assign Tests:** the column is **Lab Room** with a "Select room…" placeholder and the four rooms ("— no technician" when empty); the waiting room is shown under the select.
- **Ready Reports page:** the "Override & Deliver" button is shown to holders of `report.release_with_due` (Admin and Owner), not by role name.

---

## 11. Specimen Barcode & Operational Lifecycle UI (Module 12)

### Specimen Tube Barcode Label Specification (50mm × 30mm)
- **Dimensions:** Formatted for standard 50mm × 30mm and 50mm × 25mm thermal direct adhesive rolls.
- **Color Scheme:** 100% monochrome black on white background (`print:border-none print:shadow-none`).
- **Typography:** Sans-serif bold patient name and MRN; monospace for sample code (`SMP-INV-YYYY-XXXX-ID`); bold test code pill.
- **Barcode Encoding:** Code 128 Character Set B vector SVG without client-side image canvas rasterization.
- **Clinical Details:** Center name, Specimen type (e.g. EDTA Blood), Patient Name, MRN, Age/Gender, Test Name & Code, Timestamp, Sample ID.
- **Strict Financial Privacy:** Never includes prices, fees, dues, or payment indicators.

### Specimen Rejection & D15 Workflow Tokens
- **Rejected Specimen Pill:** `bg-rose-100 text-rose-800 border border-rose-300` with `XCircle` icon and prominent rejection reason.
- **Follow-up Call Trigger:** `bg-[#CF8852] text-white rounded-lg shadow-2xs` with `PhoneCall` icon.

### Department-Specific Visual Tokens
- **Culture Stages:** `bg-purple-50 text-purple-800 border-purple-200` with `Layers` icon for `INCUBATING`, `PRELIMINARY`, `FINAL`.
- **Referral Labs:** `bg-blue-50 text-blue-800 border-blue-200` with `Send` icon for `SENT` and `RECEIVED`.
- **Imaging Procedures:** `bg-indigo-50 text-indigo-700 border-indigo-200` with `Camera` icon.

### Operational Lifecycle Timeline (`LifecycleHistoryModal.tsx`)
- Vertical timeline with connected left border (`before:w-0.5 before:bg-[#E8E7E3]`).
- Distinct status node icons (`Droplet` for collected, `AlertTriangle` for rejected, `Camera` for imaging, `Layers` for culture, `Send` for outsourced).
- Metadata cards with actor attribution, role badges, and clinical notes.

---

## 12. Clinical Result Entry & Reference Range UI (Module 13 & Fixes)

### Result Entry Modal (`ResultEntryModal.tsx`)
- **Layout & Sizing:** Clean `maxWidth="xl"` modal with tabbed sections and clinical header. Strictly financial-free.
- **Component Table Design:**
  - Header with Component, Result Value input, Reference Limits, Critical Limits, and Live Flag Preview.
  - **Live Result Flag Tokens:**
    - `NORMAL`: `bg-emerald-50 text-emerald-800 border border-emerald-200`
    - `LOW`: `bg-blue-50 text-blue-800 border border-blue-200` with downward arrow indicator
    - `HIGH`: `bg-amber-50 text-amber-800 border border-amber-200` with upward arrow indicator
    - `CRITICAL`: `bg-rose-100 text-rose-800 border border-rose-300 font-bold` with alert icon
    - `None` (no limits): Muted dash (`-`) in neutral gray; never falsely displays `NORMAL`.
- **Impossible-Value Validation Alert:**
  - Real-time client warning and backend rejection: `bg-rose-50 border border-rose-300 text-rose-900 rounded-xl p-3` with physiological boundary explanation.
- **Structured Ultrasound Template:**
  - Organ-by-organ breakdown (Liver, Gallbladder, Pancreas, Spleen, Kidneys, Bladder, Pelvic Organs) with organ-specific findings and consolidated Impression editor.
- **Narrative Multi-Section Template:**
  - Findings, Impression, and Comments (backed by `results.findings`, `results.impression`, `results.comments`). There are no Technique or Recommendations fields. (Clinical History field removed). Delta visual indicators excluded by D25.

### Module 12 Fix Visual Patterns
- **FIX 1 (Line Lock Decoupling):** Complete removal of the visual `Line Locked` badge from Technician Worklist rows and timeline cards to reduce technician cognitive clutter.
- **FIX 2 (Persistent STAT Urgent Beacon):** STAT `URGENT` badge (`bg-[#F9E2D2] text-[#B05B20] border-[#E9BD9E]`) remains visibly pinned across all intermediate task states (`SAMPLE_PENDING`, `IN_PROGRESS`, `AWAITING_DOCTOR`, `REJECTED`, `SPOILED`) and disappears only when task is `COMPLETED`.
- **FIX 3 (Authoritative Sample Status Badges in Invoices):**
  - `COLLECTED` -> `Badge variant="success"`
  - `REJECTED` / `SPOILED` -> `Badge variant="danger"`
  - `PERFORMED` -> `Badge variant="info"`
  - `AWAITING COLLECTION` -> `Badge variant="neutral"`
- **FIX 4 (D15 Refund Workflow Visuals):**
  - Technician Worklist: "Submit D15 Refund" action button with amber pill for spoiled/rejected items.
  - Invoice Details Table: Investigation column displays `NOT PERFORMED (D15)` tag and live D15 status pill (`Pending Approval`, `Approved (Awaiting Payout)`, `Disbursed`).
  - Disburse Payout Modal: Dedicated cash/digital payout modal (`DisburseModal`) with payment channel select (`CASH`, `BKASH`, `NAGAD`, etc.) and transaction reference input.

### Prompt 07C Visual & Interaction Invariants
- **Technician Clinical Response (Fix 5):** Submitting a D15 refund request produces a clinical-only confirmation dialog with status, without showing any pricing, invoice totals, or refund amounts.
- **Timeline Financial Redaction (Fix 5):** `LifecycleHistoryModal` dynamically redacts all monetary values (`Tk` and `৳`) for `LAB_TECH` viewers, preserving strict counter privacy.
- **Original Channel Disburse Restriction (Fix 1):** The disbursement dialog strictly restricts selectable payout methods to the payment channels actually used on that invoice's recorded payments.
- **Immutable Completed Orders (Fix 4):** Result entry interface displays a read-only lock banner on `COMPLETED` test orders, preventing post-completion modifications.

---

## 13. Branded Landing Page & Animated Login UI (Prompt 10)

### 13.1 Landing Page Specification (`/`)
- **Canvas & Header:**
  - Background: Flat Platinum (`#E8E7E3`).
  - Header: Logo mark (Dark Moss rounded square `#525333` with Persian Orange plus `#CF8852`, `rx="8"`) with title "MedScope DCMS" and one primary "Sign in" button (`bg-[#525333] text-white rounded-xl px-6 py-3 font-bold`).
- **Hero Structure (Two Columns, Responsive Wrap):**
  - **Left Column:**
    - H1: "Your diagnostic center, in one place" (capped at 680px width, `text-4xl sm:text-5xl lg:text-6xl font-bold text-[#26270F]`, `text-wrap: balance`).
    - Subtitle: "Billing, samples, results and reports." (capped at 480px, `text-lg sm:text-xl text-[#3D3E1F]`, `text-wrap: pretty`).
    - Primary CTA: Single action button "Sign in" (`bg-[#CF8852] hover:bg-[#B7703B] text-[#26270F] font-bold text-lg px-8 py-4 rounded-xl shadow-xs`).
    - Cleanliness Invariant: No additional marketing sections, pricing tables, testimonials, or invented facts.
  - **Right Column (Animated Medical Scene):**
    - Container: Dark Moss rounded card (`bg-[#525333] rounded-3xl p-8 sm:p-10 relative overflow-hidden min-h-[400px]`).
    - Heartbeat ECG: Self-drawing vector SVG looping continuously via `stroke-dashoffset` (`@keyframes ecg-landing 3.6s cubic-bezier(0.22, 1, 0.36, 1) infinite`).
    - Specimen Tube: Self-filling and draining tube graphic (`@keyframes fillup 4s cubic-bezier(0.22, 1, 0.36, 1) infinite alternate`).
    - Travelling Track Dot: Smooth lateral indicator along progress line (`@keyframes travel 4.8s cubic-bezier(0.22, 1, 0.36, 1) infinite alternate`).
    - Sequential Chips: Step badges fading and translating sequentially: "Sample taken" (0s delay), "Result entered" (2s delay), "Report ready" (4s delay, `#CF8852` accent).
    - Clinical Privacy: Strictly decorative animation; zero real or fabricated patient data.
- **Endless Marquee Strip (Workflow Stages):**
  - Surface: Flat white band (`bg-white border-y border-[#DCDAD4]`).
  - Dimensions: Capped at **70px total section height** (`py-4 md:py-5`, 28×28 SVG icons, `gap-3 px-6 md:px-8`) for an uncluttered, modern ticker strip.
  - Driven by a clean **extensible data array** (`WORKFLOW_STEPS` in `frontend/src/features/landing/LandingPage.tsx`).
  - Items: Register, Sample, Result, Report.
  - Interactive Behavior: Continuous linear scroll (`animation: marquee 28s linear infinite`); automatically pauses on hover (`:hover`) or keyboard focus (`:focus-within`).
  - Extensibility: Center administrators can append new workflow phases (e.g., Phlebotomy, Verification, Delivery) directly to the data array without modifying layout markup.
- **Footer:** Clean minimal branding: "MedScope DCMS".

### 13.2 Animated Login Page Specification (`/login`)
- **Two-Panel Architecture (Stacked on Mobile Viewports):**
  - **Left Brand Panel (Dark Moss `#525333`):**
    - Logo mark: Persian Orange rounded square `#CF8852` with dark plus `#26270F` and title "MedScope DCMS".
    - Large animated ECG illustration: Centered vector ECG line on subtle baseline (`#E8E7E3` opacity 0.25) looping continuously with pulsing ring marker at peak `(128, 30)` (`@keyframes ecg-login 4.2s`, `@keyframes pulse-ring 2.4s`).
    - Disclaimer note: "Illustration only. No patient information is shown on this page."
    - Strict Layout Rule: Zero step cards or clutter tiles on left panel.
  - **Right Sign-In Panel (Platinum `#E8E7E3` Canvas):**
    - Centered white rounded container (`bg-white rounded-3xl p-8 sm:p-10 border border-[#DCDAD4] max-w-[420px] w-full shadow-xs`).
    - Title & Subtitle: "Sign in", "Use your own account. What you see depends on your role."
    - Real Form Controls:
      - Visible labels: `<label htmlFor="user">` and `<label htmlFor="pass">`.
      - Autocomplete tags: `username` and `current-password`.
      - Show/Hide Password Toggle: Inline button toggles password input type with aria-label.
      - Full-Width CTA: Persian Orange `#CF8852` button with ink `#26270F` text (font-weight 700), loading state ("Signing in…", disabled), and active scale (`active:scale-[0.98]`).
      - Inline `aria-live="polite"` Error Area: Calm, polite messages with zero exclamation marks.
        - Wrong credentials: `"Invalid username or password."`
        - Lockout: `"This account is locked. Ask your administrator to reset it."`
        - Session expired: `"Your session has expired. Please sign in again."`
        - Network error: `"Unable to connect to the server. Check your network connection."`
      - Helper Links: "Forgot your password? Ask your center administrator to reset it." and "Back to the overview" link pointing to `/`.

### 13.3 Motion & Accessibility Standards
- **Motion Curve:** All non-continuous animations use the weighted deceleration curve `cubic-bezier(0.22, 1, 0.36, 1)`. The marquee uses a linear progression (`28s linear infinite`).
- **Continuous Motion Delivery:** Pure SVG and CSS keyframe animations (`ecg-landing`, `ecg-login`, `fillup`, `travel`, `chipin`, `pulse-ring`, `marquee`) are declared at the component level to ensure smooth execution across all Windows and web clients, preventing OS client area animation flags from freezing vector paths or stacking marquee tracks into two vertical rows.
- **No Reduced-Motion Fallback (intentional):** `frontend/src/index.css` contains **no** `@media (prefers-reduced-motion: reduce)` rule. The original fallback was removed on purpose in Prompt 10: on Windows machines with animations turned off, Chromium reports `prefers-reduced-motion: reduce`, and the fallback froze the ECG line and stacked the marquee into two rows. Animations therefore always run. Whether to add a user-facing "Pause animations" control is an open owner decision. Nothing is implemented for it yet.
- **Marquee Layout Geometry:** The marquee strip uses a single-line horizontal flex track (`flex-nowrap`, `width: max-content`) that translates continuously by `-50%`. Hovering or focusing pauses playback cleanly without rewrapping or shifting layout.
- **390px Viewport Compliance:** Zero horizontal overflow at 390px width (`scrollWidth == clientWidth == 390px`); primary actions ("Sign in") remain visible above the fold without scrolling.
- **Keyboard Navigation:** Full tab traversal, visible focus rings (`focus-visible:ring-2 focus-visible:ring-[#CF8852]`), and skip-to-content links on both pages.

### 13.4 Branded 404 Page (`NotFoundPage.tsx`)
- Renders for any unrecognized route (`*`).
- Centered white bento card on Platinum canvas with brand logo mark, heading "Page not found", explanatory sentence, and contextual navigation button ("Back to workbench" for authenticated users, "Back to home" for guests).

### 13.5 Design Reference & Skill Assets
- **Visual References:** `docs/design-reference/Landing.dc.html`, `docs/design-reference/Login.dc.html`.
- **Design Skill:** `docs/design-skills/landing-page-design/SKILL.md` (Part B visual rules enforced with owner brand overrides: MedScope palette, flat backgrounds, self-hosted fonts, and no marketing clutter).

## 14. Prompt 11 UI (soft delete, discard, audit)

- **ConfirmDialog** (`components/common/ConfirmDialog.tsx`, on the existing `Modal`, `max-w-sm`): bold item name, one-sentence effect, optional required **Reason** textarea (max 500; Confirm disabled until non-empty), Cancel + Confirm (red for delete/discard, olive for restore). Used by user delete, catalog delete/restore and draft discard.
- **Catalog & Deleted** page (`/catalog-admin`): tabs Tests, Doctors & 3rd parties (name/type/phone, red **Delete**), Deleted (type, item, deleted by, when, reason, **Restore**). Empty states: "No tests found.", "No doctors or 3rd parties found.", "Nothing has been deleted.". No-access state: "You do not have access to this page."
- **Audit Log** page (`/audit-log`): filters (action, entity, actor ID, from/to), table (when, who, role, action, entity, reason, Details), a before/after panel, Previous/Next. Empty state "No audit rows match."; no-access "You do not have access to the audit log."
- **Invoices:** drafts get a red **Discard** button next to Continue Draft.

## 15. Prompt 12 UI

- The amber "line locked" note on an invoice line now appears for no-sample/imaging lines only after result completion (it previously appeared at "Imaging performed"). For the Owner it carries an **Unlock (same day)** link that opens the shared ConfirmDialog (reason required).
- No other badge, label or layout changed. The invoice screens refresh sample status without a reload (no visual change).

## 16. Cancellation, Disbursement and Business Day UI

- **Line action:** a small underlined **Cancel Test** link under the test name on each eligible line of the invoice detail (shown only when the server says `can_request_cancellation` and the user has `refund.request`). There is no edit-price, discount, payment or add-line action.
- **Whole-invoice action:** a small underlined **Cancel Whole Invoice** link at the right of the "Investigations Ordered" heading, shown only on a Confirmed invoice where every remaining line is cancellable.
- **Cancel modal (one component, two scopes):** title **Cancel Test** or **Cancel Whole Invoice**; an amber note that the figures are system-calculated and cannot be edited, that the cancellation takes effect immediately without approval, and that no money is paid by this click. Line scope: a read-only list (label left, value right): Invoice total, Paid so far, This line price, Amount retained, **Refund amount** (highlighted row), New due. Whole-invoice scope: Invoice total, Paid so far, one small row per test (name, price, "refund ৳X"), Amount retained, **Total refund** (highlighted), New due. When a refund is due a grey note says the refund waits for a separate Disburse step. One optional Reason field. Buttons: Close, **Cancel Test** / **Cancel Whole Invoice**. There is no amount input and no payout channel.
- **Disburse placement:** a red-tinted banner at the top of the invoice detail, above the test table, shown when any refund on the invoice is `APPROVED` with an amount and the user has `refund.disburse`: "Refund of ৳X is pending payout" with a **Disburse now** button. It opens the **Disburse Approved Refund** modal (amount read-only, channel select limited to the channels used, reference for non-cash): a separate second click; nothing is pre-submitted. The per-request Disburse buttons in the Refund Lifecycle list and on the Refunds page open the same modal.
- **"Sample already taken" dialog:** a small modal, plain text (cancellation now needs the Admin/Owner "Not Performed" approval; inform Admin/Owner), one OK button.
- **Refunds page:** intro text says pre-sample cancellations take effect at once and only D15 Not Performed requests wait for Admin/Owner approval; the approval modal shows the live breakdown, the amount at request time and an amber warning when they differ, with a required approval reason (optional for D15).
- **Line status badge:** the Sample column shows `display_status` when a cancellation/refund exists (amber while requested, red once cancelled), otherwise the usual sample badge.
- **Header business-day badge:** "Day #N Open (date)" (green) or "Business Day Closed" (red); the same for every role, including Lab Tech.

## 17. Reference Range UI (D24, Prompt 14)

- **Catalog & Deleted → Reference ranges tab** (Admin/Owner, same page and button styles as the Tests tab): a searchable test list on the left; on the right one card per component (name, code, unit) with an **Add band** button and a table: Sex (Any/Male/Female), Age (days), Reference, Critical (low / high), Version (`v1`, `v2`, marked "(old)" for history), actions **New version** and **Retire** on current rows only. A "Show old versions" checkbox reveals superseded and retired rows (greyed). A component with no current band shows an amber "No current band" row.
- **Add band / New version modal:** Sex, Age from (days), Age to (days, empty = no limit), Reference min/max, Critical low/high, optional report text, optional note. For a new version the sex and age fields are read-only and an amber note says it applies to future results only. **Retire** opens the standard confirm dialog with a required reason.
- **Result entry modal:** the Reference column shows the range text of the band chosen for the patient (or "min - max" when no text), a grey "any-sex range used" line when the any-sex band was the fallback, and an amber "No range for this age/sex: review manually" when no band fits.

## 18. Doctor Sign-off UI (D22, Prompt 15)

- **Sidebar item** "Doctor Sign-off" (icon user-check) shown to holders of `result.complete_doctor_routed` (Admin, Owner, Doctor); route `/doctor-approvals`. A user without the permission sees a "no permission" card.
- **Queue page:** same look as the Ready Results list (search box, refresh, bordered card, table with Invoice #, Patient, Test, Rule badge, Technician, Doctor, actions). Admin/Owner get a doctor search filter ("Showing all doctors" until one is picked) and an **Assign doctor** button per row; a DOCTOR login sees a banner when its login is not linked to a doctor profile. Empty state: "Nothing is waiting for a doctor's approval."
- **Review modal (wide):** a blue summary strip (approval rule, technician sign-off, doctor name and registration number), then the shared read-only result body (`ResultPreviewBody`, extracted from the report preview modal so there is one result display), then the action area. Path A: doctor search-by-name picker (individual doctors only, shows registration number), the attestation checkbox with the explicit wording, optional notes, **Confirm approval on behalf** (disabled until a doctor is picked and the box ticked). Path B: a one-line "You are approving this result as Dr. X (Reg ...)" and **Approve**. An already approved item shows a green line saying who approved and whether it was recorded on the doctor's behalf.
- **User Management:** a **Doctor profile** select appears for DOCTOR users (create and edit) to link the login to a doctor profile.

## 19. Final Report UI (Module 14, Prompt 16)

- **Finalize area** at the bottom of the Preview Report modal (Lab Ready tab, sidebar Ready Results), shown to holders of `result.enter` for a submitted result that is not Final yet: a bordered strip with the text "Finalizing closes this report: its content can no longer be changed." and a green-olive **Finalize report** button; when it cannot be finalized the strip shows the reason (for example "Waiting for the doctor's approval.") and the button is disabled. After success a toast "Report finalized" shows the report number, the modal closes and the lists refresh.
- **Final note:** a Final report's preview shows a green note "Final report RPT-… Stored content, it cannot be changed." with the technician line and the doctor line (name, "Reg …", "approved personally" or "recorded on the doctor's behalf").
- **Issued Reports tab:** each row gets a document-icon button, **View result**, before the print-preview eye; it opens a wide modal "Final report" with the shared read-only result body (`ResultPreviewBody`) from the stored snapshot. Seeded older reports show "This report was issued before report snapshots existed and has no stored result content."
- **Result entry modal:** no visible change; it sends the opened version of the result so a conflicting save shows the server's "changed by X" message as a toast.

## 20. Handover, Dues and Settings UI (Prompt 17)

- **Issued Reports (handover):** the search box placeholder reads "Bill no. (final / temp), patient no., test, mobile, name..." and is wider; the Paid / Held filter now filters on the server. A row with a due gets a green-outlined **Take payment** button before Deliver; it opens the shared **Settle Due** modal. The status badge reads DUE HOLD only when the report is actually held (the hold setting is on).
- **Settle Due modal** (`SettleDueModal.tsx`): the former Dues page modal and thermal receipt, extracted unchanged so Dues and handover use one component.
- **Dues page:** tabs Bills with due, Call list, Write-offs (Admin/Owner) and Doctor balances (Admin/Owner), as pill tabs like Ready Reports. Age-of-bill chips (All, 0-7, 8-30, 31-90, Over 90 days; the call list shows the bucket totals). The bills table gains an Age badge (green, amber, orange, red by bucket) and a "written off" note under the due; Admin/Owner see a red-outlined **Write off** button next to Settle Due. The write-off modal states the due, that it is bad debt and not a discount, the Admin limit (for an Admin) and requires an amount and a reason. The Write-offs tab lists requests with a status badge (Written off, Waiting for Owner, Rejected) and Approve / Reject buttons for the Owner. The Doctor balances tab shows two columns with their meaning under each heading (wholesale receivable in red, professional-fee payable in teal) and a note that the figures stay 0 until the source modules exist.
- **Settings page** (`/settings`, sidebar "Settings", Owner): a card with the hold-while-due checkbox and a card with the Admin write-off limit (number field and Save) and a card with the day-close variance tolerance (number field and Save).

## 21. Day Close and Accounting UI (Prompt 18)

- **Business Day page (`/business-day`):** the open dialog and the status cards are as before. For Admin / Owner a **Day close** panel (`DayClosePanel.tsx`) is added; the old "Close Business Day (Admin)" header button is gone (the panel closes the day). Receptionist and Cashier still see the disabled close button.
- **Expected cash** is a short list with every term visible: opening cash, + cash collections, - cash refunds, - bank deposits, - owner withdrawals, - small expenses, then the four unbuilt payouts (commission, visit-fee handover, consultant fees, outside-lab payments) each at 0 and labelled "not built yet, always 0", and the **Expected cash** total. A line states that write-offs are not cash and that unsynced items are 0 because offline sync is not built.
- **Count:** a counted-cash field, a live **Variance** (green at 0, red otherwise, "short" / "over"), a reason field that becomes required above the tolerance (the Close button stays disabled until it is filled), and one counted field per wallet / bank channel that had activity, each next to its own expected figure.
- **Movements:** while the day is open, a one-line form (kind, amount, note) records an expense, a bank deposit or (Owner only) an owner withdrawal; the day's entries are listed under it.
- **Closed day:** shows counted cash, variance and reason with the note that a closed day cannot be edited; the Owner sees a reason field and **Reopen for adjustments**. A reopened day shows its reopen reason and a list of its journal entries each with **Reverse** (needs the adjustment reason); **Close the day again** reuses the count form.
- **Accounting page (`/accounting`, sidebar "Accounting", `accounting.view`):** pill tabs Cash book, Daily income & expense, Dues, Cost by referrer; From / To date fields (empty = everything); an Account selector on the cash book; a one-line summary above the table; **Export CSV (Excel)**. A note says the journal starts at deployment. Cost by referrer shows 0 cost with the Module 19 note.
- **Settings page:** the variance tolerance card is described in section 20.

## 22. Doctor / 3rd-party Edit (Prompt 19)

- **Catalog & Deleted > Doctors & 3rd parties:** each row now has **Edit** (pencil, outlined) beside the red **Delete**. Edit opens a modal "Edit doctor / 3rd party" with Name (required), Type (Doctor / Third Party), Phone, Registration no., Specialty and Chamber, Cancel and Save. A note says rates and commission are not edited here. Save updates the record in place and the list reloads; a toast reminds that saved bills and reports keep what they already captured. The tab is visible to the same Admin / Owner holders of `referrer.manage` as Delete.
