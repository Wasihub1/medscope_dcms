# Prompt_09 — Real Role-Based Login and Removal of the Development Role Switcher

You are working on **MedScope DCMS**. The app currently trusts a development **role switcher** (the frontend sends a role/staff identity that the backend trusts). The product owner wants **real sign-in** and wants the switcher **removed completely**.

**Prerequisite:** Prompt_08 Part B (separate test database) must be done so tests never touch the main database. Verify this first. If it is not done, stop and report; do not continue.

Scope is Module 1 (partial): sign-in, sessions, acting role, lockout. Full user management, PIN quick-switching and production hardening are **not** part of this prompt.

## 1. Business rules (from the scope)

- Roles currently in code: `RECEPTIONIST`, `LAB_TECH`, `ADMIN`, `OWNER` (verify). A person may hold **several roles** (M1.1); permissions are checked per action; the **acting role is logged on every action** (D57).
- Different first screen per role: Receptionist → patients/invoices area; Lab Tech → worklist (own tasks only); Admin/Owner → dashboard.
- **5 wrong password attempts lock the account** until an Admin/Owner resets it (M1, D58 spirit).
- Technicians never see financial data (already implemented; keep it intact).
- Existing role permissions are **not changed** by this prompt. They remain as coded today (they will be made configurable later).

## 2. Design to implement (you may propose a better equivalent; document any deviation in an ADL entry)

**Data model (Alembic migration, single head, no data loss, existing staff preserved):**
- Credentials for existing staff/users: `username` (unique per tenant, case-insensitive), `password_hash`, `is_active`, `failed_attempts`, `locked_at`, `last_login_at`, `password_changed_at`.
- A person-to-roles mapping that allows several roles per person (for example `staff_roles`), seeded from each existing person's current single role.
- Server-side **sessions** table (for example `auth_sessions`): hashed session id, staff id, acting role, created/expires/last_seen/revoked timestamps, user agent, IP. Sessions can be revoked (logout, password reset, deactivation).

**Passwords:** hash with Argon2id (or bcrypt if Argon2 is unavailable; justify). Minimum length 8, must differ from the username. Never log or return passwords/hashes.

**Session transport:** HttpOnly, `SameSite=Lax` cookie (`Secure` when served over HTTPS); no tokens in `localStorage`. Configure CORS with explicit origins and credentials. For state-changing requests require a custom header (for example `X-Requested-With`) as CSRF defense. Add idle timeout and absolute lifetime as settings (no hard-coded constants). If you choose JWT instead, justify it and keep revocation possible.

**Endpoints (`/api/v1/auth/...`):** `POST login`, `POST logout`, `GET me` (staff id, name, roles, acting role, home route), `POST acting-role` (switch among own roles), `POST change-password`. Admin/Owner: reset another user's password and unlock a locked user (API only, no UI in this prompt). Generic error text for bad credentials (do not reveal whether the username exists). Basic per-IP/username throttling.

**Enforcement:** every API route except health and `auth/login` requires an authenticated session (401 otherwise). Replace the old "role from request header" dependency with a dependency that returns the current user with `role = acting role` from the session, so existing role-guard functions keep working unchanged. Replace every place that used the switcher's staff identity with the session user.

**Audit:** write audit rows (same transaction) for login success, login failure, lockout, logout, password change/reset, acting-role change, each including the acting role.

**CLI (no secrets in repo):** `backend/scripts/manage_users.py` (or similar) with commands to create a user, set/reset a password (password read from a hidden prompt or an environment variable, never an argument echoed in logs), unlock, list users, and assign roles. Provide a documented way to give the **existing staff** (for example the lab technicians already in the data) credentials. Do not write any real password in code, docs or reports.

