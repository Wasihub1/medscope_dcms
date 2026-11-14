from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class ManualAssignRequest(BaseModel):
    """Prompt 10E Part 7: the target is a lab room. Send lab_section (room key) or a room name;
    a numeric destination id is resolved to its room name and never stored as an id."""
    test_order_id: int
    lab_section: Optional[str] = None
    assigned_destination: Optional[str] = None
    destination_name: Optional[str] = None
    destination_id: Optional[int] = None
    assigned_to_id: Optional[int] = None  # ignored: routing never targets one technician
    reason: Optional[str] = Field(default=None, max_length=255)


class UnassignedOrderResponse(BaseSchema):
    test_order_id: int
    invoice_id: int
    invoice_no: str
    patient_id: int
    patient_name: str
    patient_code: str
    patient_phone: str
    test_code: str
    test_name: str
    department: str
    urgent: bool
    status: str
    created_at: datetime
    id: Optional[str] = None
    invoice_number: Optional[str] = None
    is_urgent: Optional[bool] = None
    order_status: Optional[str] = None
    lab_section: Optional[str] = None
    lab_section_label: Optional[str] = None

    @model_validator(mode="after")
    def populate_order_aliases(self):
        if self.id is None:
            self.id = str(self.test_order_id)
        if not self.invoice_number:
            self.invoice_number = self.invoice_no
        if self.is_urgent is None:
            self.is_urgent = self.urgent
        if not self.order_status:
            self.order_status = self.status
        return self


class AssignmentHistoryResponse(BaseSchema):
    id: int
    test_order_id: int
    previous_assignee: Optional[str] = None
    new_assignee: str
    reason: Optional[str] = None
    changed_by_name: Optional[str] = None
    changed_at: datetime



class AssignedTestOrderResponse(BaseSchema):
    """Prompt 10F (F1): one row of the Assigned Tests view. Strictly money-free."""
    test_order_id: int
    invoice_id: int
    invoice_no: str
    patient_id: int
    patient_name: str
    patient_code: str
    test_code: str
    test_name: str
    department: Optional[str] = None
    lab_section: Optional[str] = None
    lab_section_label: Optional[str] = None
    # Active technicians of the room; empty when the order is UNASSIGNED
    technician_names: list[str] = Field(default_factory=list)
    assignment_state: str  # ASSIGNED or UNASSIGNED
    status: str  # order status; CANCELLED when the invoice line is cancelled
    urgent: bool = False
    result_status: Optional[str] = None
    worked_by_name: Optional[str] = None
    created_at: datetime
    can_reassign: bool = False
    reassign_block_reason: Optional[str] = None
