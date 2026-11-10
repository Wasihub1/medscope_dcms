from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, model_validator
from backend.app.schemas.common import BaseSchema
from backend.app.schemas.invoice import InvoiceResponse
from backend.app.schemas.business_day import BusinessDayStatusResponse


class BentoTileStats(BaseModel):
    today_patients_count: int
    today_invoices_count: int
    today_payments_collected: int  # Whole-Taka integer
    total_outstanding_dues: int    # Whole-Taka integer
    unassigned_tests_count: int
    reports_ready_for_delivery: int
    reports_held_due_to_balance: int
    pending_refund_requests_count: int


class ReceptionistDashboardResponse(BaseModel):
    stats: BentoTileStats
    business_day: BusinessDayStatusResponse
    recent_invoices: List[InvoiceResponse]
    active_unassigned_summary: List[dict]
    held_reports_summary: List[dict]

    # Root-level convenience aliases
    today_patients_count: Optional[int] = None
    today_invoices_count: Optional[int] = None
    today_paid_amount: Optional[int] = None
    today_net_amount: Optional[int] = None
    today_due_amount: Optional[int] = None
    active_patients_today: Optional[int] = None
    unassigned_tests_count: Optional[int] = None
    ready_reports_count: Optional[int] = None
    held_reports_count: Optional[int] = None
    pending_refunds_count: Optional[int] = None

    @model_validator(mode="after")
    def populate_root_aliases(self):
        s = self.stats
        if self.today_patients_count is None:
            self.today_patients_count = s.today_patients_count
        if self.active_patients_today is None:
            self.active_patients_today = s.today_patients_count
        if self.today_invoices_count is None:
            self.today_invoices_count = s.today_invoices_count
        if self.today_paid_amount is None:
            self.today_paid_amount = s.today_payments_collected
        if self.today_due_amount is None:
            self.today_due_amount = s.total_outstanding_dues
        if self.today_net_amount is None:
            self.today_net_amount = s.today_payments_collected + s.total_outstanding_dues
        if self.unassigned_tests_count is None:
            self.unassigned_tests_count = s.unassigned_tests_count
        if self.ready_reports_count is None:
            self.ready_reports_count = s.reports_ready_for_delivery
        if self.held_reports_count is None:
            self.held_reports_count = s.reports_held_due_to_balance
        if self.pending_refunds_count is None:
            self.pending_refunds_count = s.pending_refund_requests_count
        return self

