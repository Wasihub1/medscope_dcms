"""
Prompt 10D Parts 4 and 5 — one login = one fixed role, Dashboard landing, central permission
layer, per-user overrides and the user-management endpoints.
"""
import secrets
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.core.permissions import (
    MONEY_PERMISSIONS,
    ROLE_DEFAULTS,
    ROLES,
    effective_permissions,
)
from backend.app.core.security import CurrentActor
from backend.app.models.audit import AuditLog
from backend.app.models.tenant import Tenant
from backend.app.models.user import Staff, StaffPermissionOverride, StaffRole
from tests.conftest import (
    ADMIN_HEADERS,
    CASHIER_HEADERS,
    OWNER_HEADERS,
    RECEPTIONIST_HEADERS,
    TECH_KAMAL_HEADERS,
    TECH_NASRIN_AUTH_TOKEN,
    TEST_PASSWORD_DEFAULT,
)

NEW_PASSWORD = "T" + secrets.token_urlsafe(16)  # generated per run; never stored


def _fresh_client():
    """Separate cookie jar so logins here never leak cookies into other tests."""
    from backend.app.main import app
    return TestClient(app, base_url="http://testserver/api/v1")


def _uname(prefix):
    return f"{prefix}_{uuid4().hex[:8]}"


def _create_user(client, headers, role, **extra):
    body = {"username": _uname(role.lower()), "display_name": f"Test {role}", "password": NEW_PASSWORD, "role": role}
    body.update(extra)
    return client.post("/users", headers=headers, json=body)


def _login(username, password=NEW_PASSWORD):
    c = _fresh_client()
    res = c.post("/auth/login", json={"username": username, "password": password})
    return c, res


# ---------------------------------------------------------------------------
# Part 4 — single role, no switching, Dashboard landing
# ---------------------------------------------------------------------------
def test_split_accounts_have_exactly_one_role_each(client, db_session):
    for uname, role in [("reception_fatima", "RECEPTIONIST"), ("cashier_fatima", "CASHIER"),
                        ("admin_tariq", "ADMIN"), ("owner_tariq", "OWNER")]:
        c, res = _login(uname, TEST_PASSWORD_DEFAULT)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["roles"] == [role] and body["acting_role"] == role
        assert body["home_route"] == "/dashboard"
    rows = db_session.execute(select(StaffRole.staff_id)).scalars().all()
    assert len(rows) == len(set(rows))  # never two roles for one user


def test_acting_role_endpoint_is_gone(client):
    assert client.post("/auth/acting-role", headers=ADMIN_HEADERS, json={"role": "OWNER"}).status_code == 404


def test_second_role_row_is_rejected_by_database(db_session):
    admin = db_session.execute(select(Staff).where(Staff.username == "admin_tariq")).scalar_one()
    db_session.add(StaffRole(staff_id=admin.id, role="OWNER", is_primary=False))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_every_role_lands_on_dashboard_and_lab_tech_gets_no_money(client):
    me = client.get("/auth/me", headers=TECH_KAMAL_HEADERS).json()
    assert me["home_route"] == "/dashboard"
    assert not (set(me["permissions"]) & MONEY_PERMISSIONS)
    # The financial dashboard endpoint is refused to LAB_TECH; the lab summary has no money fields
    assert client.get("/dashboard", headers=TECH_KAMAL_HEADERS).status_code == 403
    summary = client.get("/worklist/summary", headers=TECH_KAMAL_HEADERS)
    assert summary.status_code == 200
    money_words = ("price", "amount", "net", "gross", "due", "paid", "discount", "commission")
    assert not any(any(w in k.lower() for w in money_words) for k in summary.json().keys())
    # Front desk still sees the financial dashboard
    assert client.get("/dashboard", headers=CASHIER_HEADERS).status_code == 200


# ---------------------------------------------------------------------------
# Part 5 — permission defaults identical to the old gates
# ---------------------------------------------------------------------------
def test_role_list_and_defaults_match_pre_10d_behavior():
    # Prompt 10E changed three defaults on purpose (DOCTOR role added, CASHIER release-with-due
    # removed, LAB_TECH profile.manage added); everything else is still the pre-10D behavior.
    assert ROLES == ("OWNER", "ADMIN", "RECEPTIONIST", "CASHIER", "LAB_TECH", "DOCTOR")
    front = ROLE_DEFAULTS["RECEPTIONIST"]
    assert ROLE_DEFAULTS["CASHIER"] == front
    assert "report.release_with_due" not in ROLE_DEFAULTS["CASHIER"]
    # Prompt 11: audit.view is OWNER-only by default (grantable to ADMIN); otherwise identical
    assert ROLE_DEFAULTS["ADMIN"] | {"audit.view", "invoice.line_unlock", "settings.manage"} == ROLE_DEFAULTS["OWNER"]  # Prompt 12 adds the owner-only line unlock
    assert "audit.view" not in ROLE_DEFAULTS["ADMIN"]
    for key in ("refund.approve", "business_day.close", "user.manage", "worklist.view", "result.enter", "worklist.reassign"):
        assert key not in front
    assert ROLE_DEFAULTS["LAB_TECH"] == {"worklist.view", "sample.manage", "worklist.update", "result.enter", "refund.request_d15", "profile.manage"}
    assert not (ROLE_DEFAULTS["LAB_TECH"] & MONEY_PERMISSIONS)


