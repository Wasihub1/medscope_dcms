from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Integer, ForeignKey, Index, UniqueConstraint, CheckConstraint, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Account(Base):
    """Prompt 18 (Module 21): chart of accounts. Only the accounts the real postings need (seeded per tenant by
    accounting_service.ensure_accounts). type: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE."""
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_accounts_tenant_code"),)


class JournalEntry(Base):
    """Prompt 18: one balanced double-entry event. Append-only (database trigger blocks UPDATE / DELETE);
    a mistake is fixed by a new entry whose reverses_entry_id points at the original."""
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    business_day_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("business_days.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reverses_entry_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("journal_entries.id"), nullable=True)
    is_adjustment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    lines: Mapped[list["JournalLine"]] = relationship("JournalLine", back_populates="entry", order_by="JournalLine.id")

    __table_args__ = (
        Index("idx_journal_entry_tenant_date", "tenant_id", "entry_date"),
        Index("idx_journal_entry_source", "tenant_id", "source_type", "source_id"),
        UniqueConstraint("reverses_entry_id", name="uq_journal_entry_reverses"),
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entry_id: Mapped[int] = mapped_column(Integer, ForeignKey("journal_entries.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    debit: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    credit: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Reserved so a later commission module can post per-referrer lines; nothing writes it yet.
    referrer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=True, index=True)

    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["Account"] = relationship("Account")

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0 AND (debit = 0 OR credit = 0) AND (debit + credit) > 0", name="chk_journal_line_one_side"),
    )


class DayMovement(Base):
    """Prompt 18 (D48): a cash movement entered from the day screen: BANK_DEPOSIT, OWNER_WITHDRAWAL or EXPENSE.
    All three are cash leaving the drawer, so each lowers the expected cash (D45). Never edited or deleted."""
    __tablename__ = "day_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_day_id: Mapped[int] = mapped_column(Integer, ForeignKey("business_days.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    journal_entry_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("journal_entries.id"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (CheckConstraint("amount > 0", name="chk_day_movement_amount_pos"),)
