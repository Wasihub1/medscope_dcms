from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_orders.id"), nullable=False, index=True)

    report_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    findings_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="FINAL_AUTHORIZED", nullable=False) # DRAFT, FINAL_AUTHORIZED
    authorized: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    issued_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="report_version")
    issued_by: Mapped["Staff | None"] = relationship("Staff")
    deliveries: Mapped[list["ReportDelivery"]] = relationship("ReportDelivery", back_populates="report_version")

    __table_args__ = (
        Index("idx_report_tenant_no", "tenant_id", "report_no"),
    )


class ReportDelivery(Base):
    __tablename__ = "report_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_versions.id"), nullable=False, index=True)

    delivered_to_name: Mapped[str] = mapped_column(String(150), nullable=False)
    delivered_to_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivered_to_relation: Mapped[str] = mapped_column(String(50), default="Self", nullable=False) # Self, Father, Mother, Spouse, Relative, Other

    delivered_with_due: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_release_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    delivered_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)

    report_version: Mapped["ReportVersion"] = relationship("ReportVersion", back_populates="deliveries")
    delivered_by: Mapped["Staff"] = relationship("Staff")

