from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.core.permissions import has_permission
from backend.app.core.samples import SAMPLE_REQUIRED_MESSAGE, requires_sample
from backend.app.core.timezone import utc_now
from backend.app.core.security import CurrentActor
from backend.app.models.test import Test, TestComponent
from backend.app.models.test_order import TestOrder, TestOrderEvent
from backend.app.models.sample import Sample
from backend.app.models.result import Result, ResultItem
from backend.app.schemas.result import (
    TestComponentResponse,
    ComponentResultInput,
    ResultEntryRequest,
    ResultItemResponse,
    ResultResponse,
    ResultTemplateResponse,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.services import reference_range_service as rrs
from backend.app.services.line_lock_service import lock_line_at_result_completion
from backend.app.services.routing_service import ensure_order_access, record_actor


def validate_and_compute_flag(
    comp: Optional[TestComponent],
    raw_value: str,
    band: Optional[Any] = None,
) -> Tuple[Optional[float], Optional[str]]:
    """
    Module 13 Invariant:
    1. Validates impossible-value limits to prevent absurd numeric entries (e.g. Hemoglobin 150).
       Raises HTTP 400 with an explicit message if limits are violated.
    2. Automatically determines result flag: LOW, HIGH, CRITICAL, NORMAL, or None.
    3. Handles missing or incomplete configuration safely (never silently classifies as normal).
    Prompt 14 (D24): the reference / critical limits come from `band` (the ReferenceRangeVersion chosen for
    this patient by sex and age in days); impossible-value limits stay on the component. When `band` is None
    the limits are read from `comp` (only objects that still carry them, e.g. unit-test stand-ins); a real
    TestComponent has none, so no band means no flag.
    """
    limits = band if band is not None else comp
    if not raw_value or not raw_value.strip():
        return None, None

    clean_str = raw_value.strip()
    try:
        val = float(clean_str)
    except ValueError:
        # Non-numeric text (e.g. "Trace", "Positive", "Negative", "Nil")
        return None, None

    if not comp:
        return val, None

    # 1. Impossible-value limits check (Section 3.4)
    if comp.impossible_min is not None and val < comp.impossible_min:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Validation Error: Entered value '{val}' for '{comp.name}' is below the "
                f"physiologically impossible minimum limit of {comp.impossible_min} {comp.unit or ''}. "
                f"Absurd numeric entries are rejected."
            ),
        )

    if comp.impossible_max is not None and val > comp.impossible_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Validation Error: Entered value '{val}' for '{comp.name}' exceeds the "
                f"physiologically impossible maximum limit of {comp.impossible_max} {comp.unit or ''}. "
                f"Absurd numeric entries are rejected."
            ),
        )

    # 2. Critical Limits Check (Section 3.3)
    c_min, c_max = getattr(limits, "critical_min", None), getattr(limits, "critical_max", None)
    r_min, r_max = getattr(limits, "ref_min", None), getattr(limits, "ref_max", None)
    if c_min is not None and val < c_min:
        return val, "CRITICAL"
    if c_max is not None and val > c_max:
        return val, "CRITICAL"

    # 3. Normal / Low / High Reference Range Check
    if r_min is not None and val < r_min:
        return val, "LOW"
    if r_max is not None and val > r_max:
        return val, "HIGH"

    # If within configured ref_min and ref_max
    if r_min is not None or r_max is not None:
        return val, "NORMAL"

    # Missing or incomplete reference limits: safe fallback, do NOT silently assume NORMAL
    return val, None


