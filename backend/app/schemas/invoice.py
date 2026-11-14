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


# Prompt 10E Part 3: age is a whole number; infants are recorded in months or days.
# The limits are all equivalent to 130 years.
AGE_UNIT_LIMITS = {"years": 130, "months": 130 * 12, "days": 130 * 365}
GENDER_VALUES = ("Male", "Female", "Other")


def normalize_gender(value: Optional[str]) -> str:
    v = (value or "").strip().lower()
    for g in GENDER_VALUES:
        if v == g.lower() or (len(v) == 1 and v == g[0].lower()):
            return g
    raise ValueError(f"Gender must be one of: {', '.join(GENDER_VALUES)}.")


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
    initial_payment_method: str = Field(default="CASH", description="CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER")
    initial_payment_reference: Optional[str] = Field(default=None)
    # Prompt 10E Part 4: name of the channel when initial_payment_method is OTHER (required then)
    initial_payment_channel_detail: Optional[str] = Field(default=None, max_length=100)
    cash_tendered: Optional[int] = Field(default=None, ge=0)
    initial_payment: Optional[Union[dict, int, float]] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None

    # Visit demographics snapshot (Prompt 10E Part 3): no silent defaults. A draft may omit
    # them; Finalize requires both age and gender (enforced in the service).
    age_value: Optional[int] = Field(default=None, ge=0)
    age_unit: str = Field(default="years", description="years, months, days")
    gender: Optional[str] = Field(default=None, description="Male, Female, Other")

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
                if init_pmt.get("channel_detail") is not None:
                    data["initial_payment_channel_detail"] = init_pmt.get("channel_detail")
            elif isinstance(init_pmt, (int, float)):
                data["initial_payment_amount"] = int(init_pmt)

            if "payment_method" in data and "initial_payment_method" not in data:
                data["initial_payment_method"] = str(data["payment_method"]).upper()

            # Age aliases (age_years / age_months) used by the patient form
            if data.get("age_value") in (None, "") and data.get("age_years") not in (None, ""):
                data["age_value"] = int(data["age_years"])
                data["age_unit"] = "years"
            elif data.get("age_value") in (None, "") and data.get("age_months") not in (None, ""):
                data["age_value"] = int(data["age_months"])
                data["age_unit"] = "months"
            if data.get("age_value") == "":
                data["age_value"] = None
            if data.get("gender") == "":
                data["gender"] = None
        return data

    @model_validator(mode="after")
    def validate_demographics(self):
        unit = (self.age_unit or "years").strip().lower()
        if unit not in AGE_UNIT_LIMITS:
            raise ValueError(f"age_unit must be one of: {', '.join(AGE_UNIT_LIMITS)}.")
        self.age_unit = unit
        if self.age_value is not None and not (0 <= self.age_value <= AGE_UNIT_LIMITS[unit]):
            raise ValueError(f"Age must be a whole number between 0 and {AGE_UNIT_LIMITS[unit]} {unit}.")
        if self.gender is not None:
            self.gender = normalize_gender(self.gender)
        return self

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
    # Prompt 13: explicit cancellation state, the label to show (precedence over sample status) and
    # whether "Request Cancellation" may be offered for this line right now.
    cancellation_state: str = "NONE"
    display_status: Optional[str] = None
    can_request_cancellation: bool = False
    net_amount: Optional[int] = None
    # Prompt 10E: urgent fee charged for this line (informational; the fee belongs to the
    # invoice and is never refunded on cancellation) and the lab room of its test order
    line_urgent_fee: int = 0
    lab_section: Optional[str] = None

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
    visit_id: Optional[int] = None  # None while the invoice is a DRAFT (Prompt 10D)
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
    is_draft: bool = False
    finalized_at: Optional[datetime] = None
    # Prompt 10E Part 5: urgent fee computed by the backend and included in net
    urgent_fee: int = 0

    @model_validator(mode="after")
    def populate_invoice_aliases(self):
        self.is_draft = (self.status == "DRAFT")
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
    # Prompt 10D: saved draft form (only meaningful while status == DRAFT) for reopen/edit
    draft_payload: Optional[dict] = None
    # Prompt 10E Part 3: visit snapshot (None while DRAFT)
    age_value: Optional[int] = None
    age_unit: Optional[str] = None
    visit_gender: Optional[str] = None


from backend.app.schemas.payment import PaymentResponse
InvoiceDetailResponse.model_rebuild()

