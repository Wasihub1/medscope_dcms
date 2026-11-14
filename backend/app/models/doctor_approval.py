from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class DoctorApproval(Base):
    """
    Prompt 15 (D22): the doctor-side signature on one test order's result.

    - approved_by_user_id = the staff login that actually clicked Approve (audit truth).
    - doctor_id = the doctor (referrers row) the approval is attributed to. It is the DOCTOR user's own
      profile in Path B, or the doctor selected by Admin/Owner in Path A (visiting doctors have no login).
    - is_attestation = True when staff recorded it on the doctor's behalf (Path A).
    - doctor_name / doctor_registration_no are snapshots, so the eventual report prints what was approved
      even if the doctor's profile is edited later.
    The technician's own sign-off stays on results.entered_by_id / entered_at (Module 13); this row is
    stored beside it, never over it. One approval per test order (append-only; no update or delete path).
    """
    __tablename__ = "doctor_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_orders.id"), nullable=False)
    result_id: Mapped[int] = mapped_column(Integer, ForeignKey("results.id"), nullable=False)
    approval_rule: Mapped[str] = mapped_column(String(50), nullable=False)  # DOCTOR_REQUIRED, BOTH_SIGNATURES (rule at the time)

    doctor_id: Mapped[int] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=False, index=True)
    doctor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    doctor_registration_no: Mapped[str] = mapped_column(String(100), nullable=False)

    approved_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False, index=True)
    approved_by_role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_attestation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    test_order: Mapped["TestOrder"] = relationship("TestOrder", back_populates="doctor_approval")
    doctor: Mapped["Referrer"] = relationship("Referrer")
    approved_by: Mapped["Staff"] = relationship("Staff", foreign_keys=[approved_by_user_id])

    __table_args__ = (
        UniqueConstraint("test_order_id", name="uq_doctor_approvals_test_order_id"),
        Index("idx_doctor_approvals_tenant_doctor", "tenant_id", "doctor_id"),
    )
