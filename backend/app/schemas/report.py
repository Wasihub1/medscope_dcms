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
    # Prompt 16: false for the seeded pre-Module-14 reports (no stored content snapshot)
    has_snapshot: bool = False
    approval_rule: Optional[str] = None

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



# ---------------------------------------------------------------------------
# Prompt 10F (F2/F3): Ready results and the read-only result preview.
# These are NOT issued reports (no report_versions row; Module 14 is not built).
# ---------------------------------------------------------------------------
class ReadyReportResponse(BaseSchema):
    """One Ready result for the sidebar Ready Reports page (all rooms).
    Money: invoice_due / has_due are only set for actors allowed to see money; for anyone else the
    keys are left unset and omitted from the response (response_model_exclude_unset)."""
    test_order_id: int
    invoice_id: int
    invoice_no: str
    patient_id: int
    patient_name: str
    patient_code: str
    patient_phone: Optional[str] = None
    test_code: str
    test_name: str
    department: Optional[str] = None
    lab_section: Optional[str] = None
    lab_section_label: Optional[str] = None
    order_status: str
    urgent: bool = False
    result_status: str
    result_entered_at: Optional[datetime] = None
    result_entered_by_name: Optional[str] = None
    # Prompt 16 (Module 14): Finalize state
    approval_rule: Optional[str] = None
    doctor_approved: bool = False
    can_finalize: bool = False
    finalize_blocker: Optional[str] = None
    # money (only for money-permitted roles)
    has_due: Optional[bool] = None
    invoice_due: Optional[int] = None


class ResultPreviewItem(BaseSchema):
    """A saved result row exactly as snapshotted at entry (D24): later catalog changes never show here."""
    component_name: str
    component_code: Optional[str] = None
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    flag: Optional[str] = None
    comment: Optional[str] = None


class ResultPreviewResponse(BaseSchema):
    """Read-only, money-free preview of a saved result (DRAFT or ENTERED). Not a final report."""
    test_order_id: int
    invoice_no: str
    patient_name: str
    patient_code: str
    patient_gender: Optional[str] = None
    patient_age: Optional[str] = None
    test_code: str
    test_name: str
    department: Optional[str] = None
    lab_section_label: Optional[str] = None
    sample_code: Optional[str] = None
    sample_type: Optional[str] = None
    sample_collected_at: Optional[datetime] = None
    order_status: str
    report_template: Optional[str] = None
    result_status: str
    is_draft: bool
    is_ready: bool
    findings: Optional[str] = None
    impression: Optional[str] = None
    comments: Optional[str] = None
    structured_data: Optional[dict] = None
    entered_by_name: Optional[str] = None
    entered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Prompt 16 (Module 14): report state of this order. report_status NONE (no Final report yet) or FINAL.
    approval_rule: Optional[str] = None
    doctor_approved: bool = False
    report_status: str = "NONE"
    report_version_id: Optional[int] = None
    report_no: Optional[str] = None
    can_finalize: bool = False
    finalize_blocker: Optional[str] = None
    signatures: Optional[dict] = None  # only on a stored Final snapshot
    items: List[ResultPreviewItem] = Field(default_factory=list)


class FinalizeReportResponse(BaseModel):
    """Prompt 16: the Final report created by Finalize."""
    report_version_id: int
    report_no: str
    version: int
    status: str
    finalized_at: datetime
    finalized_by_name: Optional[str] = None
    test_order_id: int
