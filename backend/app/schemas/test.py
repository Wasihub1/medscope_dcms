from typing import Optional
from pydantic import BaseModel, model_validator
from backend.app.schemas.common import BaseSchema


class TestResponse(BaseSchema):
    id: int
    code: str
    name: str
    short_name: Optional[str] = None
    alternate_names: Optional[str] = None
    department: str
    price: int  # Whole-Taka integer
    default_price: Optional[int] = None
    sample_type: Optional[str] = None
    default_assignee: Optional[str] = None
    turnaround_hours: Optional[int] = None
    performing_role: str = "LAB_TECH"
    requires_doctor: bool = False
    report_template: str = "NUMERIC_TABLE"
    approval_rule: str = "TECHNICIAN_FINAL"
    is_outsourced: bool = False
    active: bool

    @model_validator(mode="after")
    def populate_default_price(self):
        if self.default_price is None:
            self.default_price = self.price
        return self


class TestDestinationResponse(BaseSchema):
    id: int
    name: str
    destination_type: str
    department: Optional[str] = None
    active: bool

