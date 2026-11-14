from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from backend.app.schemas.common import BaseSchema


class TechnicianWorklistItemResponse(BaseSchema):
    """
    Strictly isolated clinical response schema for laboratory technicians.
    Pursuant to Section 5.4 of Prompt 05 and Prompt 06, ALL financial fields
    (prices, invoice totals, dues, discounts, commissions, reagent costs)
    are strictly excluded at the backend schema level.
    """
    test_order_id: int
    invoice_id: int
    invoice_no: str
    status: str
    urgent: bool

    # Patient demographics (Clinical / Operational only)
    patient_id: int
    patient_name: str
    patient_code: str
    patient_gender: Optional[str] = None
    patient_age: Optional[str] = None
    patient_phone: Optional[str] = None

    # Investigation metadata
    test_id: int
    test_code: str
    test_name: str
    department: str
    sample_type: Optional[str] = None
    sample_route: str = "QUICK"
    report_template: str = "NUMERIC_TABLE"
    approval_rule: str = "TECHNICIAN_FINAL"
    requires_doctor: bool = False

    # Specimen tracking & Lifecycle (Module 12)
    sample_id: Optional[int] = None
    sample_code: Optional[str] = None
    temp_sample_id: Optional[str] = None
    sample_status: str = "PENDING"  # PENDING, COLLECTED, REJECTED, SPOILED
    sample_collected_at: Optional[datetime] = None
    is_line_locked: bool = False
    rejection_reason: Optional[str] = None
    outcome: Optional[str] = None

    # Module 13: Result Entry Status
    result_status: Optional[str] = None
    has_result: bool = False

    # Patient Contact Follow-up (D15 rule)
    patient_followup_required: bool = False
    patient_contact_status: Optional[str] = None
    patient_contact_notes: Optional[str] = None
    d15_refund_status: Optional[str] = None

    # Department Workflow Extensions (Module 12)
    culture_stage: Optional[str] = None
    outsourced_status: Optional[str] = None
    outsourced_lab_name: Optional[str] = None
    outsourced_sent_at: Optional[datetime] = None
    outsourced_received_at: Optional[datetime] = None
    outsourced_ref_no: Optional[str] = None

    # Staff attribution
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    assigned_destination: Optional[str] = None
    assigned_at: Optional[datetime] = None

    # Turnaround clocks & Late tracking
    turnaround_hours: Optional[int] = None
    tat_display: str
    ordered_at: datetime
    patient_clock_elapsed_mins: int
    patient_clock_display: str
    lab_clock_elapsed_mins: Optional[int] = None
    lab_clock_display: Optional[str] = None
    is_late: bool
    late_reason: Optional[str] = None
    # Prompt 10E: sample rule, room and report readiness (all money-free)
    requires_sample: bool = True
    is_imaging: bool = False
    lab_section: Optional[str] = None
    lab_section_label: Optional[str] = None
    report_ready: bool = False


class SampleTakenRequest(BaseModel):
    """
    Quick route specimen collection event request (Section 4.7 & 5.2).
    Allows entering collection time and optional offline temporary sample ID.
    """
    collected_at: Optional[datetime] = Field(default=None, description="Collection timestamp. Defaults to UTC now if omitted.")
    sample_type: Optional[str] = Field(default=None, description="Optional specimen type override.")
    temp_sample_id: Optional[str] = Field(default=None, description="Temporary sample ID for offline reconciliation.")
    notes: Optional[str] = Field(default=None, max_length=255, description="Collection notes.")


class RejectSampleRequest(BaseModel):
    """
    Spoiled or rejected specimen event request (Section 5.3).
    A rejection reason is mandatory. Triggers patient contact follow-up.
    """
    rejection_reason: str = Field(..., min_length=3, max_length=255, description="Mandatory reason for sample rejection.")
    notes: Optional[str] = Field(default=None, max_length=500, description="Additional clinical or handling notes.")
    spoil_type: str = Field(default="REJECTED", description="REJECTED (hemolyzed, clotted, insufficient) or SPOILED (mishandled, contaminated).")


class PatientContactRequest(BaseModel):
    """Patient follow-up contact record after sample rejection (D15 rule)."""
    contact_status: str = Field(..., description="CALLED, RECOLLECTION_AGREED, REFUND_REQUESTED")
    notes: Optional[str] = Field(default=None, max_length=500, description="Outcome notes from patient call.")


class ImagingPerformedRequest(BaseModel):
    """Radiology / Imaging scan execution record (Section 5.5)."""
    performed_at: Optional[datetime] = Field(default=None, description="Examination timestamp. Defaults to UTC now.")
    notes: Optional[str] = Field(default=None, max_length=500, description="Technologist procedure notes.")


class CultureStageRequest(BaseModel):
    """Culture multi-stage lifecycle transition request (Section 5.5)."""
    stage: str = Field(..., description="Target stage: INCUBATING, PRELIMINARY, FINAL")
    notes: Optional[str] = Field(default=None, max_length=500, description="Stage observations or preliminary findings.")


class OutsourcedStageRequest(BaseModel):
    """Outside referral laboratory dispatch or receipt record (Section 5.5)."""
    action: str = Field(..., description="SENT or RECEIVED")
    lab_name: Optional[str] = Field(default=None, max_length=100, description="External referral laboratory name.")
    ref_no: Optional[str] = Field(default=None, max_length=100, description="Courier dispatch number or external reference number.")
    timestamp: Optional[datetime] = Field(default=None, description="Dispatch or receipt timestamp.")
    notes: Optional[str] = Field(default=None, max_length=500, description="Outsourced notes.")


class BarcodeLabelResponse(BaseSchema):
    """Printable barcode label payload for specimen tubes (50mm x 25mm / 50mm x 30mm)."""
    test_order_id: int
    sample_code: str
    temp_sample_id: Optional[str] = None
    patient_name: str
    patient_code: str
    patient_gender: Optional[str] = None
    patient_age: Optional[str] = None
    test_code: str
    test_name: str
    department: str
    sample_type: Optional[str] = None
    collected_at: Optional[datetime] = None
    barcode_svg: str
    barcode_format: str = "CODE128"


class TestOrderEventResponse(BaseSchema):
    """Append-only operational history entry."""
    id: int
    test_order_id: int
    event_type: str
    stage: Optional[str] = None
    description: str
    notes: Optional[str] = None
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    created_at: datetime


class UpdateOrderStatusRequest(BaseModel):
    """Workflow state transition request."""
    status: str = Field(..., description="Target status: IN_PROGRESS, AWAITING_DOCTOR, COMPLETED, CANCELLED")
    notes: Optional[str] = Field(default=None, max_length=255)


class WorklistSummaryResponse(BaseSchema):
    """Bento metrics for the technician workbench."""
    technician_id: int
    technician_name: str
    department: Optional[str] = None
    total_assigned: int = 0
    urgent_count: int = 0
    sample_pending_count: int = 0
    in_progress_count: int = 0
    awaiting_doctor_count: int = 0
    late_count: int = 0
    completed_count: int = 0
    rejected_count: int = 0
    culture_count: int = 0
    imaging_count: int = 0
    outsourced_count: int = 0
    # Prompt 10E
    ready_count: int = 0
    unassigned_count: int = 0
    lab_section: Optional[str] = None


class ReassignRoomRequest(BaseModel):
    """Prompt 10E Part 7: move an order to another room (worklist.reassign)."""
    lab_section: str
    reason: Optional[str] = None


class RoomResponse(BaseModel):
    code: str
    name: str
    room: str
    destination: str
    label: Optional[str] = None
    active_technicians: int = 0
