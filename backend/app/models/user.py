from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="RECEPTIONIST", index=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # e.g. Hematology, Biochemical Tests
    # Prompt 10D: lab section / room code (backend/app/core/lab_sections.py); LAB_TECH only
    lab_section: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # Prompt 15: DOCTOR login -> its doctor profile (a referrers row holding name + registration no.)
    doctor_profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    # Prompt 11: soft delete (separate from `active`); NULL deleted_at = not deleted
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    delete_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Prompt 09: Credentials and lockout fields
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="staff_members")
    roles: Mapped[list["StaffRole"]] = relationship("StaffRole", back_populates="staff", cascade="all, delete-orphan")
    sessions: Mapped[list["AuthSession"]] = relationship("AuthSession", back_populates="staff", cascade="all, delete-orphan")
    permission_overrides: Mapped[list["StaffPermissionOverride"]] = relationship(
        "StaffPermissionOverride",
        back_populates="staff",
        cascade="all, delete-orphan",
        foreign_keys="StaffPermissionOverride.staff_id",
    )

    __table_args__ = (
        # Prompt 10E Part 7: a technician always belongs to a room
        CheckConstraint("role <> 'LAB_TECH' OR lab_section IS NOT NULL", name="chk_staff_lab_tech_has_section"),
    )

    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def is_locked(self) -> bool:
        return self.locked_at is not None


class StaffRole(Base):
    __tablename__ = "staff_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    staff: Mapped["Staff"] = relationship("Staff", back_populates="roles")

    __table_args__ = (
        UniqueConstraint("staff_id", "role", name="uq_staff_roles_staff_id_role"),
        # Prompt 10D: one login = one fixed role
        UniqueConstraint("staff_id", name="uq_staff_roles_staff_id"),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    acting_role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    staff: Mapped["Staff"] = relationship("Staff", back_populates="sessions")


class StaffPermissionOverride(Base):
    """Prompt 10D: per-user permission grant (granted=True) or revoke (granted=False)
    applied on top of the role defaults in backend/app/core/permissions.py."""
    __tablename__ = "staff_permission_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_key: Mapped[str] = mapped_column(String(100), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    staff: Mapped["Staff"] = relationship("Staff", back_populates="permission_overrides", foreign_keys=[staff_id])

    __table_args__ = (
        UniqueConstraint("staff_id", "permission_key", name="uq_staff_permission_override"),
    )
