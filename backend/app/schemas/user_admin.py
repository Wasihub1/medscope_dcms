"""Prompt 10D Part 5: user management (Create User tab) schemas. Passwords are write-only."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PermissionDefResponse(BaseModel):
    key: str
    label: str
    group: str
    exposes_money: bool


class LabSectionResponse(BaseModel):
    code: str
    name: str
    room: str
    label: str


class UserAdminMetaResponse(BaseModel):
    roles: List[str]
    permissions: List[PermissionDefResponse]
    role_defaults: Dict[str, List[str]]
    money_restricted_roles: List[str]
    lab_sections: List[LabSectionResponse]


class UserSummaryResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    department: Optional[str] = None
    lab_section: Optional[str] = None
    lab_section_label: Optional[str] = None
    doctor_profile_id: Optional[int] = None  # Prompt 15: DOCTOR login -> doctor profile (referrers row)
    doctor_profile_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: bool
    is_locked: bool
    last_login_at: Optional[datetime] = None
    override_count: int = 0


class UserPermissionsResponse(BaseModel):
    role: str
    defaults: List[str]
    overrides: Dict[str, bool]
    effective: List[str]


class UserDetailResponse(UserSummaryResponse):
    permissions: UserPermissionsResponse


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    display_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=8, description="Initial password (write-only, never returned or logged)")
    role: str
    department: Optional[str] = Field(default=None, max_length=100)
    lab_section: Optional[str] = None
    doctor_profile_id: Optional[int] = None
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    active: bool = True
    permission_overrides: Dict[str, bool] = Field(default_factory=dict)


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    department: Optional[str] = Field(default=None, max_length=100)
    lab_section: Optional[str] = None
    doctor_profile_id: Optional[int] = None
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)


class UserRoleRequest(BaseModel):
    role: str
    lab_section: Optional[str] = None


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class UserPermissionOverridesRequest(BaseModel):
    """Map of permission key -> True (grant), False (revoke) or None (remove override, use role default)."""
    overrides: Dict[str, Optional[bool]]
