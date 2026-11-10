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

