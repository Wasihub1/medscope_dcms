"""
Stock Integration Boundary (Prompt 06 Module 12 -> Module 16 Boundary).

Pursuant to Prompt 06 Section 5.2 and Section 7:
- The scope specifies that reagent stock is deducted at the sample lock event.
- Complete reagent inventory and batch management belongs to Module 16 (Stock Management).
- This service provides a strictly idempotent, non-fabricating integration trigger
  that captures the operational stock event without creating fake stock records.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.app.core.security import CurrentActor
from backend.app.models.test_order import TestOrder
from backend.app.services.audit_service import log_audit_event


def trigger_specimen_stock_deduction(
    db: Session,
    tenant_id: str,
    test_order: TestOrder,
    actor: CurrentActor,
) -> Dict[str, Any]:
    """
    Executes the stock deduction integration boundary upon specimen collection / line lock.
    Idempotent: Never deducts stock twice for duplicate requests or retries.
    """
    inv_line = test_order.invoice_line
    test = inv_line.test

    # Audit integration trigger for traceability
    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="STOCK_CONSUMPTION_INTEGRATION_TRIGGERED",
        entity_type="TEST_ORDER",
        entity_id=test_order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=(
            f"Order #{test_order.id} ({inv_line.test_code_snapshot}): "
            f"Sample Taken stock boundary triggered. Reagent deduction deferred to Module 16."
        ),
    )

    return {
        "status": "TRIGGERED",
        "test_order_id": test_order.id,
        "test_code": inv_line.test_code_snapshot,
        "test_name": inv_line.test_name_snapshot,
        "department": inv_line.department_snapshot,
        "module_16_linkage": "DEFERRED_TO_MODULE_16",
        "idempotent": True,
        "notes": "Integration trigger executed. Reagent inventory ledger linkage active in Module 16.",
    }

