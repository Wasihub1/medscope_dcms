"""
MedScope DCMS — Central role & permission layer (Prompt 10D Part 5).

Single source of truth for:
- the role list (ROLES) — add a new role here and give it a default set;
- the permission keys (PERMISSIONS), derived from the checks that existed in the code
  before Prompt 10D (require_receptionist / require_admin / require_lab_tech_or_admin and
  the inline role checks in services);
- the default permission set per role (ROLE_DEFAULTS), equal to the behavior before 10D;
- effective permissions = role defaults, then per-user overrides (granted / revoked);
- one check function (has_permission) and one FastAPI dependency (require_permission).

Absolute rule: LAB_TECH and DOCTOR never receive a permission that exposes money, whatever the
overrides say (MONEY_RESTRICTED_ROLES). Money hiding in responses stays role-based.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Mapping, Optional

ROLES: tuple[str, ...] = ("OWNER", "ADMIN", "RECEPTIONIST", "CASHIER", "LAB_TECH", "DOCTOR")

# Roles that can never see money fields, even through an override.
# Prompt 10E: DOCTOR is money-restricted exactly like LAB_TECH.
MONEY_RESTRICTED_ROLES: FrozenSet[str] = frozenset({"LAB_TECH", "DOCTOR"})


@dataclass(frozen=True)
class PermissionDef:
    key: str
    label: str
    group: str
    exposes_money: bool


_DEFS: tuple[PermissionDef, ...] = (
    # Front desk (was require_receptionist: RECEPTIONIST, CASHIER, ADMIN, OWNER)
    PermissionDef("dashboard.view", "View the financial front-desk dashboard", "Front desk", True),
    PermissionDef("search.use", "Use global search (patients, invoices, tests, reports)", "Front desk", True),
    PermissionDef("patient.view", "View patients and patient history", "Front desk", True),
    PermissionDef("patient.create", "Register patients", "Front desk", False),
    PermissionDef("referrer.view", "View referrers and doctors", "Front desk", False),
    PermissionDef("referrer.create", "Add referrers and doctors", "Front desk", False),
    PermissionDef("test_catalog.view", "View the test catalog with prices", "Front desk", True),
    PermissionDef("invoice.view", "View and search invoices", "Billing", True),
    PermissionDef("invoice.create", "Create and edit DRAFT invoices", "Billing", True),
    PermissionDef("invoice.finalize", "Finalize invoices", "Billing", True),
    PermissionDef("invoice.reprint", "Reprint invoice receipts", "Billing", True),
    PermissionDef("payment.view", "View dues and payment history", "Billing", True),
    PermissionDef("payment.take", "Take payments and settle dues", "Billing", True),
    PermissionDef("refund.view", "View refund requests", "Refunds", True),
    PermissionDef("refund.request", "Request pre-sample refunds", "Refunds", True),
    PermissionDef("refund.disburse", "Disburse approved refunds", "Refunds", True),
    PermissionDef("assignment.manage", "Assign tests to destinations", "Front desk", False),
    PermissionDef("business_day.view", "View business day and drawer", "Business day", True),
    PermissionDef("business_day.open", "Open the business day", "Business day", True),
    PermissionDef("report.view", "View deliverable reports", "Reports", True),
    PermissionDef("report.deliver", "Deliver and print reports", "Reports", True),
    PermissionDef("profile.manage", "View and edit own profile", "Account", False),
    # Was the inline check in report_service.record_report_delivery (blocked only RECEPTIONIST)
    PermissionDef("report.release_with_due", "Release a report with a due without an override reason", "Reports", True),
    # Admin / Owner only (was require_admin and inline ADMIN/OWNER checks)
    PermissionDef("refund.approve", "Approve or reject refund requests", "Refunds", True),
    PermissionDef("business_day.close", "Close the business day", "Business day", True),
    PermissionDef("user.manage", "Manage users, roles and permissions", "Administration", False),
    PermissionDef("worklist.view_all", "See every room's worklist", "Laboratory", False),
    # Prompt 10E Part 7: move an order to another room any time before COMPLETED
    PermissionDef("worklist.reassign", "Reassign test orders to another room", "Laboratory", False),
    PermissionDef("result.complete_doctor_routed", "Complete doctor-routed tests; record doctor sign-off (own, or on a doctor's behalf with attestation)", "Laboratory", False),
    # Laboratory (was require_lab_tech_or_admin: LAB_TECH, ADMIN, OWNER)
    PermissionDef("worklist.view", "View the worklist of own room", "Laboratory", False),
    # Prompt 10E Part 6: doctor queue (AWAITING_DOCTOR orders from all rooms)
    PermissionDef("worklist.doctor_queue", "View the doctor queue (Awaiting Doctor, all rooms)", "Laboratory", False),
    PermissionDef("sample.manage", "Record sample taken / rejected", "Laboratory", False),
    PermissionDef("worklist.update", "Update order status, imaging, culture, outsourced, patient contact", "Laboratory", False),
    PermissionDef("result.enter", "Enter and save results", "Laboratory", False),
    PermissionDef("refund.request_d15", "Submit D15 (not performed) refund requests", "Laboratory", False),
    # Prompt 11: no existing key gated editing/deleting referrers or catalog tests (referrer.create is
    # held by the front desk, test_catalog.view exposes prices), so two Admin/Owner keys are added.
    # Their Deleted views carry no money, so they are not money keys.
    PermissionDef("referrer.manage", "Delete and restore doctors and 3rd parties", "Administration", False),
    PermissionDef("test_catalog.manage", "Delete and restore catalog tests; manage reference-range versions", "Administration", False),
    # Prompt 11 (small slice of Module 23): read-only audit log. Audit before/after text can contain
    # amounts, so it is a money key: LAB_TECH/DOCTOR can never be granted it.
    PermissionDef("audit.view", "View the audit log (read only)", "Administration", True),
    # Prompt 12 (D14): owner-only, reason-required, same-business-day unlock of a locked invoice line.
    # Prompt 17: owner-editable center settings (report hold, write-off limit); no existing key fits Owner-only edits.
    PermissionDef("settings.manage", "Edit center settings (report hold while due, Admin write-off limit)", "Administration", False),
    # Prompt 17 (D11): write off a patient due (Admin within the limit, Owner above); money.
    PermissionDef("due.writeoff", "Write off a patient due (Admin within the limit, Owner above it)", "Billing", True),
    # Prompt 17 (D43): a doctor's wholesale receivable and professional-fee payable; commission-adjacent, so not for the front desk.
    PermissionDef("doctor_balance.view", "View doctor balances (wholesale receivable and professional-fee payable)", "Administration", True),
    # Prompt 18 (Module 21): the four V1 accounting reports and the journal view; money, Admin/Owner by default.
    PermissionDef("accounting.view", "View accounting reports (cash book, income and expense, dues, cost by referrer) and the journal", "Administration", True),
    PermissionDef("invoice.line_unlock", "Unlock a locked test line (same business day, reason required)", "Administration", False),
)

PERMISSIONS: Dict[str, PermissionDef] = {d.key: d for d in _DEFS}
MONEY_PERMISSIONS: FrozenSet[str] = frozenset(k for k, d in PERMISSIONS.items() if d.exposes_money)

_FRONT_DESK = frozenset({
    "dashboard.view", "search.use", "patient.view", "patient.create", "referrer.view", "referrer.create",
    "test_catalog.view", "invoice.view", "invoice.create", "invoice.finalize", "invoice.reprint",
    "payment.view", "payment.take", "refund.view", "refund.request", "refund.disburse",
    "assignment.manage", "business_day.view", "business_day.open", "report.view", "report.deliver",
    "profile.manage",
})
_LAB = frozenset({"worklist.view", "sample.manage", "worklist.update", "result.enter", "refund.request_d15"})
_ADMIN_ONLY = frozenset({
    "refund.approve", "business_day.close", "user.manage", "worklist.view_all",
    "result.complete_doctor_routed", "report.release_with_due", "worklist.reassign",
    "worklist.doctor_queue", "referrer.manage", "test_catalog.manage", "due.writeoff", "doctor_balance.view", "accounting.view",
})
# Prompt 11: audit.view is ON by default for OWNER only; an Owner can grant it to an Admin.
_OWNER_ONLY = frozenset({"audit.view", "invoice.line_unlock", "settings.manage"})

# Defaults reproduced the pre-10D behavior in Prompt 10D; Prompt 10E owner decisions:
# - LAB_TECH gets profile.manage (own My Profile only).
# - CASHIER can no longer release a report while a due exists (report.release_with_due removed);
#   RECEPTIONIST and CASHIER are blocked, ADMIN/OWNER may release with an override reason.
# - worklist.reassign: ADMIN and OWNER by default (grantable per user).
# - DOCTOR (assumption, see the 10E report): money-free Dashboard, the doctor queue and its
#   results, and completion of doctor-routed tests through the existing endpoint. No invoicing,
#   payment, refund or business-day permissions; money keys can never be granted.
ROLE_DEFAULTS: Dict[str, FrozenSet[str]] = {
    "OWNER": _FRONT_DESK | _LAB | _ADMIN_ONLY | _OWNER_ONLY,
    "ADMIN": _FRONT_DESK | _LAB | _ADMIN_ONLY,
    "RECEPTIONIST": _FRONT_DESK,
    "CASHIER": _FRONT_DESK,
    "LAB_TECH": _LAB | frozenset({"profile.manage"}),
    "DOCTOR": frozenset({
        "worklist.view", "worklist.doctor_queue", "worklist.update", "result.enter",
        "result.complete_doctor_routed", "profile.manage",
    }),
}
assert set(ROLE_DEFAULTS) == set(ROLES)
assert all(p in PERMISSIONS for perms in ROLE_DEFAULTS.values() for p in perms)
assert not any(ROLE_DEFAULTS[r] & MONEY_PERMISSIONS for r in MONEY_RESTRICTED_ROLES)

# Roles that hold user.manage by default; used for "last administrator" protection.
USER_ADMIN_ROLES: FrozenSet[str] = frozenset(r for r, p in ROLE_DEFAULTS.items() if "user.manage" in p)


def normalize_role(role: Optional[str]) -> str:
    return (role or "").strip().upper()


def is_valid_role(role: Optional[str]) -> bool:
    return normalize_role(role) in ROLES


def default_permissions(role: Optional[str]) -> FrozenSet[str]:
    return ROLE_DEFAULTS.get(normalize_role(role), frozenset())


def is_grant_allowed(role: Optional[str], permission_key: str) -> bool:
    """A money-exposing permission can never be granted to a money-restricted role."""
    return not (normalize_role(role) in MONEY_RESTRICTED_ROLES and permission_key in MONEY_PERMISSIONS)


def effective_permissions(role: Optional[str], overrides: Optional[Mapping[str, bool]] = None) -> FrozenSet[str]:
    """Role defaults, then per-user overrides (True = grant, False = revoke).
    Unknown keys are ignored. Money permissions are always removed for money-restricted roles."""
    perms = set(default_permissions(role))
    for key, granted in (overrides or {}).items():
        if key not in PERMISSIONS:
            continue
        if granted:
            perms.add(key)
        else:
            perms.discard(key)
    if normalize_role(role) in MONEY_RESTRICTED_ROLES:
        perms -= MONEY_PERMISSIONS
    return frozenset(perms)


def is_money_restricted(actor) -> bool:
    """True when money must be hidden from this actor (absolute, role based)."""
    return normalize_role(getattr(actor, "role", None)) in MONEY_RESTRICTED_ROLES


def has_permission(actor, permission_key: str) -> bool:
    """The single permission check used by endpoints and services."""
    if permission_key not in PERMISSIONS:
        raise KeyError(f"Unknown permission key: {permission_key}")
    perms: Iterable[str] = getattr(actor, "permissions", None) or ()
    return permission_key in perms


def require_permission(permission_key: str):
    """FastAPI dependency factory: resolves the session actor and enforces one permission."""
    if permission_key not in PERMISSIONS:
        raise KeyError(f"Unknown permission key: {permission_key}")

    from fastapi import Depends, HTTPException, status
    from backend.app.core.security import CurrentActor, get_current_actor

    def _dependency(actor: CurrentActor = Depends(get_current_actor)) -> CurrentActor:
        if not has_permission(actor, permission_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission_key}' is required for this action.",
            )
        return actor

    _dependency.__name__ = f"require_{permission_key.replace('.', '_')}"
    return _dependency


def require_any_permission(*permission_keys: str):
    """FastAPI dependency factory: the actor must hold at least one of the keys (Prompt 10E)."""
    for k in permission_keys:
        if k not in PERMISSIONS:
            raise KeyError(f"Unknown permission key: {k}")

    from fastapi import Depends, HTTPException, status
    from backend.app.core.security import CurrentActor, get_current_actor

    def _dependency(actor: CurrentActor = Depends(get_current_actor)) -> CurrentActor:
        if not any(has_permission(actor, k) for k in permission_keys):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: one of {', '.join(permission_keys)} is required for this action.",
            )
        return actor

    _dependency.__name__ = "require_any_" + "_".join(k.replace(".", "_") for k in permission_keys)
    return _dependency
