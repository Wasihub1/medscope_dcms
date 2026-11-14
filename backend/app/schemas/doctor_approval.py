"""Prompt 15 (D22): doctor sign-off queue and approval. Money-free by design."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.report import ResultPreviewResponse


class DoctorRef(BaseModel):
    id: int
    name: str
    registration_no: Optional[str] = None
    specialty: Optional[str] = None


class ApprovalQueueItem(BaseModel):
    test_order_id: int
    invoice_no: str
    patient_name: str
    patient_code: str
    test_code: str
    test_name: str
    department: Optional[str] = None
    lab_section_label: Optional[str] = None
    approval_rule: str
    order_status: str
    urgent: bool = False
    technician_name: Optional[str] = None
    result_entered_at: Optional[datetime] = None
    assigned_doctor: Optional[DoctorRef] = None


class ApprovalQueueResponse(BaseModel):
    scope: str  # 'OWN' (DOCTOR login) or 'ALL' (Admin/Owner)
    my_doctor: Optional[DoctorRef] = None  # the DOCTOR login's own profile
    items: List[ApprovalQueueItem]


class ApprovalRecord(BaseModel):
    id: int
    doctor: DoctorRef
    approved_by_user_id: int
    approved_by_name: Optional[str] = None
    approved_by_role: str
    is_attestation: bool
    notes: Optional[str] = None
    approved_at: datetime


class ApprovalDetailResponse(BaseModel):
    test_order_id: int
    approval_rule: str
    order_status: str
    path: str  # 'DOCTOR_OWN' or 'STAFF_ATTESTATION'
    can_approve: bool
    blocked_reason: Optional[str] = None
    technician_name: Optional[str] = None
    technician_signed_at: Optional[datetime] = None
    assigned_doctor: Optional[DoctorRef] = None
    my_doctor: Optional[DoctorRef] = None
    approval: Optional[ApprovalRecord] = None
    preview: ResultPreviewResponse


class ApproveRequest(BaseModel):
    doctor_id: Optional[int] = Field(default=None, description="Path A (Admin/Owner): the doctor the approval is for. Ignored for DOCTOR logins.")
    attestation: bool = Field(default=False, description="Path A: must be true (staff confirms the doctor reviewed and approved).")
    notes: Optional[str] = Field(default=None, max_length=500)


class AssignDoctorRequest(BaseModel):
    doctor_id: Optional[int] = Field(default=None, description="Referrer id; null clears the assignment.")
