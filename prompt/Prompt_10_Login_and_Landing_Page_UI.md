# Prompt_10 — Branded Landing Page and Animated Login Page

You are working on **MedScope DCMS** (React 19 + TypeScript + Vite). Real sign-in exists from Prompt_09.

**Prerequisite:** Prompt_09 completed (auth routes, session handling, a functional `/login`). Verify first; if missing, stop and report.

## 1. Goal

Build two public, branded pages: a clean **landing page** at `/` and an animated **login page** at `/login`, matching the approved design. Signed-in users who open `/` or `/login` are redirected to their role's home route. Unknown routes show a simple branded 404.

## 2. Read first

1. The nine canonical docs, especially `docs/DESIGN.md` and how the frontend is styled today (Tailwind or plain CSS, tokens, existing fonts and icon library). Follow the existing approach; do not introduce a second styling system.
2. **Design reference files** (provided by the owner): `docs/design-reference/Landing.dc.html` and `docs/design-reference/Login.dc.html`. They are visual references. Ignore their `x-dc`, `helmet`, `support.js` and `{{accent}}` wrappers; reuse the markup structure, sizes, SVG shapes and CSS keyframes. If these files are missing, build from Section 3 and report that they were missing.
3. **Design skill:** `docs/design-skills/landing-page-design/SKILL.md` if present. Use its Part B visual rules (typography discipline, spacing, motion curve, states, accessibility, 390px check) **with these explicit owner overrides, which win over the skill**:
   - Colors come from the MedScope brand, not the skill's dark palette (Section 3.1).
   - Backgrounds are flat (no gradients, no gradient washes).
   - Fonts: Manrope plus **Noto Sans Bengali as the Bangla fallback** (the skill's font list has no Bangla). Prefer self-hosted packages (`@fontsource/manrope`, `@fontsource/noto-sans-bengali`) over runtime Google Fonts requests, because customers may have weak internet. No italics, no weight above 700.
   - Do **not** apply the skill's Part A marketing structure: no FAQ, pricing, testimonials, proof section or tagline-reveal section. Copy stays minimal as specified below.
   - Never invent facts, statistics, customer names or logos.
   - Icons: Phosphor, Solar or Iconamoon, or the inline SVGs from the reference files; never Material icons.

## 3. Specification

### 3.1 Brand tokens
Persian Orange `#CF8852` (accent, primary buttons), Platinum `#E8E7E3` (page background), Dark Moss `#525333` (header/panels), ink `#26270F` (text), secondary text `#3D3E1F`, white `#FFFFFF`. Button text on orange is ink `#26270F` (contrast). Define them as tokens; keep the accent color a single variable.

### 3.2 Landing page (`/`)
- **Header:** logo mark (Dark Moss rounded square with orange plus) + "MedScope DCMS", and one "Sign in" button.
- **Hero** (two columns, wraps on small screens): H1 "Your diagnostic center, in one place" (max width 680px, balanced wrapping); one short line "Billing, samples, results and reports."; one primary button "Sign in" (single CTA). No other text blocks.
- **Animated scene** on the right inside a Dark Moss rounded panel: an ECG line that draws itself in a loop; a sample tube that fills and refills; a small dot travelling along a line; and three short chips that appear one after another and fade out: "Sample taken", "Result entered", "Report ready". Decorative only: **no real or fake patient data**.
- **Endless scrolling strip** (carousel/marquee) on a white band under the hero: icon + label items **Register, Sample, Result, Report**, scrolling continuously and seamlessly, pausing on hover/focus. Drive it from a **data array** so the owner can add more items later without touching layout code. Duplicate the set as needed so there is no visible gap on wide screens.
- **Footer:** just "MedScope DCMS".
- Keep the page clean: do not add more copy or sections.

### 3.3 Login page (`/login`)
- Two panels (stack on small screens). **Left:** Dark Moss panel with the logo, the large animated **ECG illustration** (draws itself in a loop, with a pulsing marker at the first peak), and a small note "Illustration only. No patient information is shown on this page." **No step tiles/cards.**
- **Right:** Platinum background with a centered white rounded card: heading "Sign in", one helper sentence, a real `<form>` with **Username** and **Password** (each with a visible `<label>`, proper `autocomplete`, a **Show/Hide** toggle on the password), a full-width orange "Sign in" button (shows "Signing in…" and is disabled while the request runs), an inline `aria-live` error area, the line "Forgot your password? Ask your center administrator to reset it.", and a "Back to the overview" link.
- Error messages (calm, specific, no exclamation marks): wrong credentials, locked account ("This account is locked. Ask your administrator to reset it."), session expired, network failure. Enter key submits. Client-side required-field validation.

### 3.4 Motion rules
Animate only `transform`, `opacity` and SVG stroke properties. Use the curve `cubic-bezier(0.22, 1, 0.36, 1)` for non-continuous motion (the marquee may be linear). Respect `prefers-reduced-motion`: no movement, show final states, marquee becomes a static wrapped row. Lightweight SVG/CSS only: no video, no 3D, no heavy animation library.

### 3.5 Quality bar
Visible focus rings; hover and active states on every control; keyboard operable; semantic landmarks (`header`, `main`, `footer`, `nav`); skip-to-content link; sensible `<title>`, meta description and social tags; branded favicon from the logo mark; alt text/aria labels; contrast at least 4.5:1 for text. No horizontal overflow at **390px** wide; primary action visible without scrolling. Page styles must **not leak** into the signed-in app screens.

## 4. Limited browser exception (this prompt only)

You **may** use Playwright (Chromium) **only to take screenshots** of the two pages at 1360x900 and 390x844 (read-only, no sign-in, no data) and to check for horizontal overflow at 390px. Save screenshots under `report/screenshots/` and list them in the report. Do not use Playwright for any other flow and do not claim acceptance; the owner reviews the design personally. Record this exception in `docs/TESTING.md`. Also run typecheck, lint and build.

## 5. Must NOT do

- No changes to backend behavior or the auth logic (use what Prompt_09 provides; only fix a real defect if you find one and report it).
- No redesign of signed-in app screens; no new copy, sections, FAQ, pricing or testimonials; no invented numbers or logos.
- No heavy dependencies; no external runtime font/CDN requests.
- Do not add soft delete or any other upcoming work.


## 6. Documentation specifics for this prompt (in addition to the nine-docs rule)

- `docs/DESIGN.md`: brand tokens, fonts and Bangla fallback, the layout and behavior of the landing and login pages, the animation inventory and reduced-motion behavior, how to add items to the scrolling strip, and the design-reference and design-skill file locations.
- `docs/WORKFLOWS.md`: the `/` and `/login` routes, the redirect of signed-in users to their role's home route, the 404 behavior, and the sign-in error states.
- `docs/TESTING.md`: the screenshot-only Playwright exception and where the screenshots are stored.
- `docs/ARCHITECTURE.md`: any ADL entry for font hosting, animation approach or route structure.
- `project-context.md`: current phase and state.

## Permanent project rules (apply to this prompt)

1. **Inspect first.** Read all nine canonical docs (`README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`) and the actual code you will touch. **The code is the truth.** If a doc disagrees with the code, say so in your report and correct the doc.
2. **Browser testing is prohibited** (no Playwright, Selenium, Cypress, Puppeteer, no opening the app in a browser), **except where this prompt explicitly grants a narrow exception**. Never claim browser acceptance; the product owner performs acceptance personally.
3. **Non-browser checks are expected:** `pytest`, TypeScript typecheck (`tsc -b`), lint, build, `alembic heads/current/check`, read-only DB inspection. Report exactly what you ran and the real output. Never write "passed" for anything you did not observe.
4. **Alembic rule.** Any change to a database model/schema requires a matching migration with the correct `down_revision` and a **single head**. Verify the current head before creating anything (last reported head: `a7d834bc912e`; later prompts may have moved it). Never reset, truncate or destroy existing data. If a migration cannot be applied, still create/review it and state the exact remaining action.
5. **Docs rule.** At the end, update **all nine** canonical docs so they are mutually consistent and match the code. If one has no substantive change, verify it and record that it was reviewed. Record every decision from this prompt in the right docs (SCOPE.md for business rules, ARCHITECTURE.md ADL for technical decisions, DATABASE.md, API.md, WORKFLOWS.md, DESIGN.md, TESTING.md). `project-context.md` must show current phase, state, completed work, known limitations, next step. Before finishing, **audit the docs you touched against the code** and fix mismatches.
6. **Report.** Write `report/PROMPT_10_IMPLEMENTATION_REPORT.md` with: Done / Partial / Blocked / Deferred table, files changed, migration/head status (say clearly if no migration was created), API and permission changes, tests added and their **actual** results, docs updated (one line each), remaining limitations, and an explicit statement about browser testing.
7. **Business rules to protect:** whole-taka integer money; payments, refunds, stock, audit, events, results and snapshots are append-only (never rewrite history); technicians never see financial data; keep accepted workflows and existing data.
8. **Owner decisions in force:** automatic LOW/HIGH/CRITICAL/NORMAL result flags are kept and technicians cannot override them; who may open/close the business day and who may physically disburse an approved refund are **not fixed** and will become configurable per customer later (do not change them now); only Admin/Owner approve refunds; self-approval of refunds is blocked by default.
9. **Working tree.** `git status` has previously shown ~15 tracked files as deleted (old prompt/report files and `DCMS Final Scope V1.docx`). Do **not** restore, delete or move them; just list them in the report.
10. **Never** put secrets, passwords or tokens in code, docs, reports, prompts or logs. Do not start any phase or module other than the one in this prompt.
