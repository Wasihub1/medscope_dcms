from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, Index, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Result(Base):
    """
    Module 13: Laboratory & Diagnostic Result Record.
    Associated 1-to-1 with TestOrder.
    Supports NUMERIC_TABLE, NARRATIVE, ULTRASOUND, CULTURE_SENSITIVITY.
    """
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_orders.id"), nullable=False, index=True)

    result_type: Mapped[str] = mapped_column(String(50), default="NUMERIC_TABLE", nullable=False)
    # NUMERIC_TABLE, NARRATIVE, ULTRASOUND, CULTURE_SENSITIVITY
    status: Mapped[str] = mapped_column(String(50), default="ENTERED", nullable=False)
    # DRAFT, ENTERED

    # Narrative & Ultrasound report fields
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Structured organ observations (e.g. USG)

    entered_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="result")
    entered_by: Mapped["Staff"] = relationship("Staff", foreign_keys=[entered_by_id])
    items: Mapped[list["ResultItem"]] = relationship("ResultItem", back_populates="result", cascade="all, delete-orphan", order_by="ResultItem.sort_order")

    __table_args__ = (
        UniqueConstraint("test_order_id", name="uq_results_test_order_id"),
        Index("idx_result_tenant_order", "tenant_id", "test_order_id"),
    )


class ResultItem(Base):
    """
    Module 13: Individual numeric / component result row with historical reference range snapshot
    and automatic flag (LOW, HIGH, CRITICAL, NORMAL).
    Preserves D24 invariant: later changes to a test's reference range will never alter
    an already-entered historical result.
    """
    __tablename__ = "result_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result_id: Mapped[int] = mapped_column(Integer, ForeignKey("results.id", ondelete="CASCADE"), nullable=False, index=True)
    test_component_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("test_components.id"), nullable=True)

    component_name: Mapped[str] = mapped_column(String(200), nullable=False)
    component_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Reference range snapshot at time of result entry (D24 invariant)
    reference_range: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ref_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    critical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    impossible_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    impossible_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    flag: Mapped[str | None] = mapped_column(String(50), nullable=True)  # NORMAL, LOW, HIGH, CRITICAL, None
    comment: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    result: Mapped["Result"] = relationship("Result", back_populates="items")
    component: Mapped["TestComponent | None"] = relationship("TestComponent")

    __table_args__ = (
        Index("idx_result_item_tenant_result", "tenant_id", "result_id", "sort_order"),
    )

