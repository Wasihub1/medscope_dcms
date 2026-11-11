from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_lab_tech_or_admin, require_receptionist
from backend.app.schemas.result import (
    ResultTemplateResponse,
    ResultEntryRequest,
    ResultResponse,
)
from backend.app.schemas.refund import RefundRequestResponse, D15RefundClinicalResponse
from backend.app.services.result_service import (
    get_result_template,
    save_test_result,
    seed_default_test_components,
)
from backend.app.services.refund_service import initiate_d15_refund_request
from backend.app.api.v1.endpoints.refunds import to_refund_response

router = APIRouter()


@router.get("/{test_order_id}/result-template", response_model=ResultTemplateResponse, summary="Get result entry template and components for test order")
def get_order_result_template(
    test_order_id: int,
    actor: CurrentActor = Depends(require_lab_tech_or_admin),
    db: Session = Depends(get_db),
):
    # Ensure default catalog components are seeded for this tenant if not present
    seed_default_test_components(db, actor.tenant_id)
    db.commit()
    return get_result_template(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
    )


@router.post("/{test_order_id}/result", response_model=ResultResponse, status_code=status.HTTP_200_OK, summary="Save or submit clinical result data (Module 13)")
def save_order_result(
    test_order_id: int,
    data: ResultEntryRequest,
    actor: CurrentActor = Depends(require_lab_tech_or_admin),
    db: Session = Depends(get_db),
):
    res = save_test_result(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return res


@router.get("/{test_order_id}/result", response_model=ResultTemplateResponse, summary="Get entered clinical result")
def get_order_result(
    test_order_id: int,
    actor: CurrentActor = Depends(require_lab_tech_or_admin),
    db: Session = Depends(get_db),
):
    return get_result_template(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
    )


@router.post("/{test_order_id}/d15-refund-request", response_model=D15RefundClinicalResponse, status_code=status.HTTP_201_CREATED, summary="Lab Tech submits D15 refund request for rejected/spoiled specimen")
def submit_d15_refund_request(
    test_order_id: int,
    notes: str = "",
    actor: CurrentActor = Depends(require_lab_tech_or_admin),
    db: Session = Depends(get_db),
):
    req = initiate_d15_refund_request(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        requested_by_id=actor.id,
        notes=notes,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(req)
    inv = req.invoice
    line = req.invoice_line
    staff = req.requested_by
    return D15RefundClinicalResponse(
        id=req.id,
        test_order_id=test_order_id,
        invoice_id=req.invoice_id,
        invoice_no=getattr(inv, "invoice_number", None) if inv else None,
        invoice_line_id=req.invoice_line_id,
        test_name=getattr(line, "test_name", None) if line else None,
        reason=req.reason,
        request_type=req.request_type,
        status=req.status,
        requested_by_id=req.requested_by_id,
        requested_by_name=getattr(staff, "full_name", None) or getattr(staff, "display_name", None) if staff else None,
        requested_at=req.requested_at,
        message="D15 refund request submitted for Admin/Owner approval.",
    )