def get_result_template(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
) -> ResultTemplateResponse:
    """
    Retrieves the clinical result-entry template for a TestOrder.
    Enforces technician assignment boundaries and specimen collection eligibility.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    # Access Boundary: Technician can only access assigned tasks (unless supervisor/admin)
    # Prompt 10E Part 7: room-based access (every technician of the room, Admin/Owner, doctor queue)
    ensure_order_access(actor, order, "You can only enter results for orders in your room.")

    # Ineligible Check: Cancelled, Rejected, or Spoiled tasks cannot proceed to ordinary result entry
    if order.status in ("CANCELLED", "REJECTED", "SPOILED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Test order is in '{order.status}' status. Result entry is prohibited.",
        )

    sample = order.sample
    if sample and sample.status in ("REJECTED", "SPOILED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Specimen is '{sample.status}'. Result entry is prohibited under D15 rule.",
        )

    # For biological tests, verify sample collection (Prompt 10E: one requires_sample helper)
    test = order.invoice_line.test
    # Prompt 10F (F4): NULL/empty sample_type on a non-imaging test now requires a sample
    if requires_sample(test, order) and (not sample or sample.status != "COLLECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SAMPLE_REQUIRED_MESSAGE,
        )

    inv = order.invoice_line.invoice
    patient = inv.patient
    visit = inv.visit
    age_str = f"{visit.age_value} {visit.age_unit}" if visit else None
    # Prompt 14 (D24): entered age + visit date -> total days; recorded gender -> sex key
    age_days = rrs.age_to_days(visit.age_value, visit.age_unit, visit.created_at.date() if visit.created_at else None) if visit else 0
    sex = rrs.sex_key(visit.gender if visit and visit.gender else patient.gender)

    # Fetch configured components
    components = (
        db.execute(
            select(TestComponent)
            .where(
                TestComponent.tenant_id == tenant_id,
                TestComponent.test_id == test.id,
                TestComponent.active == True,
            )
            .order_by(TestComponent.sort_order)
        )
        .scalars()
        .all()
    )

    bands = rrs.bands_by_component(db, [c.id for c in components])
    component_responses = []
    for c in components:
        band, match = rrs.pick_band(bands.get(c.id, []), sex, age_days)
        component_responses.append(TestComponentResponse(
            id=c.id,
            test_id=c.test_id,
            code=c.code,
            name=c.name,
            unit=c.unit,
            reference_range_text=band.reference_range_text if band else None,
            ref_min=band.ref_min if band else None,
            ref_max=band.ref_max if band else None,
            critical_min=band.critical_min if band else None,
            critical_max=band.critical_max if band else None,
            impossible_min=c.impossible_min,
            impossible_max=c.impossible_max,
            sort_order=c.sort_order,
            reference_range_version_id=band.id if band else None,
            range_match=match,
        ))

    existing_result = None
    if order.result:
        res = order.result
        item_responses = [
            ResultItemResponse(
                id=it.id,
                test_component_id=it.test_component_id,
                component_name=it.component_name,
                component_code=it.component_code,
                value=it.value,
                numeric_value=it.numeric_value,
                unit=it.unit,
                reference_range=it.reference_range,
                ref_min=it.ref_min,
                ref_max=it.ref_max,
                critical_min=it.critical_min,
                critical_max=it.critical_max,
                impossible_min=it.impossible_min,
                impossible_max=it.impossible_max,
                flag=it.flag,
                comment=it.comment,
                sort_order=it.sort_order,
                reference_range_version_id=it.reference_range_version_id,
                range_match=it.range_match,
            )
            for it in res.items
        ]
        staff = res.entered_by
        existing_result = ResultResponse(
            id=res.id,
            test_order_id=res.test_order_id,
            result_type=res.result_type,
            status=res.status,
            findings=res.findings,
            impression=res.impression,
            comments=res.comments,
            structured_data=res.structured_data,
            entered_by_id=res.entered_by_id,
            entered_by_name=staff.display_name if staff else None,
            entered_at=res.entered_at,
            updated_at=res.updated_at,
            updated_by_name=res.updated_by.display_name if res.updated_by else None,
            items=item_responses,
        )

    return ResultTemplateResponse(
        test_order_id=order.id,
        invoice_no=inv.invoice_no,
        test_id=test.id,
        test_code=test.code,
        test_name=test.name,
        department=order.department or test.department,
        sample_code=sample.sample_code if sample else None,
        sample_type=sample.sample_type if sample else test.sample_type,
        report_template=test.report_template,
        approval_rule=test.approval_rule,
        requires_doctor=test.requires_doctor,
        patient_name=patient.name,
        patient_code=patient.patient_code,
        patient_gender=patient.gender,
        patient_age=age_str,
        components=component_responses,
        existing_result=existing_result,
    )


def save_test_result(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: ResultEntryRequest,
) -> ResultResponse:
    """
    Saves or updates clinical result data for a TestOrder.
    - Validates impossible values with strict rejection.
    - Automatically computes result flags (LOW, HIGH, CRITICAL, NORMAL).
    - Stores immutable reference range snapshots (D24).
    - Preserves distinction between Result Status and TestOrder Status (Section 3.8).
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    # Prompt 10E Part 7: room-based access (every technician of the room, Admin/Owner, doctor queue)
    ensure_order_access(actor, order, "You can only enter results for orders in your room.")

    # Fix 4(a): Reject saving results if order is already COMPLETED (HTTP 409)
    if order.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot enter or modify results for a completed test order. Completed orders are immutable.",
        )

    # Prompt 16 (Module 14): a Final report or a recorded doctor approval closes the result.
    if order.report_version is not None and order.report_version.status == "FINAL_AUTHORIZED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This test already has a Final report. Its result can no longer be changed (corrections are a separate, later module).",
        )
    if order.doctor_approval is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A doctor approval is already recorded for this result, so it can no longer be changed.",
        )
    # Prompt 16: simple optimistic lock so two people cannot silently overwrite each other's draft.
    if data.expected_updated_at is not None and order.result is not None:
        exp = data.expected_updated_at
        cur = order.result.updated_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=cur.tzinfo)
        if abs((cur - exp).total_seconds()) > 0.001:
            who = order.result.updated_by or order.result.entered_by
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This result was changed by {who.display_name if who else 'another user'} at "
                       f"{cur.astimezone().strftime('%d %b %Y %H:%M')} after you opened it. Close and reopen it to see their changes.",
            )

    if order.status in ("CANCELLED", "REJECTED", "SPOILED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot enter results for order in '{order.status}' status.",
        )

    test = order.invoice_line.test

    # Fix 4(c): For sample-based tests, reject result saving before specimen collection (HTTP 409)
    if requires_sample(test, order):
        sample = order.sample
        if not sample or sample.status != "COLLECTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=SAMPLE_REQUIRED_MESSAGE,
            )

    now_ts = utc_now()
    result_status = "DRAFT" if data.status.upper() == "DRAFT" else "ENTERED"

    # Pre-fetch components for validation and snapshotting
    comps_by_id: Dict[int, TestComponent] = {}
    comps_by_code: Dict[str, TestComponent] = {}
    db_comps = (
        db.execute(
            select(TestComponent).where(
                TestComponent.tenant_id == tenant_id,
                TestComponent.test_id == test.id,
            )
        )
        .scalars()
        .all()
    )
    for c in db_comps:
        comps_by_id[c.id] = c
        comps_by_code[c.code.upper()] = c

    # Prompt 14 (D24): the patient sex and total age in days at the visit pick each component band
    visit = order.invoice_line.invoice.visit
    patient = order.invoice_line.invoice.patient
    age_days = rrs.age_to_days(visit.age_value, visit.age_unit, visit.created_at.date() if visit.created_at else None) if visit else 0
    sex = rrs.sex_key(visit.gender if visit and visit.gender else (patient.gender if patient else None))
    bands = rrs.bands_by_component(db, [c.id for c in db_comps])

    # 1. Validate all component inputs and compute flags
    processed_items: List[Dict[str, Any]] = []
    for item_input in data.items:
        comp = None
        if item_input.component_id and item_input.component_id in comps_by_id:
            comp = comps_by_id[item_input.component_id]
        elif item_input.component_code and item_input.component_code.upper() in comps_by_code:
            comp = comps_by_code[item_input.component_code.upper()]

        # Prompt 14: band by sex + age in days (the server decides; a client-sent range is never used for a known component)
        band, range_match = (rrs.pick_band(bands.get(comp.id, []), sex, age_days) if comp else (None, None))

        # Compute flag & validate impossible values (raises HTTP 400 on absurd values)
        numeric_val, auto_flag = validate_and_compute_flag(comp, item_input.value, band)

        # Snapshot applicable reference ranges (D24: the values used now; later versions never change them)
        if comp:
            ref_text = band.reference_range_text if band else None
            ref_min = band.ref_min if band else None
            ref_max = band.ref_max if band else None
            crit_min = band.critical_min if band else None
            crit_max = band.critical_max if band else None
        else:
            ref_text, ref_min, ref_max = item_input.reference_range, item_input.ref_min, item_input.ref_max
            crit_min, crit_max = item_input.critical_min, item_input.critical_max
        imp_min = comp.impossible_min if comp else item_input.impossible_min
        imp_max = comp.impossible_max if comp else item_input.impossible_max
        unit = comp.unit if comp else item_input.unit

        processed_items.append({
            "test_component_id": comp.id if comp else item_input.component_id,
            "component_name": comp.name if comp else item_input.component_name,
            "component_code": comp.code if comp else item_input.component_code,
            "value": item_input.value.strip(),
            "numeric_value": numeric_val,
            "unit": unit,
            "reference_range": ref_text,
            "ref_min": ref_min,
            "ref_max": ref_max,
            "critical_min": crit_min,
            "critical_max": crit_max,
            "impossible_min": imp_min,
            "impossible_max": imp_max,
            "flag": auto_flag,
            "reference_range_version_id": band.id if band else None,
            "range_match": range_match,
            "comment": item_input.comment.strip() if item_input.comment else None,
            "sort_order": item_input.sort_order if item_input.sort_order else (comp.sort_order if comp else 0),
        })

    # 2. Upsert Result
    result = order.result
    if not result:
        result = Result(
            tenant_id=tenant_id,
            test_order_id=order.id,
            result_type=test.report_template,
            status=result_status,
            findings=data.findings.strip() if data.findings else None,
            impression=data.impression.strip() if data.impression else None,
            comments=data.comments.strip() if data.comments else None,
            structured_data=data.structured_data,
            entered_by_id=actor.id,
            entered_at=now_ts,
            updated_at=now_ts,
            updated_by_id=actor.id,
        )
        db.add(result)
        db.flush()
    else:
        result.status = result_status
        result.findings = data.findings.strip() if data.findings else None
        result.impression = data.impression.strip() if data.impression else None
        result.comments = data.comments.strip() if data.comments else None
        result.structured_data = data.structured_data
        result.updated_at = now_ts
        result.updated_by_id = actor.id
        # Clear existing items for replacement
        result.items.clear()
        db.flush()

    # 3. Insert ResultItems
    for p in processed_items:
        r_item = ResultItem(
            tenant_id=tenant_id,
            result_id=result.id,
            test_component_id=p["test_component_id"],
            component_name=p["component_name"],
            component_code=p["component_code"],
            value=p["value"],
            numeric_value=p["numeric_value"],
            unit=p["unit"],
            reference_range=p["reference_range"],
            ref_min=p["ref_min"],
            ref_max=p["ref_max"],
            critical_min=p["critical_min"],
            critical_max=p["critical_max"],
            impossible_min=p["impossible_min"],
            impossible_max=p["impossible_max"],
            flag=p["flag"],
            reference_range_version_id=p["reference_range_version_id"],
            range_match=p["range_match"],
            comment=p["comment"],
            sort_order=p["sort_order"],
        )
        db.add(r_item)

    # 4. Update TestOrder operational lifecycle (distinct from Result status)
    if result_status == "ENTERED":
        # Fix 3 (D19, M12): Culture stage must be FINAL before order can be completed
        is_culture = (test and test.report_template == "CULTURE_SENSITIVITY") or (order.culture_stage is not None)
        if test.requires_doctor or test.performing_role == "DOCTOR":
            order.status = "AWAITING_DOCTOR"
        elif test.approval_rule == "TECHNICIAN_FINAL":
            if is_culture and order.culture_stage != "FINAL":
                order.status = "IN_PROGRESS"
            else:
                order.status = "COMPLETED"
                lock_line_at_result_completion(order, now_ts)  # Prompt 12
        else:
            order.status = "IN_PROGRESS"
    # Fix 4(b): Saving a DRAFT does NOT change or advance the TestOrder status
    record_actor(order, actor)  # Prompt 10E: who acted (not used for visibility)

    # 5. Append lifecycle history event
    event_action = "RESULT_SAVED_DRAFT" if result_status == "DRAFT" else "RESULT_ENTERED"
    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type=event_action,
        stage=order.status,
        description=f"Results {result_status.lower()} by {actor.display_name} ({actor.role})",
        notes=f"Items entered: {len(processed_items)} | Findings: {'Yes' if result.findings else 'No'}",
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=event_action,
        entity_type="RESULT",
        entity_id=result.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"Status: {result_status}, Items: {len(processed_items)}, Order Status: {order.status}",
    )

    db.flush()
    db.refresh(result)

    item_resps = [
        ResultItemResponse(
            id=it.id,
            test_component_id=it.test_component_id,
            component_name=it.component_name,
            component_code=it.component_code,
            value=it.value,
            numeric_value=it.numeric_value,
            unit=it.unit,
            reference_range=it.reference_range,
            ref_min=it.ref_min,
            ref_max=it.ref_max,
            critical_min=it.critical_min,
            critical_max=it.critical_max,
            impossible_min=it.impossible_min,
            impossible_max=it.impossible_max,
            flag=it.flag,
            comment=it.comment,
            sort_order=it.sort_order,
            reference_range_version_id=it.reference_range_version_id,
            range_match=it.range_match,
        )
        for it in result.items
    ]

    return ResultResponse(
        id=result.id,
        test_order_id=result.test_order_id,
        result_type=result.result_type,
        status=result.status,
        findings=result.findings,
        impression=result.impression,
        comments=result.comments,
        structured_data=result.structured_data,
        entered_by_id=result.entered_by_id,
        entered_by_name=actor.display_name,
        entered_at=result.entered_at,
        updated_at=result.updated_at,
        items=item_resps,
    )


