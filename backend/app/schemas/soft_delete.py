"""Prompt 11: soft-delete / restore / Deleted-view / discard / audit-log schemas.
Money-free by design (no prices, commission, amounts)."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DeleteRequest(BaseModel):
    # Optional in the schema so a missing reason is a clear 400 from the service, not a 422.
    reason: Optional[str] = Field(default=None, description="Mandatory, non-empty (max 500 characters)")


class DeletedItemResponse(BaseModel):
    id: int
    kind: str  # USER | REFERRER | TEST
    title: str
    subtitle: Optional[str] = None
    deleted_at: datetime
    deleted_by_id: Optional[int] = None
    deleted_by_name: Optional[str] = None
    delete_reason: Optional[str] = None


class DiscardResponse(BaseModel):
    message: str
    discarded_invoice_id: int
    temp_invoice_id: Optional[str] = None


class AuditLogItem(BaseModel):
    id: int
    created_at: datetime
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    acting_role: str
    action: str
    domain: str = "other"
    entity_type: str
    entity_id: str
    reason: Optional[str] = None
    before_value: Optional[str] = None
    after_value: Optional[str] = None


class AuditLogPage(BaseModel):
    items: List[AuditLogItem]
    total: int
    page: int
    size: int
    pages: int


class AuditDomain(BaseModel):
    key: str
    label: str


class AuditActor(BaseModel):
    id: int
    name: str


class AuditLogMeta(BaseModel):
    actions: List[str]
    entity_types: List[str]
    domains: List[AuditDomain] = []
    roles: List[str] = []
    actors: List[AuditActor] = []


class RestoredResponse(BaseModel):
    id: int
    kind: str
    title: str
    message: str
