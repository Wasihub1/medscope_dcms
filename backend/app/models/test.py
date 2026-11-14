from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alternate_names: Mapped[str | None] = mapped_column(String(300), nullable=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # Whole-Taka integer
    sample_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    turnaround_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)  # TAT in hours for clocks
    performing_role: Mapped[str] = mapped_column(String(50), default="LAB_TECH", nullable=False)  # LAB_TECH, DOCTOR, RADIOLOGIST
    requires_doctor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # e.g. USG awaiting doctor
    report_template: Mapped[str] = mapped_column(String(50), default="NUMERIC_TABLE", nullable=False)  # NUMERIC_TABLE, NARRATIVE, CULTURE_SENSITIVITY, HISTOPATHOLOGY
    approval_rule: Mapped[str] = mapped_column(String(50), default="TECHNICIAN_FINAL", nullable=False)  # TECHNICIAN_FINAL, DOCTOR_REQUIRED, BOTH_SIGNATURES
    is_outsourced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Prompt 10E Part 7: lab room the test is routed to (backend/app/core/lab_sections.py); NULL = no room
    lab_section: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    # Prompt 11: soft delete (separate from `active`); NULL deleted_at = not deleted
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    components: Mapped[list["TestComponent"]] = relationship("TestComponent", back_populates="test", cascade="all, delete-orphan", order_by="TestComponent.sort_order")

    __table_args__ = (
        Index("idx_test_tenant_code", "tenant_id", "code", unique=True),
        Index("idx_test_tenant_name", "tenant_id", "name"),
        Index("idx_test_tenant_department", "tenant_id", "department"),
    )


class TestComponent(Base):
    """
    Module 13: Configurable components / parameters for tests with reference ranges,
    critical limits, and impossible-value limits.
    """
    __tablename__ = "test_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_id: Mapped[int] = mapped_column(Integer, ForeignKey("tests.id"), nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Prompt 14 (D24): reference ranges and critical limits live in `reference_range_versions`
    # (by sex and age band in days). Only the impossible-value limits stay on the component.
    impossible_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    impossible_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    test: Mapped["Test"] = relationship("Test", back_populates="components")
    range_versions: Mapped[list["ReferenceRangeVersion"]] = relationship(
        "ReferenceRangeVersion", back_populates="component", order_by="ReferenceRangeVersion.id"
    )

    __table_args__ = (
        Index("idx_test_comp_tenant_test", "tenant_id", "test_id", "sort_order"),
    )


class ReferenceRangeVersion(Base):
    """
    Prompt 14 (D24): one reference-range BAND of a test component, versioned.
    A band = (sex, age_days_min..age_days_max, inclusive; max NULL = no upper limit). Changing a band never
    edits a row: a new row with version_no + 1 is added and the old row is marked not current
    (retired_at set). Result items snapshot the values used at entry, so history never changes.
    sex: 'ANY' (no sex dependence), 'MALE' or 'FEMALE'.
    """
    __tablename__ = "reference_range_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_component_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_components.id"), nullable=False, index=True)

    sex: Mapped[str] = mapped_column(String(10), nullable=False, default="ANY")
    age_days_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    age_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ref_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_range_text: Mapped[str | None] = mapped_column(String(200), nullable=True)

    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    component: Mapped["TestComponent"] = relationship("TestComponent", back_populates="range_versions")

    __table_args__ = (
        Index("idx_range_version_comp_current", "tenant_id", "test_component_id", "is_current"),
        # one current band per (component, sex, band start)
        Index(
            "uq_range_version_current_band", "test_component_id", "sex", "age_days_min",
            unique=True, postgresql_where=text("is_current"),
        ),
    )


class TestDestination(Base):
    __tablename__ = "test_destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Technician") # Technician, Room, Lab
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


