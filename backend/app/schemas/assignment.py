from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class ManualAssignRequest(BaseModel):
    test_order_id: int
    assigned_destination: Optional[str] = None
    destination_name: Optional[str] = None
    destination_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    reason: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="before")
    @classmethod
    def normalize_destination(cls, data):
        if isinstance(data, dict):
            dest = data.get("assigned_destination") or data.get("destination_name")
            if not dest and data.get("destination_id"):
                dest = f"Destination #{data['destination_id']}"
            data["assigned_destination"] = dest or "General Lab"
        return data


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

