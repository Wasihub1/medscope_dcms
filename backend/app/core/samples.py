"""
MedScope DCMS — sample requirement rule. Single source of truth.

Prompt 10F (owner decision A5, supersedes the Prompt 10E rule):
1. Imaging tests never need a sample (definition below, the only one in the code base).
2. An EXPLICIT no-sample marker in the catalog sample_type ("None", "N/A", "NA", "No sample";
   trimmed, any case) means no sample is needed.
3. NULL or empty sample_type on a non-imaging test means UNKNOWN, and therefore a sample IS
   required (safe direction until the owner completes sample_type in the catalog).
4. Any other sample_type value names a real specimen: a sample is required.
An order explicitly on the FULL sample route still requires a sample unless it is imaging.

Imaging (Prompt 10F, tightened): a test is imaging when its lab room is ULTRASONOGRAPHY, or its
department names an imaging discipline (ultrasono, usg, x-ray, xray, radiolog, imaging), or its
report template is NARRATIVE (the imaging report type). "requires_doctor" / performing_role
DOCTOR alone no longer make a test imaging: a doctor-read tissue test still needs its specimen.

Used by: result template + result save (DRAFT and ENTERED), operational Complete, culture stage,
outsourced dispatch, Perform Scan (imaging only), the invoice sample status, the refund imaging
lock, the worklist IMAGING filter and the worklist item flags (requires_sample / is_imaging).
"""
from typing import Any, Optional

from sqlalchemy import func, or_

# Explicit "no sample needed" markers (compared trimmed and lower-cased). Empty is NOT a marker.
NO_SAMPLE_MARKERS = frozenset({"none", "n/a", "na", "no sample"})

# Lowercase fragments of department names that identify imaging investigations.
IMAGING_DEPARTMENT_HINTS = ("ultrasono", "usg", "x-ray", "xray", "radiolog", "imaging")
IMAGING_LAB_SECTIONS = frozenset({"ULTRASONOGRAPHY"})
IMAGING_REPORT_TEMPLATES = frozenset({"NARRATIVE"})

# Plain message shown to the user when a gate refuses an action before Sample Taken.
SAMPLE_REQUIRED_MESSAGE = "Take the sample before entering results: the specimen has not been collected yet. Record 'Sample Taken' first."
SAMPLE_REQUIRED_COMPLETE_MESSAGE = "Take the sample before completing this test: the specimen has not been collected yet. Record 'Sample Taken' first."
SAMPLE_REQUIRED_STAGE_MESSAGE = "Take the sample before this step: the specimen has not been collected yet. Record 'Sample Taken' first."


def is_explicit_no_sample(sample_type: Optional[str]) -> bool:
    """True only for an explicit catalog marker that the test needs no sample."""
    if sample_type is None:
        return False
    return sample_type.strip().lower() in NO_SAMPLE_MARKERS


def is_imaging_test(test: Any, order: Any = None) -> bool:
    """Imaging investigation (USG, X-ray, narrative imaging report). The only imaging definition.
    `order` is accepted for call-site compatibility; the decision depends on the test only."""
    if test is None:
        return False
    if (getattr(test, "lab_section", None) or "") in IMAGING_LAB_SECTIONS:
        return True
    if (getattr(test, "report_template", "") or "").upper() in IMAGING_REPORT_TEMPLATES:
        return True
    dept = (getattr(test, "department", "") or "").lower()
    return any(h in dept for h in IMAGING_DEPARTMENT_HINTS)


def imaging_sql_clause(test_model):
    """The same imaging definition as an SQL condition on the Test model (worklist filter)."""
    dept = func.lower(func.coalesce(test_model.department, ""))
    return or_(
        test_model.lab_section.in_(sorted(IMAGING_LAB_SECTIONS)),
        func.upper(func.coalesce(test_model.report_template, "")).in_(sorted(IMAGING_REPORT_TEMPLATES)),
        *[dept.contains(h) for h in IMAGING_DEPARTMENT_HINTS],
    )


def requires_sample(test: Any, order: Any = None) -> bool:
    """The one helper deciding whether a test order must have a collected sample."""
    if is_imaging_test(test, order):
        return False
    if order is not None and (getattr(order, "sample_route", "") or "").upper() == "FULL":
        return True
    sample_type = getattr(test, "sample_type", None) if test is not None else None
    if is_explicit_no_sample(sample_type):
        return False
    # NULL / empty = unknown = a sample IS required; any other value names a specimen.
    return True


def sample_collected(order: Any) -> bool:
    sample = getattr(order, "sample", None)
    return bool(sample is not None and sample.status == "COLLECTED")


def sample_gate_blocks(test: Any, order: Any) -> bool:
    """True when the order needs a sample and none has been collected yet."""
    return requires_sample(test, order) and not sample_collected(order)