def seed_default_test_components(db: Session, tenant_id: str) -> int:
    """
    Populates standard clinical test components and reference ranges for common tests.
    Idempotent: skips components that already exist.
    """
    defaults = {
        "CBC": [
            {"code": "HGB", "name": "Hemoglobin (Hb)", "unit": "g/dL", "ref_text": "12.0 - 16.0 g/dL", "ref_min": 12.0, "ref_max": 16.0, "critical_min": 6.0, "critical_max": 20.0, "imp_min": 1.0, "imp_max": 30.0, "sort": 1},
            {"code": "ESR", "name": "ESR (Westergren)", "unit": "mm in 1st hr", "ref_text": "0 - 20 mm in 1st hr", "ref_min": 0.0, "ref_max": 20.0, "critical_min": None, "critical_max": 100.0, "imp_min": 0.0, "imp_max": 150.0, "sort": 2},
            {"code": "TC", "name": "Total Leukocyte Count (TC)", "unit": "/cu.mm", "ref_text": "4,000 - 11,000 /cu.mm", "ref_min": 4000.0, "ref_max": 11000.0, "critical_min": 1500.0, "critical_max": 50000.0, "imp_min": 100.0, "imp_max": 200000.0, "sort": 3},
            {"code": "PLT", "name": "Platelet Count", "unit": "/cu.mm", "ref_text": "150,000 - 450,000 /cu.mm", "ref_min": 150000.0, "ref_max": 450000.0, "critical_min": 20000.0, "critical_max": 1000000.0, "imp_min": 5000.0, "imp_max": 2500000.0, "sort": 4},
            {"code": "NEUT", "name": "Neutrophils (DC)", "unit": "%", "ref_text": "40 - 75 %", "ref_min": 40.0, "ref_max": 75.0, "critical_min": 15.0, "critical_max": 95.0, "imp_min": 0.0, "imp_max": 100.0, "sort": 5},
            {"code": "LYMPH", "name": "Lymphocytes (DC)", "unit": "%", "ref_text": "20 - 45 %", "ref_min": 20.0, "ref_max": 45.0, "critical_min": 5.0, "critical_max": 85.0, "imp_min": 0.0, "imp_max": 100.0, "sort": 6},
            {"code": "EOSIN", "name": "Eosinophils (DC)", "unit": "%", "ref_text": "1 - 6 %", "ref_min": 1.0, "ref_max": 6.0, "critical_min": None, "critical_max": 25.0, "imp_min": 0.0, "imp_max": 100.0, "sort": 7},
            {"code": "MONO", "name": "Monocytes (DC)", "unit": "%", "ref_text": "2 - 10 %", "ref_min": 2.0, "ref_max": 10.0, "critical_min": None, "critical_max": 20.0, "imp_min": 0.0, "imp_max": 100.0, "sort": 8},
            {"code": "BASO", "name": "Basophils (DC)", "unit": "%", "ref_text": "0 - 1 %", "ref_min": 0.0, "ref_max": 1.0, "critical_min": None, "critical_max": 10.0, "imp_min": 0.0, "imp_max": 100.0, "sort": 9},
        ],
        "HGB": [
            {"code": "HGB", "name": "Hemoglobin (Hb%)", "unit": "g/dL", "ref_text": "12.0 - 16.0 g/dL", "ref_min": 12.0, "ref_max": 16.0, "critical_min": 6.0, "critical_max": 20.0, "imp_min": 1.0, "imp_max": 30.0, "sort": 1},
        ],
        "RBS": [
            {"code": "RBS", "name": "Random Blood Sugar (RBS)", "unit": "mmol/L", "ref_text": "4.0 - 7.8 mmol/L", "ref_min": 4.0, "ref_max": 7.8, "critical_min": 2.5, "critical_max": 25.0, "imp_min": 0.5, "imp_max": 60.0, "sort": 1},
        ],
        "FBS": [
            {"code": "FBS", "name": "Fasting Blood Sugar (FBS)", "unit": "mmol/L", "ref_text": "3.9 - 6.1 mmol/L", "ref_min": 3.9, "ref_max": 6.1, "critical_min": 2.5, "critical_max": 20.0, "imp_min": 0.5, "imp_max": 60.0, "sort": 1},
        ],
        "CREAT": [
            {"code": "CREAT", "name": "Serum Creatinine", "unit": "mg/dL", "ref_text": "0.6 - 1.2 mg/dL", "ref_min": 0.6, "ref_max": 1.2, "critical_min": 0.2, "critical_max": 6.0, "imp_min": 0.1, "imp_max": 25.0, "sort": 1},
        ],
        "SGPT": [
            {"code": "SGPT", "name": "Serum ALT / SGPT", "unit": "U/L", "ref_text": "Up to 45 U/L", "ref_min": 0.0, "ref_max": 45.0, "critical_min": None, "critical_max": 500.0, "imp_min": 0.0, "imp_max": 5000.0, "sort": 1},
        ],
        "SGOT": [
            {"code": "SGOT", "name": "Serum AST / SGOT", "unit": "U/L", "ref_text": "Up to 40 U/L", "ref_min": 0.0, "ref_max": 40.0, "critical_min": None, "critical_max": 500.0, "imp_min": 0.0, "imp_max": 5000.0, "sort": 1},
        ],
        "UREA": [
            {"code": "UREA", "name": "Serum Blood Urea", "unit": "mg/dL", "ref_text": "15 - 45 mg/dL", "ref_min": 15.0, "ref_max": 45.0, "critical_min": 5.0, "critical_max": 150.0, "imp_min": 1.0, "imp_max": 300.0, "sort": 1},
        ],
        "HBA1C": [
            {"code": "HBA1C", "name": "HbA1c (Glycated Hemoglobin)", "unit": "%", "ref_text": "4.0 - 6.0 %", "ref_min": 4.0, "ref_max": 6.0, "critical_min": 3.0, "critical_max": 16.0, "imp_min": 2.0, "imp_max": 25.0, "sort": 1},
        ],
        "LIPID": [
            {"code": "CHOL", "name": "Total Cholesterol", "unit": "mg/dL", "ref_text": "< 200 mg/dL", "ref_min": 100.0, "ref_max": 200.0, "critical_min": None, "critical_max": 400.0, "imp_min": 20.0, "imp_max": 1000.0, "sort": 1},
            {"code": "TG", "name": "Triglycerides", "unit": "mg/dL", "ref_text": "< 150 mg/dL", "ref_min": 50.0, "ref_max": 150.0, "critical_min": None, "critical_max": 600.0, "imp_min": 10.0, "imp_max": 2000.0, "sort": 2},
            {"code": "HDL", "name": "HDL Cholesterol", "unit": "mg/dL", "ref_text": "> 40 mg/dL", "ref_min": 40.0, "ref_max": 65.0, "critical_min": 15.0, "critical_max": None, "imp_min": 5.0, "imp_max": 150.0, "sort": 3},
            {"code": "LDL", "name": "LDL Cholesterol", "unit": "mg/dL", "ref_text": "< 130 mg/dL", "ref_min": 50.0, "ref_max": 130.0, "critical_min": None, "critical_max": 300.0, "imp_min": 10.0, "imp_max": 600.0, "sort": 4},
        ],
        "ELC": [
            {"code": "NA", "name": "Serum Sodium (Na+)", "unit": "mmol/L", "ref_text": "135 - 148 mmol/L", "ref_min": 135.0, "ref_max": 148.0, "critical_min": 120.0, "critical_max": 160.0, "imp_min": 80.0, "imp_max": 200.0, "sort": 1},
            {"code": "K", "name": "Serum Potassium (K+)", "unit": "mmol/L", "ref_text": "3.5 - 5.3 mmol/L", "ref_min": 3.5, "ref_max": 5.3, "critical_min": 2.5, "critical_max": 6.5, "imp_min": 1.0, "imp_max": 12.0, "sort": 2},
            {"code": "CL", "name": "Serum Chloride (Cl-)", "unit": "mmol/L", "ref_text": "98 - 107 mmol/L", "ref_min": 98.0, "ref_max": 107.0, "critical_min": 80.0, "critical_max": 125.0, "imp_min": 50.0, "imp_max": 160.0, "sort": 3},
        ],
        "TSH": [
            {"code": "TSH", "name": "Thyroid Stimulating Hormone (TSH)", "unit": "uIU/mL", "ref_text": "0.4 - 4.5 uIU/mL", "ref_min": 0.4, "ref_max": 4.5, "critical_min": 0.05, "critical_max": 40.0, "imp_min": 0.01, "imp_max": 150.0, "sort": 1},
        ],
        "FT4": [
            {"code": "FT4", "name": "Free Thyroxine (FT4)", "unit": "ng/dL", "ref_text": "0.8 - 1.9 ng/dL", "ref_min": 0.8, "ref_max": 1.9, "critical_min": 0.3, "critical_max": 4.0, "imp_min": 0.05, "imp_max": 10.0, "sort": 1},
        ],
    }

    count = 0
    for test_code, items in defaults.items():
        test = db.execute(
            select(Test).where(Test.tenant_id == tenant_id, Test.code == test_code)
        ).scalar_one_or_none()
        if not test:
            continue

        for it in items:
            existing = db.execute(
                select(TestComponent).where(
                    TestComponent.tenant_id == tenant_id,
                    TestComponent.test_id == test.id,
                    TestComponent.code == it["code"],
                )
            ).scalar_one_or_none()
            if not existing:
                comp = TestComponent(
                    tenant_id=tenant_id,
                    test_id=test.id,
                    code=it["code"],
                    name=it["name"],
                    unit=it["unit"],
                    impossible_min=it["imp_min"],
                    impossible_max=it["imp_max"],
                    sort_order=it["sort"],
                    active=True,
                )
                db.add(comp)
                db.flush()
                # D24: the demo range values become version 1 of one band (any sex, all ages)
                rrs.add_first_version(
                    db, tenant_id, comp, ref_min=it["ref_min"], ref_max=it["ref_max"],
                    critical_min=it["critical_min"], critical_max=it["critical_max"],
                    reference_range_text=it["ref_text"], note="Version 1: demo catalog range",
                )
                count += 1

    if count > 0:
        db.flush()
    return count

