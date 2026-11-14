from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: int = Field(..., gt=0, description="Payment amount in whole Taka")
    method: str = Field(default="CASH", description="CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER")
    reference: Optional[str] = Field(default=None, description="Transaction ID or voucher reference")
    channel_detail: Optional[str] = Field(default=None, max_length=100, description="Channel name, required when method is OTHER")
    cash_tendered: Optional[int] = Field(default=None, ge=0, description="Amount handed by patient for change calculation")


class DueSettlementRequest(BaseModel):
    amount: int = Field(..., gt=0)
    method: str = Field(default="CASH", description="CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER")
    reference: Optional[str] = None
    channel_detail: Optional[str] = Field(default=None, max_length=100, description="Channel name, required when method is OTHER")
    cash_tendered: Optional[int] = None


class PaymentResponse(BaseSchema):
    id: int
    invoice_id: int
    amount: int
    method: str
    reference: Optional[str] = None
    channel_detail: Optional[str] = None  # Prompt 10E: name typed for OTHER
    change_amount: int
    received_at: datetime
    received_by_id: int
    received_by_name: Optional[str] = None


class DueInvoiceSummary(BaseSchema):
    invoice_id: int
    invoice_no: str
    patient_id: int
    patient_code: str
    patient_name: str
    patient_phone: str
    created_at: datetime
    net: int
    paid: int
    due: int
    payment_status: str
    # Prompt 17 (Module 18): derived age of the bill and the amount already written off
    age_days: int = 0
    age_bucket: str = "0-7"
    written_off: int = 0

    # UI aliases
    id: Optional[str] = None
    invoice_number: Optional[str] = None
    patient_mrn: Optional[str] = None
    net_amount: Optional[int] = None
    paid_amount: Optional[int] = None
    due_amount: Optional[int] = None
    gross_amount: Optional[int] = None
    lines_count: Optional[int] = 0

    @model_validator(mode="after")
    def populate_aliases(self):
        if not self.id:
            self.id = str(self.invoice_id)
        if not self.invoice_number:
            self.invoice_number = self.invoice_no
        if not self.patient_mrn:
            self.patient_mrn = self.patient_code
        if self.net_amount is None:
            self.net_amount = self.net
        if self.paid_amount is None:
            self.paid_amount = self.paid
        if self.due_amount is None:
            self.due_amount = self.due
        if self.gross_amount is None:
            self.gross_amount = self.net
        return self