@pytest.mark.parametrize("headers,method,path,expected", [
    (RECEPTIONIST_HEADERS, "get", "/worklist", 403),
    (RECEPTIONIST_HEADERS, "get", "/invoices", 200),
    (CASHIER_HEADERS, "get", "/invoices", 200),
    (CASHIER_HEADERS, "post", "/business-day/close", 403),
    (TECH_KAMAL_HEADERS, "get", "/invoices", 403),
    (TECH_KAMAL_HEADERS, "get", "/worklist", 200),
    (ADMIN_HEADERS, "get", "/worklist", 200),
    (ADMIN_HEADERS, "get", "/users", 200),
    (OWNER_HEADERS, "get", "/users", 200),
    (RECEPTIONIST_HEADERS, "get", "/users", 403),
    (CASHIER_HEADERS, "get", "/users", 403),
    (TECH_KAMAL_HEADERS, "get", "/users", 403),
])
def test_endpoint_access_matrix_unchanged(client, headers, method, path, expected):
    res = getattr(client, method)(path, headers=headers, **({"json": {"notes": "matrix"}} if method == "post" else {}))
    assert res.status_code == expected, f"{path}: {res.status_code} {res.text[:200]}"


# ---------------------------------------------------------------------------
# Part 5 — user management, overrides and safety rules
# ---------------------------------------------------------------------------
def test_create_user_with_single_role_and_lab_section(client, db_session):
    res = _create_user(client, ADMIN_HEADERS, "LAB_TECH", lab_section="MICROBIOLOGY")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["role"] == "LAB_TECH" and body["lab_section"] == "MICROBIOLOGY"
    assert "password" not in body and "password_hash" not in body
    assert body["permissions"]["effective"] == sorted(ROLE_DEFAULTS["LAB_TECH"])
    c, login = _login(body["username"])
    assert login.status_code == 200 and login.json()["home_route"] == "/dashboard"
    db_session.expire_all()
    assert db_session.execute(
        select(AuditLog).where(AuditLog.action == "USER_CREATED", AuditLog.entity_id == str(body["id"]))
    ).scalar_one_or_none() is not None
    # lab section is only valid for LAB_TECH
    bad = _create_user(client, ADMIN_HEADERS, "RECEPTIONIST", lab_section="HEMATOLOGY")
    assert bad.status_code == 400


