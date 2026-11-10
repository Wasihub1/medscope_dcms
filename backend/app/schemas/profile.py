from typing import Optional
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class ProfileResponse(BaseSchema):
    id: int
    username: str
    display_name: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None
    tenant_id: str
    tenant_name: Optional[str] = "Seba Diagnostic Center"
    full_name: Optional[str] = None

    @model_validator(mode="after")
    def populate_profile_aliases(self):
        if not self.full_name:
            self.full_name = self.display_name
        return self


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(default="", max_length=150)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def normalize_profile_input(cls, data):
        if isinstance(data, dict):
            if "full_name" in data and ("display_name" not in data or not data.get("display_name")):
                data["display_name"] = data["full_name"]
            if not data.get("display_name"):
                data["display_name"] = "Staff Member"
        return data

