"""Prompt 10E Parts 2-5: sample_type normalization, payment channel detail, urgent fee,
business-day rows for the new channels (ROCKET, OTHER).

All changes are additive. Data steps:
- tests.sample_type values 'None' / 'N/A' / '' (any case) become NULL ("no sample").
- every OPEN business day gets zero-balance rows for any missing channel (ROCKET, OTHER, ...).

Revision ID: e8b2f4a6c1d3
Revises: d7e5a91c4f02
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa


revision = "e8b2f4a6c1d3"
down_revision = "d7e5a91c4f02"
branch_labels = None
depends_on = None

CHANNELS = ("CASH", "BKASH", "NAGAD", "ROCKET", "POS_CARD", "BANK_TRANSFER", "OTHER")


def upgrade() -> None:
    # Part 2: "None" strings mean no sample -> NULL (single representation)
    op.execute(
        "UPDATE tests SET sample_type = NULL "
        "WHERE sample_type IS NOT NULL AND lower(trim(sample_type)) IN ('none', 'n/a', '')"
    )

    # Part 4: free-text channel name for OTHER payments
    op.add_column("payments", sa.Column("channel_detail", sa.String(length=100), nullable=True))

    # Part 5: urgent fee (computed by the backend, part of net)
    op.add_column("invoices", sa.Column("urgent_fee", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("chk_invoice_urgent_fee_nonneg", "invoices", "urgent_fee >= 0")
    op.add_column("invoice_lines", sa.Column("urgent_fee", sa.Integer(), nullable=False, server_default="0"))

    # Part 4: open business days get rows for channels that did not exist when they opened
    bind = op.get_bind()
    open_days = bind.execute(sa.text("SELECT id, tenant_id FROM business_days WHERE status = 'OPEN'")).fetchall()
    bind.execute(sa.text(
        "SELECT setval('business_day_channel_balances_id_seq', "
        "COALESCE((SELECT MAX(id) FROM business_day_channel_balances), 1))"
    ))
    for day_id, tenant_id in open_days:
        present = {
            r[0] for r in bind.execute(
                sa.text("SELECT channel FROM business_day_channel_balances WHERE business_day_id = :d"), {"d": day_id}
            )
        }
        for ch in CHANNELS:
            if ch not in present:
                bind.execute(
                    sa.text(
                        "INSERT INTO business_day_channel_balances "
                        "(tenant_id, business_day_id, channel, opening_balance, received_amount) "
                        "VALUES (:t, :d, :c, 0, 0)"
                    ),
                    {"t": tenant_id, "d": day_id, "c": ch},
                )


def downgrade() -> None:
    # Zero-balance channel rows and the NULL sample types are kept (data is never wiped;
    # NULL and 'None' both mean "no sample").
    op.drop_column("invoice_lines", "urgent_fee")
    op.drop_constraint("chk_invoice_urgent_fee_nonneg", "invoices", type_="check")
    op.drop_column("invoices", "urgent_fee")
    op.drop_column("payments", "channel_detail")
