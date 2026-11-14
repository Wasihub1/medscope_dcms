"""
Prompt 13B Item 2 - the Business Day open/closed state is the same for every role.

Root cause found: the header only fetched the day when the user held `business_day.view`, and Lab Tech does
not (and must not: the full status carries cash and channel figures), so the header defaulted to "Business
Day Closed" for Lab Tech while the day was open. The fix is a money-free `GET /business-day/state` that every
authenticated role can read. Runs only against medscope_test (conftest guard).
"""
from sqlalchemy import select

from backend.app.models.business_day import BusinessDay
from tests.conftest import (
    ADMIN_HEADERS, CASHIER_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS,
)

ROLES = {
    "receptionist": RECEPTIONIST_HEADERS, "cashier": CASHIER_HEADERS, "admin": ADMIN_HEADERS,
    "owner": OWNER_HEADERS, "lab_tech": TECH_KAMAL_HEADERS,
}
MONEY_WORDS = ("balance", "float", "received", "collection", "refund", "channel", "amount", "cash")


def _states(client):
    out = {}
    for name, h in ROLES.items():
        res = client.get("/business-day/state", headers=h)
        assert res.status_code == 200, (name, res.text)
        out[name] = res.json()
    return out


def _ensure_open(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st["is_open"]:
        assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201


def test_open_day_reads_the_same_for_every_role_including_lab_tech(client):
    _ensure_open(client)
    states = _states(client)
    assert all(s["is_open"] is True for s in states.values())
    assert len({(s["is_open"], s["day_number"], s["business_date"]) for s in states.values()}) == 1
    full = client.get("/business-day/status", headers=ADMIN_HEADERS).json()
    assert states["lab_tech"]["day_number"] == full["day_number"]  # same source as the full status


def test_closed_day_reads_closed_for_every_role(client, db_session):
    _ensure_open(client)
    db_session.expire_all()
    day = db_session.execute(select(BusinessDay).where(BusinessDay.status == "OPEN")).scalars().first()
    day_id = day.id
    day.status = "CLOSED"
    db_session.commit()
    try:
        states = _states(client)
        assert all(s["is_open"] is False for s in states.values())
        assert all(s["day_number"] is None for s in states.values())
    finally:
        db_session.expire_all()
        db_session.get(BusinessDay, day_id).status = "OPEN"
        db_session.commit()
    assert all(s["is_open"] for s in _states(client).values())


def test_lab_tech_state_has_no_money_and_the_full_status_stays_forbidden(client):
    _ensure_open(client)
    body = client.get("/business-day/state", headers=TECH_KAMAL_HEADERS).json()
    assert set(body) == {"is_open", "day_number", "business_date"}
    assert not any(w in k for k in body for w in MONEY_WORDS)
    # the money-bearing endpoints are still closed to Lab Tech (M11.3)
    assert client.get("/business-day/status", headers=TECH_KAMAL_HEADERS).status_code == 403
    assert client.get("/business-day/current", headers=TECH_KAMAL_HEADERS).status_code == 403


def test_state_requires_authentication(client):
    assert client.get("/business-day/state", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401
