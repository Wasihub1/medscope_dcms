from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class TestOrder(Base):
    __tablename__ = "test_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invoice_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoice_lines.id"), nullable=False, unique=True, index=True)

    status: Mapped[str] = mapped_column(String(50), default="UNASSIGNED", nullable=False, index=True)
    # Workflow states: UNASSIGNED, ASSIGNED, PENDING, SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, COMPLETED, CANCELLED, REJECTED, SPOILED

    urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    performing_role: Mapped[str] = mapped_column(String(50), default="LAB_TECH", nullable=False)  # LAB_TECH, DOCTOR
    turnaround_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_route: Mapped[str] = mapped_column(String(20), default="QUICK", nullable=False)  # QUICK, FULL
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. NOT_PERFORMED under D15

    # Module 12: Specimen Lifecycle & Department Workflow Extensions
    patient_followup_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    patient_contact_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # PENDING_CALL, CALLED, RECOLLECTION_AGREED, REFUND_REQUESTED
    patient_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient_contact_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    culture_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)  # INCUBATING, PRELIMINARY, FINAL
    outsourced_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SENT, RECEIVED
    outsourced_lab_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outsourced_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outsourced_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outsourced_ref_no: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Prompt 10E Part 7: routing target is a room (lab section), never one technician.
    # assigned_to_id only records who actually acted; it is not used for visibility.
    lab_section: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    assigned_to_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    assigned_destination: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    # Prompt 15 (D22): the doctor (referrers row) whose queue this order sits in for doctor approval.
    # Set by Admin/Owner; a DOCTOR login only sees orders assigned to their own doctor profile.
    assigned_doctor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    invoice_line: Mapped["InvoiceLine"] = relationship("InvoiceLine", back_populates="test_order")
    doctor_approval: Mapped["DoctorApproval | None"] = relationship("DoctorApproval", back_populates="test_order", uselist=False)
    assigned_to: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[assigned_to_id])
    assigned_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[assigned_by_id])
    sample: Mapped["Sample | None"] = relationship("Sample", back_populates="test_order", uselist=False)
    result: Mapped["Result | None"] = relationship("Result", back_populates="test_order", uselist=False)
    report_version: Mapped["ReportVersion | None"] = relationship("ReportVersion", back_populates="test_order", uselist=False)
    assignment_logs: Mapped[list["AssignmentHistory"]] = relationship("AssignmentHistory", back_populates="test_order")
    events: Mapped[list["TestOrderEvent"]] = relationship("TestOrderEvent", back_populates="test_order", cascade="all, delete-orphan", order_by="TestOrderEvent.created_at")


class TestOrderEvent(Base):
    """
    Append-only timestamped operational history for test orders and specimens (Prompt 06 Module 12).
    Preserves stage transitions, timestamps, responsible actors, and clinical notes.
    """
    __tablename__ = "test_order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_orders.id"), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Event types: SAMPLE_CREATED, SAMPLE_COLLECTED, SAMPLE_REJECTED, SAMPLE_SPOILED,
    # PROCESSING_STARTED, IMAGING_PERFORMED, AWAITING_DOCTOR,
    # CULTURE_INCUBATING, CULTURE_PRELIMINARY, CULTURE_FINAL,
    # OUTSOURCED_SENT, OUTSOURCED_RECEIVED, COMPLETED, PATIENT_CONTACTED, STATUS_CHANGED

    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    actor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="events")
    actor: Mapped["Staff | None"] = relationship("Staff")

    __table_args__ = (
        Index("idx_order_events_tenant_order", "tenant_id", "test_order_id", "created_at"),
    )


class AssignmentHistory(Base):
    __tablename__ = "assignment_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_orders.id"), nullable=False, index=True)

    previous_assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_assignee: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    changed_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="assignment_logs")
    changed_by: Mapped["Staff"] = relationship("Staff")

