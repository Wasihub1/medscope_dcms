from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class DeliverableReportResponse(BaseSchema):
    report_version_id: int
    report_no: str
    version: int
    test_name: str
    department: str
    invoice_id: int
    invoice_no: str
    patient_id: int
    patient_name: str
    patient_code: str
    patient_phone: str
    issued_at: datetime
    issued_by_name: Optional[str] = None
    
    # Financial due gating
    invoice_due: int
    is_held_due_to_balance: bool
    is_delivered: bool
    delivered_at: Optional[datetime] = None
    delivered_to_name: Optional[str] = None

    # Aliases
    id: Optional[str] = None
    invoice_number: Optional[str] = None
    due_amount: Optional[int] = None
    can_deliver: Optional[bool] = None
    patient_mrn: Optional[str] = None
    authorized_at: Optional[datetime] = None
    authorized_by_name: Optional[str] = None
    version_number: Optional[int] = None

    @model_validator(mode="after")
    def populate_report_aliases(self):
        if self.id is None:
            self.id = str(self.report_version_id)
        if not self.invoice_number:
            self.invoice_number = self.invoice_no
        if self.due_amount is None:
            self.due_amount = self.invoice_due
        if self.can_deliver is None:
            self.can_deliver = not self.is_held_due_to_balance
        if not self.patient_mrn:
            self.patient_mrn = self.patient_code
        if not self.authorized_at:
            self.authorized_at = self.issued_at
        if not self.authorized_by_name:
            self.authorized_by_name = self.issued_by_name
        if self.version_number is None:
            self.version_number = self.version
        return self


class ReportDeliveryRequest(BaseModel):
    delivered_to_name: str = Field(..., min_length=2, max_length=150)
    delivered_to_phone: Optional[str] = Field(default=None, max_length=50)
    delivered_to_relation: str = Field(default="Self", max_length=50)
    admin_due_override_reason: Optional[str] = Field(default=None, max_length=300)
    override_reason: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_relation: Optional[str] = None
    notes: Optional[str] = None


class ReportDeliveryResponse(BaseSchema):
    id: int
    report_version_id: int
    delivered_to_name: str
    delivered_to_phone: Optional[str] = None
    delivered_to_relation: str
    delivered_with_due: bool
    due_release_reason: Optional[str] = None
    delivered_at: datetime
    delivered_by_name: str


class PrintableReportData(BaseModel):
    report_no: str
    version: int
    patient_name: str
    patient_code: str
    age_gender_summary: str
    phone: str
    referred_by: Optional[str] = None
    invoice_no: str
    sample_collected_at: Optional[datetime] = None
    test_name: str
    department: str
    findings_summary: Optional[str] = None
    issued_at: datetime
    issued_by_name: Optional[str] = None
    is_duplicate: bool = False
    reprint_count: int = 0

