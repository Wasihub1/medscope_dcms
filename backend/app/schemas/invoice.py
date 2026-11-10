from datetime import datetime
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema
from backend.app.schemas.patient import PatientResponse


class InvoiceLineCreate(BaseModel):
    test_id: int
    discount_type: str = Field(default="NONE", description="NONE, PERCENTAGE, AMOUNT, PERCENT, FIXED")
    discount_value: int = Field(default=0, ge=0)
    urgent: bool = Field(default=False)
    is_urgent: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_line(cls, data):
        if isinstance(data, dict):
            if "is_urgent" in data and "urgent" not in data:
                data["urgent"] = bool(data["is_urgent"])
            dt = data.get("discount_type", "NONE")
            if dt == "PERCENT":
                data["discount_type"] = "PERCENTAGE"
            elif dt == "FIXED":
                data["discount_type"] = "AMOUNT"
        return data


class InvoiceConfirmRequest(BaseModel):
    patient_id: int
    prescribed_by_id: Optional[int] = None
    referrer_id: Optional[int] = None
    urgent: bool = Field(default=False)
    
    # Selected test lines
    lines: List[InvoiceLineCreate] = Field(..., min_length=1)
    
    # Bill-level discount (if applied instead of line-level)
    bill_discount_type: str = Field(default="NONE", description="NONE, PERCENTAGE, AMOUNT")
    bill_discount_value: int = Field(default=0, ge=0)
    master_discount_type: Optional[str] = None
    master_discount_value: Optional[int] = None

    # Initial payment
    initial_payment_amount: int = Field(default=0, ge=0)
    initial_payment_method: str = Field(default="CASH", description="CASH, BKASH, NAGAD, BANK_TRANSFER, POS_CARD")
    initial_payment_reference: Optional[str] = Field(default=None)
    cash_tendered: Optional[int] = Field(default=None, ge=0)
    initial_payment: Optional[Union[dict, int, float]] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None

    # Visit demographics snapshot
    age_value: int = Field(default=30, ge=0)
    age_unit: str = Field(default="years")
    gender: str = Field(default="Male")

    @model_validator(mode="before")
    @classmethod
    def normalize_confirm_req(cls, data):
        if isinstance(data, dict):
            # Master discount aliases
            mdt = data.get("master_discount_type")
            if mdt:
                if mdt in ("PERCENT", "PERCENTAGE"):
                    data["bill_discount_type"] = "PERCENTAGE"
                elif mdt in ("FIXED", "AMOUNT"):
                    data["bill_discount_type"] = "AMOUNT"
                else:
                    data["bill_discount_type"] = "NONE"
            mdv = data.get("master_discount_value")
            if mdv is not None and "bill_discount_value" not in data:
                data["bill_discount_value"] = int(mdv)

            # Initial payment dict or int alias
            init_pmt = data.get("initial_payment")
            if isinstance(init_pmt, dict):
                data["initial_payment_amount"] = int(init_pmt.get("amount", 0))
                data["initial_payment_method"] = str(init_pmt.get("channel", "CASH")).upper()
                data["initial_payment_reference"] = init_pmt.get("reference_no")
            elif isinstance(init_pmt, (int, float)):
                data["initial_payment_amount"] = int(init_pmt)

            if "payment_method" in data and "initial_payment_method" not in data:
                data["initial_payment_method"] = str(data["payment_method"]).upper()
        return data

    @model_validator(mode="after")
    def validate_no_duplicate_lines(self):
        test_ids = [line.test_id for line in self.lines]
        if len(test_ids) != len(set(test_ids)):
            raise ValueError("Duplicate investigations cannot be added to the same invoice.")
        return self


class InvoiceLineResponse(BaseSchema):
    id: int
    test_id: int
    test_code_snapshot: str
    test_name_snapshot: str
    department_snapshot: str
    unit_price_snapshot: int
    discount_type: str
    discount_value: int
    discount_amount: int
    net_price: int
    urgent: bool
    status: str
    created_at: datetime
    sample_status: Optional[str] = None
    report_status: Optional[str] = None
    sample_collected: bool = False
    is_locked: bool = False
    locked_reason: Optional[str] = None
    outcome: Optional[str] = None
    d15_refund_status: Optional[str] = None
    d15_refund_reason: Optional[str] = None
    net_amount: Optional[int] = None

    # Aliases for direct client and print preview consumption
    test_name: Optional[str] = None
    test_code: Optional[str] = None
    department: Optional[str] = None
    price: Optional[int] = None
    is_urgent: Optional[bool] = None

    @model_validator(mode="after")
    def populate_line_aliases(self):
        if self.net_amount is None:
            self.net_amount = self.net_price
        if self.test_name is None:
            self.test_name = self.test_name_snapshot
        if self.test_code is None:
            self.test_code = self.test_code_snapshot
        if self.department is None:
            self.department = self.department_snapshot
        if self.price is None:
            self.price = self.unit_price_snapshot
        if self.is_urgent is None:
            self.is_urgent = self.urgent
        if not self.sample_collected and self.sample_status == "COLLECTED":
            self.sample_collected = True
        return self


class InvoiceResponse(BaseSchema):
    id: int
    invoice_no: str
    temp_invoice_id: Optional[str] = None
    patient_id: int
    visit_id: int
    prescribed_by_id: Optional[int] = None
    prescribed_by_name: Optional[str] = None
    referrer_id: Optional[int] = None
    referrer_name: Optional[str] = None
    status: str
    payment_status: str
    refund_status: Optional[str] = "NO_REFUND"
    gross: int
    discount: int
    net: int
    paid: int
    due: int
    refund_due: int
    urgent: bool
    created_at: datetime
    created_by_name: Optional[str] = None
    patient_name: Optional[str] = None
    patient_code: Optional[str] = None
    patient_phone: Optional[str] = None
    invoice_number: Optional[str] = None
    patient_mrn: Optional[str] = None
    gross_amount: Optional[int] = None
    discount_amount: Optional[int] = None
    net_amount: Optional[int] = None
    paid_amount: Optional[int] = None
    due_amount: Optional[int] = None

    @model_validator(mode="after")
    def populate_invoice_aliases(self):
        if not self.invoice_number:
            self.invoice_number = self.invoice_no
        if not self.patient_mrn:
            self.patient_mrn = self.patient_code
        if self.gross_amount is None:
            self.gross_amount = self.gross
        if self.discount_amount is None:
            self.discount_amount = self.discount
        if self.net_amount is None:
            self.net_amount = self.net
        if self.paid_amount is None:
            self.paid_amount = self.paid
        if self.due_amount is None:
            self.due_amount = self.due
        return self


class InvoiceDetailResponse(InvoiceResponse):
    patient: PatientResponse
    lines: List[InvoiceLineResponse]
    payments: List["PaymentResponse"]
    can_request_refund: bool  # True if at least one line is uncollected
    is_duplicate_reprint: bool = False
    reprint_count: Optional[int] = 1
    reprint_timestamp: Optional[datetime] = None
    reprinted_by_name: Optional[str] = None
    refund_requests: List[Any] = []


from backend.app.schemas.payment import PaymentResponse
InvoiceDetailResponse.model_rebuild()

