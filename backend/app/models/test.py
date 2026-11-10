from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, Index
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
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

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

    reference_range_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ref_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    impossible_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    impossible_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    test: Mapped["Test"] = relationship("Test", back_populates="components")

    __table_args__ = (
        Index("idx_test_comp_tenant_test", "tenant_id", "test_id", "sort_order"),
    )


class TestDestination(Base):
    __tablename__ = "test_destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Technician") # Technician, Room, Lab
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


