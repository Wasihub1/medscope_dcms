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
  /* Core Pillars */
  --color-brand-orange: #CF8852;
  --color-brand-platinum: #E8E7E3;
  --color-brand-moss: #525333;

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

- **Primary Font Family:** Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif.
- **Bangla Font Fallback:** 'Noto Sans Bengali', 'SolaimanLipi', 'Kalpurush', sans-serif.
- **Monospace Numbers & IDs:** 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, monospace.
- **Hierarchy Scale:**
  - Page Titles: `text-xl font-bold text-[#1B1B0E]` (20px)
  - Section Headings: `text-sm font-bold text-[#525333]` (14px)
  - Standard Labels / Inputs: `text-xs font-semibold text-[#54524A]` (12px)
  - Metadata / Microcopy: `text-[11px] text-[#6D6A60]` (11px)

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

## 8. In-Context Patient History Nested Overlay

When accessing past invoices from the **Patient History** view (`/patients`):
- The invoice detail is opened as a **nested modal overlay** over the active patient history drawer.
- **Route Preservation:** The application route remains strictly `/patients`. No redirection to `/invoices` occurs.
- **State Preservation:** Closing the invoice overlay returns the user directly to the patient's active tab (e.g. *Invoices & Tests*), preserving scroll position, active search terms, and selected patient context.

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
In accordance with Module 11 Section 5.4, the technician UI never contains monetary figures, discounts, test prices, payments, or commission indicators anywhere on the workbench.

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
  - Clinical History, Technique, Detailed Findings, Impression, and Clinical Comments.

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
