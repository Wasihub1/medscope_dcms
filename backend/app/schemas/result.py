from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, model_validator
from backend.app.schemas.common import BaseSchema


class TestComponentResponse(BaseSchema):
    id: int
    test_id: int
    code: str
    name: str
    unit: Optional[str] = None
    reference_range_text: Optional[str] = None
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    impossible_min: Optional[float] = None
    impossible_max: Optional[float] = None
    sort_order: int = 0
    # Prompt 14 (D24): the band chosen for THIS patient (sex + age in days) and how it matched
    reference_range_version_id: Optional[int] = None
    range_match: Optional[str] = None  # MATCHED, FALLBACK_ANY, NO_BAND


class ComponentResultInput(BaseModel):
    component_id: Optional[int] = None
    component_name: str
    component_code: Optional[str] = None
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    impossible_min: Optional[float] = None
    impossible_max: Optional[float] = None
    comment: Optional[str] = None
    sort_order: int = 0


class ResultEntryRequest(BaseModel):
    status: str = Field(default="ENTERED", description="DRAFT or ENTERED")
    findings: Optional[str] = None
    impression: Optional[str] = None
    comments: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    items: List[ComponentResultInput] = []
    # Prompt 16: the updated_at the editor last loaded; a different stored value means someone else saved since (409).
    expected_updated_at: Optional[datetime] = None


class ResultItemResponse(BaseSchema):
    id: int
    test_component_id: Optional[int] = None
    component_name: str
    component_code: Optional[str] = None
    value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    impossible_min: Optional[float] = None
    impossible_max: Optional[float] = None
    flag: Optional[str] = None  # NORMAL, LOW, HIGH, CRITICAL, None
    comment: Optional[str] = None
    sort_order: int = 0
    reference_range_version_id: Optional[int] = None  # Prompt 14: band version used (None before Prompt 14)
    range_match: Optional[str] = None  # MATCHED, FALLBACK_ANY, NO_BAND


class ResultResponse(BaseSchema):
    id: int
    test_order_id: int
    result_type: str
    status: str
    findings: Optional[str] = None
    impression: Optional[str] = None
    comments: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    entered_by_id: int
    entered_by_name: Optional[str] = None
    entered_at: datetime
    updated_at: datetime
    updated_by_name: Optional[str] = None
    items: List[ResultItemResponse] = []


class ResultTemplateResponse(BaseModel):
    test_order_id: int
    invoice_no: str
    test_id: int
    test_code: str
    test_name: str
    department: str
    sample_code: Optional[str] = None
    sample_type: Optional[str] = None
    report_template: str
    approval_rule: str
    requires_doctor: bool
    patient_name: str
    patient_code: str
    patient_gender: str
    patient_age: Optional[str] = None
    components: List[TestComponentResponse] = []
    existing_result: Optional[ResultResponse] = None