**Frontend:**
- Remove the **role switcher** component, its state, its request headers and all mentions, completely. No development flag keeps it alive.
- Add a **functional** `/login` page using the existing app styling (its visual redesign is a separate prompt), `credentials: 'include'` on API calls, an auth context, route guards (unauthenticated → `/login`; after login → the role's home route), a header user menu (name, acting role, **switch role** if the person has several, **sign out**), handling of 401 (session expired) and of the locked-account message.
- Keep every existing screen working for its role.

## 3. Tests (non-browser)

Rewrite the test fixtures so tests **sign in** as test users created by the test seed (in the test database from Prompt_08 Part B). Add tests for: successful login, wrong password, lockout at the 5th failure, unlock by Admin/Owner, 401 without a session, logout revoking the session, password change, acting-role switch (and refusal to act as a role the person does not hold), each existing role guard still enforced with real sessions, technician payloads still free of financial fields. Run the full suite and report the real counts.

## 4. Must NOT do

- No browser testing of any kind (no Playwright in this prompt).
- No PIN quick-switching (D58), no vendor role, no SMS/email password reset, no OAuth/SSO, no offline sign-in.
- Do not change which roles may do what; do not build the configurable permission layer; do not build a user-management UI.
- Do not redesign the login page visually (next prompt); do not add soft delete.
- No default or shared passwords anywhere in the repo.
- Do not wipe or reset the database; existing data must keep working.


## Permanent project rules (apply to this prompt)

1. **Inspect first.** Read all nine canonical docs (`README.md`, `project-context.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/WORKFLOWS.md`, `docs/DATABASE.md`, `docs/TESTING.md`) and the actual code you will touch. **The code is the truth.** If a doc disagrees with the code, say so in your report and correct the doc.
2. **Browser testing is prohibited** (no Playwright, Selenium, Cypress, Puppeteer, no opening the app in a browser), **except where this prompt explicitly grants a narrow exception**. Never claim browser acceptance; the product owner performs acceptance personally.
3. **Non-browser checks are expected:** `pytest`, TypeScript typecheck (`tsc -b`), lint, build, `alembic heads/current/check`, read-only DB inspection. Report exactly what you ran and the real output. Never write "passed" for anything you did not observe.
4. **Alembic rule.** Any change to a database model/schema requires a matching migration with the correct `down_revision` and a **single head**. Verify the current head before creating anything (last reported head: `a7d834bc912e`; later prompts may have moved it). Never reset, truncate or destroy existing data. If a migration cannot be applied, still create/review it and state the exact remaining action.
5. **Docs rule.** At the end, update **all nine** canonical docs so they are mutually consistent and match the code. If one has no substantive change, verify it and record that it was reviewed. Record every decision from this prompt in the right docs (SCOPE.md for business rules, ARCHITECTURE.md ADL for technical decisions, DATABASE.md, API.md, WORKFLOWS.md, DESIGN.md, TESTING.md). `project-context.md` must show current phase, state, completed work, known limitations, next step. Before finishing, **audit the docs you touched against the code** and fix mismatches.
6. **Report.** Write `report/PROMPT_09_IMPLEMENTATION_REPORT.md` with: Done / Partial / Blocked / Deferred table, files changed, migration/head status (say clearly if no migration was created), API and permission changes, tests added and their **actual** results, docs updated (one line each), remaining limitations, and an explicit statement about browser testing.
7. **Business rules to protect:** whole-taka integer money; payments, refunds, stock, audit, events, results and snapshots are append-only (never rewrite history); technicians never see financial data; keep accepted workflows and existing data.
8. **Owner decisions in force:** automatic LOW/HIGH/CRITICAL/NORMAL result flags are kept and technicians cannot override them; who may open/close the business day and who may physically disburse an approved refund are **not fixed** and will become configurable per customer later (do not change them now); only Admin/Owner approve refunds; self-approval of refunds is blocked by default.
9. **Working tree.** `git status` has previously shown ~15 tracked files as deleted (old prompt/report files and `DCMS Final Scope V1.docx`). Do **not** restore, delete or move them; just list them in the report.
10. **Never** put secrets, passwords or tokens in code, docs, reports, prompts or logs. Do not start any phase or module other than the one in this prompt.
