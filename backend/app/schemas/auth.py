from typing import Optional, List
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Staff username")
    password: str = Field(..., description="Account password")
    role: Optional[str] = Field(None, description="Optional acting role to select if user holds multiple roles")


class AuthUserResponse(BaseModel):
    id: int
    tenant_id: str
    username: str
    display_name: str
    roles: List[str]
    acting_role: str
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    home_route: str

    model_config = {"from_attributes": True}


class SwitchActingRoleRequest(BaseModel):
    role: str = Field(..., description="Role to switch into (must be held by the current user)")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, description="New password for target user (minimum 8 characters)")


class AuthMessageResponse(BaseModel):
    message: str
    success: bool = True
