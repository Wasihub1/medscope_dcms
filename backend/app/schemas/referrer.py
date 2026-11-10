from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class ReferrerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    referrer_type: str = Field(default="Doctor", max_length=50)
    type: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=50)
    registration_no: Optional[str] = Field(default=None, max_length=100)
    specialty: Optional[str] = Field(default=None, max_length=200)
    chamber_address: Optional[str] = Field(default=None, max_length=300)
    # Write-only initial commission input (Prompt 04 Item 01)
    commission_rate: Optional[int] = Field(default=0, ge=0, le=100, description="Write-only initial commission rate percentage")
    commission_type: Optional[str] = Field(default="PERCENTAGE", max_length=20)

    @model_validator(mode="before")
    @classmethod
    def normalize_type_field(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "type" in values and values.get("type"):
                values["referrer_type"] = values["type"]
        return values


class ReferrerResponse(BaseSchema):
    id: int
    name: str
    referrer_type: str
    type: Optional[str] = None
    phone: Optional[str] = None
    registration_no: Optional[str] = None
    specialty: Optional[str] = None
    chamber_address: Optional[str] = None
    active: bool
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_type(cls, data: Any) -> Any:
        if hasattr(data, "referrer_type") and not hasattr(data, "type"):
            setattr(data, "type", getattr(data, "referrer_type"))
        elif isinstance(data, dict) and "referrer_type" in data and "type" not in data:
            data["type"] = data["referrer_type"]
        return data

    # Notice: commission_type and commission_rate are strictly excluded from this schema
