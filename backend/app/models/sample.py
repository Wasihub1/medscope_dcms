from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_orders.id"), nullable=False, unique=True, index=True)

    sample_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    temp_sample_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # Offline reconciliation
    sample_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="COLLECTED", nullable=False)  # COLLECTED, REJECTED, SPOILED

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    collected_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    # Module 12: Spoiled / Rejected Specimen Audit Fields
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejection_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="sample")
    collected_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[collected_by_id])
    rejected_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[rejected_by_id])

    __table_args__ = (
        Index("idx_sample_tenant_code", "tenant_id", "sample_code", unique=True),
    )

