"""
Prompt 18B - regression tests for the four verification findings.
1. No payment / bill confirmation / refund payout while the day is CLOSED or REOPENED (409) or never opened (400).
2. (docs only) bank deposit is Admin or Owner; owner withdrawal Owner only.
3. A new day cannot be opened while the previous day is OPEN or REOPENED.
4. Adjusting entries touching Cash on a reopened day flow into expected cash.
Runs only against medscope_test (conftest guard).
"""
import pytest

from tests.conftest import ADMIN_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS
from tests.test_prompt13_prelock_cancellation import _open_day, _owner_case


def _screen(client):
    return client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()


def _close(client, headers=ADMIN_HEADERS, **extra):
    exp = _screen(client)["cash"]["expected_cash"]
    return client.post("/business-day/close", headers=headers, json={"counted_cash": exp, **extra})


def _body(inv):
    return {"patient_id": inv["patient_id"], "age_value": 30, "gender": "Male",
            "lines": [{"test_id": l["test_id"]} for l in inv["lines"]],
            "initial_payment_amount": 10, "initial_payment_method": "CASH"}


@pytest.fixture(autouse=True)
def _restore(client):
    yield
    st = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json().get("day")
    if st and st["status"] == "REOPENED":
        client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": _screen(client)["cash"]["expected_cash"], "variance_reason": "cleanup", "day_id": st["id"]})
    _open_day(client)


def test_finding1_money_is_refused_on_a_closed_or_reopened_day(client, db_session):
    inv, _ = _owner_case(client, db_session, paid=100)
    iid, body = inv["id"], _body(inv)
    day_id = _screen(client)["day"]["id"]
    # normal payment on an OPEN day still works
    assert client.post(f"/invoices/{iid}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 5, "method": "CASH"}).status_code == 201
    assert _close(client, variance_reason="test").status_code == 200
    def refused():
        assert client.post(f"/invoices/{iid}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 5, "method": "CASH"}).status_code == 409
        assert client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=body).status_code == 409
    refused()  # CLOSED
    assert client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "check"}).status_code == 200
    refused()  # REOPENED
    # nothing was written without a day
    from sqlalchemy import text
    db_session.expire_all()
    assert db_session.execute(text("SELECT count(*) FROM payments WHERE business_day_id IS NULL AND invoice_id = :i"), {"i": iid}).scalar_one() == 0
    assert _close(client, headers=OWNER_HEADERS, variance_reason="test", day_id=day_id).status_code == 200


def test_finding3_new_day_blocked_while_open_or_reopened(client, db_session):
    _open_day(client)
    day_id = _screen(client)["day"]["id"]
    assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 400  # OPEN (unchanged)
    exp = _screen(client)["cash"]["expected_cash"]
    assert client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp, "variance_reason": "t"}).status_code == 200
    assert client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "check"}).status_code == 200
    blocked = client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0})
    assert blocked.status_code == 400 and "REOPENED" in blocked.json()["detail"]
    exp = _screen(client)["cash"]["expected_cash"]
    assert client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": exp, "variance_reason": "t", "day_id": day_id}).status_code == 200
    assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201


def test_finding4_adjusting_cash_entry_flows_into_expected_cash(client, db_session):
    _owner_case(client, db_session, paid=500)  # cash in the drawer, so the adjustment cannot go negative
    day_id = _screen(client)["day"]["id"]
    exp = _screen(client)["cash"]["expected_cash"]
    assert client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp, "variance_reason": "t"}).status_code == 200
    assert client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "fix cash"}).status_code == 200
    before = _screen(client)["cash"]
    adj = client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={
        "reason": "misposted", "lines": [{"account": "CASH", "credit": 7}, {"account": "OPERATING_EXPENSE", "debit": 7}]})
    assert adj.status_code == 201, adj.text
    after = _screen(client)["cash"]
    assert after["adjusting_entries"] == before["adjusting_entries"] - 7
    assert after["expected_cash"] == before["expected_cash"] - 7
    # counting the corrected figure now gives no variance
    res = client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": after["expected_cash"], "day_id": day_id})
    assert res.status_code == 200, res.text
    assert _screen(client)["day"]["variance"] == 0
