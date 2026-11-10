from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.app.schemas.common import BaseSchema


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Patient name in English or Bangla")
    phone: str = Field(..., min_length=6, max_length=20, description="Contact phone number")
    address: str = Field(default="Dhaka", min_length=2, max_length=300, description="Address with at least one meaningful word")
    gender: str = Field(default="Male", description="Male, Female, Other")
    
    # Visit demographics
    age_value: int = Field(default=0, ge=0, le=130)
    age_unit: str = Field(default="years", description="years, months, days")
    alternate_phone: Optional[str] = None
    blood_group: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_patient_input(cls, data):
        if isinstance(data, dict):
            if "full_name" in data and "name" not in data:
                data["name"] = data["full_name"]
            if not data.get("address"):
                data["address"] = "Dhaka, Bangladesh"
            if "age_years" in data and ("age_value" not in data or not data.get("age_value")):
                data["age_value"] = int(data["age_years"] or 0)
                data["age_unit"] = "years"
            elif "age_months" in data and ("age_value" not in data or not data.get("age_value")):
                data["age_value"] = int(data["age_months"] or 0)
                data["age_unit"] = "months"
        return data

    @field_validator("address")
    @classmethod
    def validate_address_meaningful(cls, v: str) -> str:
        words = (v or "").strip().split()
        if not words or len(words[0]) < 2:
            return "Dhaka, Bangladesh"
        return v.strip()


class PatientResponse(BaseSchema):
    id: int
    patient_code: str
    temp_id: Optional[str] = None
    name: str
    phone: str
    phone_last4: str
    address: str
    gender: str
    created_at: datetime
    full_name: Optional[str] = None
    mrn: Optional[str] = None

    @model_validator(mode="after")
    def populate_aliases(self):
        if not self.full_name:
            self.full_name = self.name
        if not self.mrn:
            self.mrn = self.patient_code
        return self


class PatientHistoryVisitItem(BaseModel):
    visit_id: int
    visit_number: str
    visit_date: datetime
    age_summary: str
    gender: str


class PatientHistoryInvoiceItem(BaseModel):
    invoice_id: int
    invoice_no: str
    created_at: datetime
    gross: int
    discount: int
    net: int
    paid: int
    due: int
    status: str
    payment_status: str
    tests_summary: List[str]
    sample_status: str
    report_status: str
    report_delivery_status: str


class PatientHistoryPaymentItem(BaseModel):
    id: int
    invoice_id: int
    invoice_no: str
    amount: int
    method: str
    reference: Optional[str] = None
    received_at: datetime


class PatientHistoryResponse(BaseModel):
    patient: PatientResponse
    visits: List[PatientHistoryVisitItem]
    invoices: List[PatientHistoryInvoiceItem]
    payments: List[PatientHistoryPaymentItem] = []
    total_invoices_count: int
    total_billed_amount: int
    total_paid_amount: int
    total_outstanding_due: int


class DuplicatePatientCheck(BaseModel):
    has_duplicates: bool
    potential_matches: List[PatientResponse]

