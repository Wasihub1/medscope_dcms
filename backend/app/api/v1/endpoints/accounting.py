"""Prompt 18 (Module 21): the four V1 accounting reports and the journal view. Read-only. `format=csv` returns an
Excel-friendly CSV of the same rows."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor
from backend.app.services import accounting_report_service as rep

router = APIRouter()
_perm = require_permission("accounting.view")


def _csv(name: str, rows, columns) -> Response:
    return Response(rep.to_csv(rows, columns), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


@router.get("/cash-book", summary="Cash book: every movement on one money account with a running balance")
def cash_book(date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"),
              channel: str = "CASH", format: str = "json", actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    res = rep.cash_book(db, actor.tenant_id, date_from, date_to, channel)
    return _csv("cash-book", res["rows"], ["date", "entry_id", "event", "memo", "money_in", "money_out", "balance"]) if format == "csv" else res


@router.get("/income-expense", summary="Daily income and expense (billing basis)")
def income_expense(date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"),
                   format: str = "json", actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    res = rep.income_expense(db, actor.tenant_id, date_from, date_to)
    cols = ["date", "test_revenue", "urgent_fee_revenue", "discount_given", "income", "operating_expense", "bad_debt", "cash_variance", "expense", "net"]
    return _csv("income-expense", res["rows"], cols) if format == "csv" else res


@router.get("/dues", summary="Dues report (reuses the Prompt 17 dues data), filtered by bill date")
def dues(date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"),
         format: str = "json", actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    res = rep.dues_report(db, actor.tenant_id, date_from, date_to)
    cols = ["bill_no", "bill_date", "patient_code", "patient", "phone", "net", "paid", "written_off", "due", "age_days", "age_bucket"]
    return _csv("dues", res["rows"], cols) if format == "csv" else res


@router.get("/cost-by-referrer", summary="Cost by referrer (0 until commission, Module 19, is built)")
def cost_by_referrer(date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"),
                     format: str = "json", actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    res = rep.cost_by_referrer(db, actor.tenant_id, date_from, date_to)
    return _csv("cost-by-referrer", res["rows"], ["referrer", "bills", "net_billed", "cost"]) if format == "csv" else res


@router.get("/journal", summary="Journal entries with their lines (read only, newest first)")
def journal(date_from: Optional[date] = Query(None, alias="from"), date_to: Optional[date] = Query(None, alias="to"),
            business_day_id: Optional[int] = None, limit: int = Query(200, ge=1, le=1000),
            actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    return rep.journal(db, actor.tenant_id, date_from, date_to, business_day_id, limit)
