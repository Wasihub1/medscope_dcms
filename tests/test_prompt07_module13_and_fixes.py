import pytest
from fastapi import HTTPException
from backend.app.services.result_service import validate_and_compute_flag


class MockComponent:
    def __init__(
        self,
        name="Hemoglobin",
        unit="g/dL",
        ref_min=12.0,
        ref_max=16.0,
        critical_min=7.0,
        critical_max=20.0,
        impossible_min=2.0,
        impossible_max=25.0,
    ):
        self.name = name
        self.unit = unit
        self.ref_min = ref_min
        self.ref_max = ref_max
        self.critical_min = critical_min
        self.critical_max = critical_max
        self.impossible_min = impossible_min
        self.impossible_max = impossible_max


def test_compute_flag_normal_range():
    comp = MockComponent()
    val, flag = validate_and_compute_flag(comp, "14.0")
    assert val == 14.0
    assert flag == "NORMAL"


def test_compute_flag_low_and_high():
    comp = MockComponent()
    # Below normal, above critical min
    val_low, flag_low = validate_and_compute_flag(comp, "10.5")
    assert val_low == 10.5
    assert flag_low == "LOW"

    # Above normal, below critical max
    val_high, flag_high = validate_and_compute_flag(comp, "18.0")
    assert val_high == 18.0
    assert flag_high == "HIGH"


def test_compute_flag_critical_bounds():
    comp = MockComponent()
    # Severe low below critical_min 7.0
    val_crit_low, flag_crit_low = validate_and_compute_flag(comp, "6.0")
    assert val_crit_low == 6.0
    assert flag_crit_low == "CRITICAL"

    # Severe high above critical_max 20.0
    val_crit_high, flag_crit_high = validate_and_compute_flag(comp, "21.5")
    assert val_crit_high == 21.5
    assert flag_crit_high == "CRITICAL"


def test_compute_flag_safe_none_fallback():
    # Missing / partial ranges must NEVER silently default to NORMAL; must remain None
    comp_empty = MockComponent(ref_min=None, ref_max=None, critical_min=None, critical_max=None)
    val_empty, flag_empty = validate_and_compute_flag(comp_empty, "14.0")
    assert val_empty == 14.0
    assert flag_empty is None

    # None component object
    val_none_comp, flag_none_comp = validate_and_compute_flag(None, "14.0")
    assert val_none_comp == 14.0
    assert flag_none_comp is None


def test_validate_impossible_limits_valid():
    comp = MockComponent(impossible_min=2.0, impossible_max=25.0)
    # Realistic Hemoglobin 13.5 within (2.0, 25.0)
    val, flag = validate_and_compute_flag(comp, "13.5")
    assert val == 13.5
    assert flag == "NORMAL"


def test_validate_impossible_limits_high_rejection():
    comp = MockComponent(impossible_min=2.0, impossible_max=25.0)
    # Absurd Hemoglobin 150.0 exceeding impossible_max 25.0
    with pytest.raises(HTTPException) as exc_info:
        validate_and_compute_flag(comp, "150.0")
    assert exc_info.value.status_code == 400
    assert "exceeds the physiologically impossible maximum limit" in exc_info.value.detail


def test_validate_impossible_limits_low_rejection():
    comp = MockComponent(name="Potassium", unit="mmol/L", impossible_min=0.5, impossible_max=12.0)
    # Negative potassium or below impossible_min 0.5
    with pytest.raises(HTTPException) as exc_info:
        validate_and_compute_flag(comp, "0.1")
    assert exc_info.value.status_code == 400
    assert "below the physiologically impossible minimum limit" in exc_info.value.detail


def test_non_numeric_text():
    comp = MockComponent()
    val, flag = validate_and_compute_flag(comp, "Trace")
    assert val is None
    assert flag is None