def test_override_grant_and_revoke_are_enforced_by_real_endpoints(client):
    user = _create_user(client, ADMIN_HEADERS, "RECEPTIONIST").json()
    c, login = _login(user["username"])
    assert c.get("/invoices", headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 200
    assert c.get("/worklist").status_code == 403

    res = client.put(f"/users/{user['id']}/permissions", headers=ADMIN_HEADERS,
                     json={"overrides": {"invoice.view": False, "worklist.view": True}})
    assert res.status_code == 200, res.text
    eff = set(res.json()["permissions"]["effective"])
    assert "invoice.view" not in eff and "worklist.view" in eff
    assert c.get("/invoices").status_code == 403
    assert c.get("/worklist").status_code == 200

    # Removing the overrides returns to the role defaults
    client.put(f"/users/{user['id']}/permissions", headers=ADMIN_HEADERS,
               json={"overrides": {"invoice.view": None, "worklist.view": None}})
    assert c.get("/invoices").status_code == 200
    assert c.get("/worklist").status_code == 403


def test_lab_tech_can_never_get_money_permissions(client, db_session):
    tech = _create_user(client, ADMIN_HEADERS, "LAB_TECH", lab_section="HEMATOLOGY").json()  # 10E: room required
    res = client.put(f"/users/{tech['id']}/permissions", headers=ADMIN_HEADERS, json={"overrides": {"invoice.view": True}})
    assert res.status_code == 400
    # Even a money override written directly into the DB is ignored for LAB_TECH
    nasrin = db_session.execute(select(Staff).where(Staff.username == "tech_nasrin")).scalar_one()
    row = StaffPermissionOverride(tenant_id=nasrin.tenant_id, staff_id=nasrin.id, permission_key="invoice.view", granted=True)
    db_session.add(row)
    db_session.commit()
    try:
        headers = {"Authorization": f"Bearer {TECH_NASRIN_AUTH_TOKEN}", "X-Requested-With": "XMLHttpRequest"}
        assert client.get("/invoices", headers=headers).status_code == 403
        assert not (set(client.get("/auth/me", headers=headers).json()["permissions"]) & MONEY_PERMISSIONS)
    finally:
        db_session.delete(row)
        db_session.commit()
    assert not (effective_permissions("LAB_TECH", {k: True for k in MONEY_PERMISSIONS}) & MONEY_PERMISSIONS)


def test_no_self_change_and_no_owner_escalation(client, db_session):
    admin = db_session.execute(select(Staff).where(Staff.username == "admin_tariq")).scalar_one()
    assert client.put(f"/users/{admin.id}/role", headers=ADMIN_HEADERS, json={"role": "OWNER"}).status_code == 403
    assert client.put(f"/users/{admin.id}/permissions", headers=ADMIN_HEADERS,
                      json={"overrides": {"refund.approve": False}}).status_code == 403
    assert client.post(f"/users/{admin.id}/deactivate", headers=ADMIN_HEADERS).status_code == 403
    # ADMIN cannot create an OWNER; OWNER can
    assert _create_user(client, ADMIN_HEADERS, "OWNER").status_code == 403
    assert _create_user(client, OWNER_HEADERS, "OWNER").status_code == 201


def test_cannot_grant_permissions_you_do_not_hold(client):
    # A receptionist given user.manage still cannot grant refund.approve (they do not hold it)
    manager = _create_user(client, ADMIN_HEADERS, "RECEPTIONIST", permission_overrides={"user.manage": True}).json()
    c, login = _login(manager["username"])
    assert login.status_code == 200
    target = _create_user(client, ADMIN_HEADERS, "RECEPTIONIST").json()
    hdr = {"X-Requested-With": "XMLHttpRequest"}
    res = c.put(f"/users/{target['id']}/permissions", headers=hdr, json={"overrides": {"refund.approve": True}})
    assert res.status_code == 403
    assert c.put(f"/users/{target['id']}/permissions", headers=hdr, json={"overrides": {"worklist.view": False}}).status_code == 200


def test_deactivate_reactivate_and_reset_password(client):
    user = _create_user(client, ADMIN_HEADERS, "CASHIER").json()
    c, login = _login(user["username"])
    assert login.status_code == 200
    assert client.post(f"/users/{user['id']}/deactivate", headers=ADMIN_HEADERS).json()["active"] is False
    assert c.get("/auth/me").status_code == 401  # sessions revoked
    assert _login(user["username"])[1].status_code == 401
    assert client.post(f"/users/{user['id']}/reactivate", headers=ADMIN_HEADERS).json()["active"] is True
    new_pwd = "T" + secrets.token_urlsafe(16)
    res = client.post(f"/users/{user['id']}/reset-password", headers=ADMIN_HEADERS, json={"new_password": new_pwd})
    assert res.status_code == 200 and new_pwd not in res.text
    assert _login(user["username"], new_pwd)[1].status_code == 200


def test_last_active_user_admin_is_protected(db_session):
    from backend.app.services import user_admin_service as svc
    tid = f"t-{uuid4().hex[:8]}"
    db_session.add(Tenant(id=tid, name="Last admin test", slug=tid))
    db_session.flush()
    only_admin = Staff(tenant_id=tid, username=_uname("solo_admin"), display_name="Solo", role="ADMIN", active=True)
    db_session.add(only_admin)
    db_session.flush()
    db_session.add(StaffRole(staff_id=only_admin.id, role="ADMIN", is_primary=True))
    db_session.flush()
    # An external actor (e.g. CLI / platform) acting on that tenant
    actor = CurrentActor(id=-1, tenant_id=tid, username="system", display_name="System", role="OWNER",
                         permissions=ROLE_DEFAULTS["OWNER"])
    for action in (
        lambda: svc.set_user_active(db_session, actor, only_admin, False),
        lambda: svc.set_user_role(db_session, actor, only_admin, "RECEPTIONIST", None),
        lambda: svc.set_user_permissions(db_session, actor, only_admin, {"user.manage": False}),
    ):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 409
    db_session.rollback()
