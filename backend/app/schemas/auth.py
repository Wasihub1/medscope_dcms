from typing import Optional, List
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Staff username")
    password: str = Field(..., description="Account password")
    role: Optional[str] = Field(None, description="Optional; must equal the user's single role if given (Prompt 10D)")


class AuthUserResponse(BaseModel):
    id: int
    tenant_id: str
    username: str
    display_name: str
    roles: List[str]  # always exactly one role (Prompt 10D: one login = one fixed role)
    acting_role: str  # equals the single role; kept for client compatibility
    role: Optional[str] = None
    department: Optional[str] = None
    lab_section: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    home_route: str
    permissions: List[str] = []

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, description="New password for target user (minimum 8 characters)")


class AuthMessageResponse(BaseModel):
    message: str
    success: bool = True
