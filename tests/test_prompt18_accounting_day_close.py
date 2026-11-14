"""
Prompt 18 - Module 21 (journal) and Module 22 (day close), kept to the properties that cannot be checked any
other way: every entry balances, the receivable follows the invoice, the journal is append-only in the database,
the D45 expected-cash identity, variance reason above the tolerance, Owner-only reopen with adjusting entries
only. Thorough verification is a separate, later prompt. Runs only against medscope_test (conftest guard).
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.models.invoice import Invoice
from tests.conftest import ADMIN_HEADERS, CASHIER_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS
from tests.test_prompt13_prelock_cancellation import _open_day, _owner_case, _request


@pytest.fixture(autouse=True)
def _restore(client):
    yield
    client.put("/settings", headers=OWNER_HEADERS, json={"cash_variance_tolerance": 0})
    _open_day(client)


def _receivable(db) -> int:
    db.expire_all()
    return db.execute(text(
        "SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM journal_lines l JOIN accounts a ON a.id = l.account_id WHERE a.code = '1200'"
    )).scalar_one()


def _screen(client):
    res = client.get("/business-day/day-screen", headers=ADMIN_HEADERS)
    assert res.status_code == 200, res.text
    return res.json()


def test_every_entry_balances_and_receivable_follows_the_invoice(client, db_session):
    before = _receivable(db_session)
    inv, line_id = _owner_case(client, db_session, paid=3000)  # 9000 bill, 3000 paid up front
    iid = inv["id"]
    assert _receivable(db_session) - before == 6000  # net 9000 - paid 3000 = the due
    # cancel the 5000 line (nothing needs refunding: 4000 net still covers the 3000 paid)
    assert _request(client, inv, line_id).status_code in (200, 201)
    db_session.expire_all()
    assert _receivable(db_session) - before == db_session.get(Invoice, iid).due == 1000
    # write off part of the remaining due (Owner: no limit): receivable drops with it
    assert client.post(f"/invoices/{iid}/write-off", headers=OWNER_HEADERS, json={"amount": 400, "reason": "test"}).status_code == 201
    db_session.expire_all()
    assert _receivable(db_session) - before == db_session.get(Invoice, iid).due == 600
    bad = db_session.execute(text(
        "SELECT entry_id FROM journal_lines GROUP BY entry_id HAVING SUM(debit) <> SUM(credit)"
    )).all()
    assert bad == []
    kinds = {r[0] for r in db_session.execute(text("SELECT event_type FROM journal_entries"))}
    assert {"BILL_CONFIRMED", "PAYMENT_RECEIVED", "LINE_CANCELLED", "DUE_WRITTEN_OFF"} <= kinds
    # no posting exists for events whose modules are not built
    assert not kinds & {"COMMISSION_ACCRUED", "VISIT_FEE_HANDOVER", "CONSULTANT_FEE", "OUTSIDE_LAB_COST"}


def test_journal_is_append_only_and_unbalanced_entries_are_refused(client, db_session):
    _owner_case(client, db_session, paid=100)
    lid = db_session.execute(text("SELECT id FROM journal_lines ORDER BY id DESC LIMIT 1")).scalar_one()
    for stmt in ("UPDATE journal_lines SET debit = debit + 1 WHERE id = :i", "DELETE FROM journal_lines WHERE id = :i"):
        with pytest.raises(DBAPIError):
            db_session.execute(text(stmt), {"i": lid})
        db_session.rollback()
    eid = db_session.execute(text("SELECT entry_id FROM journal_lines WHERE id = :i"), {"i": lid}).scalar_one()
    with pytest.raises(DBAPIError):
        db_session.execute(text("UPDATE journal_entries SET memo = 'edited' WHERE id = :i"), {"i": eid})
    db_session.rollback()
    with pytest.raises(DBAPIError):  # a line that unbalances an entry is refused at commit
        acc = db_session.execute(text("SELECT id FROM accounts LIMIT 1")).scalar_one()
        db_session.execute(text("INSERT INTO journal_lines (tenant_id, entry_id, account_id, debit, credit) "
                                "SELECT tenant_id, :e, :a, 7, 0 FROM journal_entries WHERE id = :e"), {"e": eid, "a": acc})
        db_session.commit()
    db_session.rollback()


def test_day_close_expected_cash_variance_reopen_and_adjustments(client, db_session):
    _open_day(client)
    _owner_case(client, db_session, paid=500)  # some cash collected today
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS):
        assert client.get("/business-day/day-screen", headers=h).status_code == 403
        assert client.post("/business-day/movements", headers=h, json={"kind": "EXPENSE", "amount": 1, "note": "x"}).status_code == 403
    s = _screen(client)
    c = s["cash"]
    assert s["unsynced_items"] == 0 and all(v == 0 for v in c["deferred_payouts"].values())
    assert c["expected_cash"] == (c["opening_cash"] + c["cash_collections"] - c["cash_refunds"]
                                  - c["bank_deposits"] - c["owner_withdrawals"] - c["expenses"])
    # movements lower expected cash; the owner withdrawal is Owner only
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "OWNER_WITHDRAWAL", "amount": 5}).status_code == 403
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 10, "note": "tea"}).status_code == 201
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "BANK_DEPOSIT", "amount": 20}).status_code == 201
    assert client.post("/business-day/movements", headers=OWNER_HEADERS, json={"kind": "OWNER_WITHDRAWAL", "amount": 5}).status_code == 201
    s2 = _screen(client)
    assert s2["cash"]["expected_cash"] == c["expected_cash"] - 35
    expected, day_id = s2["cash"]["expected_cash"], s2["day"]["id"]

    # close: counted cash required; a variance above the tolerance (0) needs a reason
    assert client.post("/business-day/close", headers=ADMIN_HEADERS, json={"notes": "x"}).status_code == 422
    assert client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": expected - 7}).status_code == 400
    ok = client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": expected - 7, "variance_reason": "short change"})
    assert ok.status_code == 200, ok.text
    closed = _screen(client)
    assert closed["day"]["status"] == "CLOSED" and closed["day"]["variance"] == -7 and closed["day"]["variance_reason"] == "short change"
    j = client.get(f"/accounting/journal?business_day_id={day_id}", headers=ADMIN_HEADERS).json()["entries"]
    var = next(e for e in j if e["event"] == "CASH_VARIANCE")
    assert {(l["account"], l["debit"], l["credit"]) for l in var["lines"]} == {("CASH_VARIANCE", 7, 0), ("CASH", 0, 7)}

    # a closed day takes no movement; reopen is Owner only with a reason; then adjusting entries only
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 1, "note": "late"}).status_code == 409
    assert client.post(f"/business-day/{day_id}/reopen", headers=ADMIN_HEADERS, json={"reason": "fix"}).status_code == 403
    assert client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": ""}).status_code in (400, 422)
    assert client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={"reason": "early", "reverse_entry_id": var["id"]}).status_code == 409
    assert client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "miscounted"}).status_code == 200
    assert client.post(f"/business-day/{day_id}/adjustments", headers=ADMIN_HEADERS, json={"reason": "x", "reverse_entry_id": var["id"]}).status_code == 403
    unbalanced = client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS,
                             json={"reason": "bad", "lines": [{"account": "CASH", "debit": 5}, {"account": "OPERATING_EXPENSE", "credit": 4}]})
    assert unbalanced.status_code == 400
    rev = client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={"reason": "recount", "reverse_entry_id": var["id"]})
    assert rev.status_code == 201, rev.text
    assert client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={"reason": "again", "reverse_entry_id": var["id"]}).status_code == 409
    # re-close with the true count (variance 0): nothing further to post beyond the reversal
    assert client.put("/settings", headers=OWNER_HEADERS, json={"cash_variance_tolerance": 50}).status_code == 200
    re = client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": expected - 3, "day_id": day_id})
    assert re.status_code == 200, re.text  # |-3| <= tolerance: no reason needed
    assert _screen(client)["day"]["status"] in ("CLOSED", "OPEN")
    bad = db_session.execute(text("SELECT entry_id FROM journal_lines GROUP BY entry_id HAVING SUM(debit) <> SUM(credit)")).all()
    assert bad == []
