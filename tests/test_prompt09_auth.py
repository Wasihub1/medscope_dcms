"""
Prompt 09 Automated Test Suite: Real Role-Based Authentication & Session Management

Validates:
1. Successful staff login sets HttpOnly session cookie and returns acting role profile.
2. Wrong password returns generic 401 error.
3. Brute-force protection: 5 wrong attempts locks the account (returns 403).
4. Unlock by Admin clears lockout and resets failed attempts.
5. Unauthenticated request to protected endpoints rejected with 401.
6. Logout revokes the server-side session.
7. Password change verifies old password, validates strength, and updates hash.
8. Acting-role switch among held roles (and 403 on roles not held).
9. Existing role guards (require_receptionist, require_admin, require_lab_tech) enforced with real sessions.
10. Technician payloads remain completely free of financial data.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select
from backend.app.models.user import Staff, StaffRole
from backend.app.services.auth_service import hash_password
from backend.app.core.timezone import utc_now
from tests.conftest import (
    TEST_PASSWORD_DEFAULT,
    RECEPTIONIST_HEADERS,
    ADMIN_HEADERS,
    TECH_KAMAL_HEADERS,
)


def test_01_successful_login(client):
    """Test successful login with username and password sets session cookie."""
    res = client.post(
        "/auth/login",
        json={"username": "reception_fatima", "password": TEST_PASSWORD_DEFAULT},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == 1
    assert data["username"] == "reception_fatima"
    assert data["acting_role"] == "RECEPTIONIST"
    assert data["home_route"] == "/invoices"
    assert "RECEPTIONIST" in data["roles"]
    assert "CASHIER" in data["roles"]

    # Verify HttpOnly session cookie was set
    assert "medscope_session" in client.cookies


def test_02_wrong_password_generic_error(client):
    """Test wrong password returns generic 401 without revealing username existence."""
    res = client.post(
        "/auth/login",
        json={"username": "reception_fatima", "password": "wrong_password_attempt"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username or password"

    # Nonexistent username returns identical error
    res_nonexistent = client.post(
        "/auth/login",
        json={"username": "nonexistent_staff_xyz", "password": "random_password"},
    )
    assert res_nonexistent.status_code == 401
    assert res_nonexistent.json()["detail"] == "Invalid username or password"


def test_03_account_lockout_at_fifth_attempt(client, db_session):
    """Test 5 failed password attempts permanently locks the account until admin reset."""
    uname = f"lockout_{uuid4().hex[:8]}"
    pwd = "valid_password_2026"
    st = Staff(
        tenant_id="center-seba-01",
        username=uname,
        display_name="Lockout Victim",
        role="RECEPTIONIST",
        active=True,
        password_hash=hash_password(pwd),
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)
    db_session.add(StaffRole(staff_id=st.id, role="RECEPTIONIST", is_primary=True, created_at=utc_now()))
    db_session.commit()

    # 4 failed attempts: return 401
    for i in range(1, 5):
        r = client.post("/auth/login", json={"username": uname, "password": "bad_password"})
        assert r.status_code == 401

    # 5th failed attempt: triggers lockout
    r5 = client.post("/auth/login", json={"username": uname, "password": "bad_password"})
    assert r5.status_code == 401

    # 6th attempt (even with CORRECT password): returns 403 Forbidden with lockout warning
    r6 = client.post("/auth/login", json={"username": uname, "password": pwd})
    assert r6.status_code == 403
    assert "locked" in r6.json()["detail"].lower()


def test_04_unlock_by_admin(client, db_session):
    """Admin unlocks locked user, allowing immediate login with correct password."""
    uname = f"locked_victim_{uuid4().hex[:8]}"
    pwd = "locked_user_pass_2026"
    victim = Staff(
        tenant_id="center-seba-01",
        username=uname,
        display_name="Locked Victim",
        role="RECEPTIONIST",
        active=True,
        password_hash=hash_password(pwd),
        failed_attempts=5,
        locked_at=utc_now(),
    )
    db_session.add(victim)
    db_session.commit()
    db_session.refresh(victim)
    db_session.add(StaffRole(staff_id=victim.id, role="RECEPTIONIST", is_primary=True, created_at=utc_now()))
    db_session.commit()

    # Verify initially locked
    r_locked = client.post("/auth/login", json={"username": uname, "password": pwd})
    assert r_locked.status_code == 403

    # Receptionist cannot unlock (403)
    rec_unlock = client.post(
        f"/auth/users/{victim.id}/unlock",
        headers=RECEPTIONIST_HEADERS,
    )
    assert rec_unlock.status_code == 403

    # Admin unlocks successfully
    adm_unlock = client.post(
        f"/auth/users/{victim.id}/unlock",
        headers=ADMIN_HEADERS,
    )
    assert adm_unlock.status_code == 200
    assert "unlocked successfully" in adm_unlock.json()["message"]

    # Victim can now log in
    res = client.post(
        "/auth/login",
        json={"username": uname, "password": pwd},
    )
    assert res.status_code == 200
    assert res.json()["username"] == uname


def test_05_unauthenticated_request_rejected(client):
    """Protected endpoints strictly reject unauthenticated requests with 401."""
    # Clear cookies on test client
    client.cookies.clear()

    res = client.get("/patients")
    assert res.status_code == 401
    assert "Not authenticated" in res.json()["detail"]


def test_06_logout_revokes_session(client):
    """Logout revokes the server-side session and clears cookie."""
    # Log in
    login_res = client.post(
        "/auth/login",
        json={"username": "reception_fatima", "password": TEST_PASSWORD_DEFAULT},
    )
    assert login_res.status_code == 200

    # Request /auth/me succeeds
    me_res = client.get("/auth/me", headers={"X-Requested-With": "XMLHttpRequest"})
    assert me_res.status_code == 200

    # Logout
    logout_res = client.post("/auth/logout", headers={"X-Requested-With": "XMLHttpRequest"})
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"

    # Request /auth/me now returns 401
    after_res = client.get("/auth/me")
    assert after_res.status_code == 401


def test_07_password_change_lifecycle(client, db_session):
    """Validates user password change, strength requirements, and old password invalidation."""
    # Create test user for password change
    uname = f"pw_change_{uuid4().hex[:8]}"
    init_pwd = "initial_pass_2026"
    st = Staff(
        tenant_id="center-seba-01",
        username=uname,
        display_name="PW Changer",
        role="RECEPTIONIST",
        active=True,
        password_hash=hash_password(init_pwd),
    )
    db_session.add(st)
    db_session.commit()
    db_session.refresh(st)
    db_session.add(StaffRole(staff_id=st.id, role="RECEPTIONIST", is_primary=True, created_at=utc_now()))
    db_session.commit()

    # Log in
    client.post("/auth/login", json={"username": uname, "password": init_pwd})

    # Short password (< 8 chars) rejected with 400
    r_short = client.post(
        "/auth/change-password",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json={"old_password": init_pwd, "new_password": "short"},
    )
    assert r_short.status_code in [400, 422]

    # Password equal to username rejected with 400
    r_same = client.post(
        "/auth/change-password",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json={"old_password": init_pwd, "new_password": uname},
    )
    assert r_same.status_code == 400

    # Valid change
    new_pwd = "new_updated_pass_2026"
    r_valid = client.post(
        "/auth/change-password",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json={"old_password": init_pwd, "new_password": new_pwd},
    )
    assert r_valid.status_code == 200

    # Old password no longer works
    r_old_login = client.post("/auth/login", json={"username": uname, "password": init_pwd})
    assert r_old_login.status_code == 401

    # New password works
    r_new_login = client.post("/auth/login", json={"username": uname, "password": new_pwd})
    assert r_new_login.status_code == 200


def test_08_acting_role_switch(client):
    """Staff with multiple roles can switch active role, but cannot switch to unheld roles."""
    # Tariq holds ADMIN and OWNER
    login_res = client.post(
        "/auth/login",
        json={"username": "admin_tariq", "password": TEST_PASSWORD_DEFAULT, "role": "ADMIN"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["acting_role"] == "ADMIN"
    assert login_res.json()["home_route"] == "/"

    # Switch to OWNER
    switch_res = client.post(
        "/auth/acting-role",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json={"role": "OWNER"},
    )
    assert switch_res.status_code == 200
    assert switch_res.json()["acting_role"] == "OWNER"

    # Verify /auth/me reflects OWNER
    me = client.get("/auth/me")
    assert me.json()["acting_role"] == "OWNER"

    # Attempt to switch to LAB_TECH (not held) -> 403 Forbidden
    bad_switch = client.post(
        "/auth/acting-role",
        headers={"X-Requested-With": "XMLHttpRequest"},
        json={"role": "LAB_TECH"},
    )
    assert bad_switch.status_code == 403


def test_09_role_guards_enforced_with_real_sessions(client):
    """Validates that existing role guards remain fully operational with session authentication."""
    # Receptionist close business day -> 403
    close_rec = client.post(
        "/business-day/close",
        headers=RECEPTIONIST_HEADERS,
        json={"notes": "Unauthorized close by receptionist"},
    )
    assert close_rec.status_code == 403

    # Receptionist accessing lab worklist -> 403
    worklist_rec = client.get(
        "/worklist",
        headers=RECEPTIONIST_HEADERS,
    )
    assert worklist_rec.status_code == 403

    # Lab Tech accessing lab worklist -> 200
    worklist_tech = client.get(
        "/worklist",
        headers=TECH_KAMAL_HEADERS,
    )
    assert worklist_tech.status_code == 200

    # Admin close business day: Admin has permission (does NOT return 403)
    close_adm = client.post(
        "/business-day/close",
        headers=ADMIN_HEADERS,
        json={"notes": "Authorized close by admin"},
    )
    assert close_adm.status_code in [200, 400]
    assert close_adm.status_code != 403


def test_10_technician_payloads_free_of_financial_fields(client):
    """Technicians viewing worklist tasks receive clinical data only (no prices, dues, commissions)."""
    res = client.get("/worklist", headers=TECH_KAMAL_HEADERS)
    assert res.status_code == 200
    tasks = res.json()
    if tasks:
        for t in tasks:
            assert "price" not in t
            assert "unit_price" not in t
            assert "due_amount" not in t
            assert "paid_amount" not in t
            assert "commission_amount" not in t
            assert "cost_price" not in t
