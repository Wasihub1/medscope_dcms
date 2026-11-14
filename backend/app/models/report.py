from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Index, Text, JSON, event, text
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

    # Prompt 16 (Module 14): the Final report content. issued_at / issued_by_id are the finalization
    # time and user. status FINAL_AUTHORIZED is the Final state (the Draft state lives on results.status;
    # no report_versions row exists for a draft). content_snapshot is the money-free result preview as it
    # was at finalization (built from the result items' own D24 snapshots); signatures holds the text
    # signature data (technician and doctor name, doctor registration number, approval details).
    # NULL on the seeded pre-Module-14 rows. Immutable once written (guard below + DB trigger).
    result_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("results.id"), nullable=True)
    approval_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    doctor_approval_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("doctor_approvals.id"), nullable=True)
    content_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signatures: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="report_version")
    issued_by: Mapped["Staff | None"] = relationship("Staff")
    deliveries: Mapped[list["ReportDelivery"]] = relationship("ReportDelivery", back_populates="report_version")

    __table_args__ = (
        Index("idx_report_tenant_no", "tenant_id", "report_no"),
        # One Final report per test order for now (Module 15 corrections will add versions later).
        Index("uq_report_versions_final_per_order", "test_order_id", unique=True,
              postgresql_where=text("status = 'FINAL_AUTHORIZED'")),
    )


IMMUTABLE_REPORT_COLUMNS = (
    "test_order_id", "report_no", "version", "findings_summary", "issued_at", "issued_by_id",
    "result_id", "approval_rule", "doctor_approval_id", "content_snapshot", "signatures",
)


@event.listens_for(ReportVersion, "before_update")
def _report_version_is_immutable(mapper, connection, target):
    """Prompt 16: the stored content of a report version can never be changed (Module 15 will add a
    new version instead). Status / authorized stay changeable for later Superseded / Cancelled handling.
    The database trigger report_versions_immutable enforces the same rule for any other writer."""
    from sqlalchemy import inspect as sa_inspect
    state = sa_inspect(target)
    for col in IMMUTABLE_REPORT_COLUMNS:
        if state.attrs[col].history.has_changes():
            raise ValueError(f"A report version is immutable: '{col}' cannot be changed.")


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



class NotificationLog(Base):
    """Prompt 16 (placeholder for Module 25 / D63): a report-ready SMS is DUE when a report becomes Final.
    Nothing is sent: the row only records that a notification is owed (status PENDING_INTEGRATION).
    The patient is referenced by id; no phone number or message text is stored here."""
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # REPORT_READY_SMS
    status: Mapped[str] = mapped_column(String(30), default="PENDING_INTEGRATION", nullable=False)
    report_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_versions.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
