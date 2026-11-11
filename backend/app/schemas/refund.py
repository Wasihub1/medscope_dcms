from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.schemas.common import BaseSchema


class RefundEligibilityResponse(BaseModel):
    invoice_id: int
    invoice_line_id: int
    test_name: str
    is_eligible: bool
    rejection_reason: Optional[str] = None
    refundable_amount: int


class RefundRequestCreate(BaseModel):
    invoice_line_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: Optional[int] = None
    reason: str = Field(..., min_length=2, max_length=500, description="Reason for cancellation / D15 refund")
    request_type: Optional[str] = Field(default="PRE_SAMPLE_CANCELLATION", description="PRE_SAMPLE_CANCELLATION or D15_NOT_PERFORMED")


class RefundDisbursementRequest(BaseModel):
    method: str = Field(default="CASH", description="CASH, BKASH, NAGAD, POS_CARD, BANK_TRANSFER")
    reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=300)


class AdminReviewRefundRequest(BaseModel):
    action: Optional[str] = None  # APPROVE or REJECT
    status: Optional[str] = None  # APPROVED or REJECTED
    rejection_reason: Optional[str] = None
    review_notes: Optional[str] = Field(default=None, max_length=300)


class RefundRequestResponse(BaseSchema):
    id: int
    invoice_id: int
    invoice_no: Optional[str] = None
    invoice_line_id: Optional[int] = None
    test_name: Optional[str] = None
    amount: int
    reason: str
    request_type: str = "PRE_SAMPLE_CANCELLATION"
    status: str  # PENDING_ADMIN_APPROVAL, APPROVED, REJECTED, DISBURSED
    requested_by_id: int
    requested_by_name: Optional[str] = None
    requested_at: datetime
    reviewed_by_id: Optional[int] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    disbursed_at: Optional[datetime] = None
    disbursed_by_id: Optional[int] = None
    disbursed_by_name: Optional[str] = None
    disbursement_method: Optional[str] = None
    disbursement_reference: Optional[str] = None
    invoice_number: Optional[str] = None
    patient_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data: Any) -> Any:
        if hasattr(data, "id") and hasattr(data, "invoice_id"):
            inv = getattr(data, "invoice", None)
            inv_no = getattr(inv, "invoice_no", None) or getattr(data, "invoice_no", None) or f"INV-{data.invoice_id}"
            line = getattr(data, "invoice_line", None)
            t_name = getattr(line, "test_name_snapshot", None) if line else getattr(data, "test_name", None) or "Investigation Item"
            staff = getattr(data, "requested_by", None)
            s_name = getattr(staff, "display_name", None) if staff else getattr(data, "requested_by_name", None) or "Staff"
            reviewer = getattr(data, "reviewed_by", None)
            rev_name = getattr(reviewer, "display_name", None) if reviewer else getattr(data, "reviewed_by_name", None)
            disburser = getattr(data, "disbursed_by", None)
            disb_name = getattr(disburser, "display_name", None) if disburser else None
            return {
                "id": data.id,
                "invoice_id": data.invoice_id,
                "invoice_no": inv_no,
                "invoice_line_id": data.invoice_line_id,
                "test_name": t_name,
                "amount": data.amount,
                "reason": data.reason,
                "request_type": getattr(data, "request_type", "PRE_SAMPLE_CANCELLATION"),
                "status": data.status,
                "requested_by_id": data.requested_by_id,
                "requested_by_name": s_name,
                "requested_at": data.requested_at,
                "reviewed_by_id": getattr(data, "reviewed_by_id", None),
                "reviewed_by_name": rev_name,
                "reviewed_at": getattr(data, "reviewed_at", None),
                "review_notes": getattr(data, "review_notes", None),
                "disbursed_at": getattr(data, "disbursed_at", None),
                "disbursed_by_id": getattr(data, "disbursed_by_id", None),
                "disbursed_by_name": disb_name,
                "disbursement_method": getattr(data, "disbursement_method", None),
                "disbursement_reference": getattr(data, "disbursement_reference", None),
                "invoice_number": inv_no,
                "patient_name": getattr(inv, "patient", None).name if getattr(inv, "patient", None) else None,
            }
        return data

    @model_validator(mode="after")
    def populate_refund_aliases(self):
        if not self.invoice_number and self.invoice_no:
            self.invoice_number = self.invoice_no
        return self


class D15RefundClinicalResponse(BaseModel):
    """
    Clinical-only D15 refund response for Laboratory Technicians (Fix 5 / Rule M11.3).
    Strictly excludes all monetary figures (amount, price, refund value).
    """
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: int
    test_order_id: Optional[int] = None
    invoice_id: int
    invoice_no: Optional[str] = None
    invoice_line_id: Optional[int] = None
    test_name: Optional[str] = None
    reason: str
    request_type: str = "D15_NOT_PERFORMED"
    status: str
    requested_by_id: int
    requested_by_name: Optional[str] = None
    requested_at: datetime
    message: str = "D15 refund request submitted for Admin/Owner approval."
