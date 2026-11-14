"""
MedScope DCMS — payment channels (Prompt 10E Part 4). Single source of truth.

Channels: CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER.
- The UI label "Card" is POS_CARD (the old frontend value CARD is accepted as an alias).
- OTHER requires a free-text channel name typed by the cashier (payments.channel_detail).
  OTHER is one business-day balance bucket; the name is stored per payment.
- Every non-cash channel requires a transaction reference (unchanged rule).
"""
from typing import Optional, Tuple

from fastapi import HTTPException, status

PAYMENT_CHANNELS: tuple[str, ...] = ("CASH", "BKASH", "NAGAD", "ROCKET", "POS_CARD", "BANK_TRANSFER", "OTHER")

CHANNEL_LABELS = {
    "CASH": "Cash",
    "BKASH": "bKash",
    "NAGAD": "Nagad",
    "ROCKET": "Rocket",
    "POS_CARD": "Card",
    "BANK_TRANSFER": "Bank Transfer",
    "OTHER": "Other",
}

_ALIASES = {"CARD": "POS_CARD", "POS": "POS_CARD", "BANK": "BANK_TRANSFER"}

CHANNEL_DETAIL_MAX = 100


def normalize_channel(method: Optional[str]) -> str:
    m = (method or "CASH").strip().upper()
    return _ALIASES.get(m, m)


def validate_channel(method: Optional[str], channel_detail: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Returns (channel, channel_detail) or raises HTTP 400.
    OTHER needs a typed channel name; other channels never carry one."""
    ch = normalize_channel(method)
    if ch not in PAYMENT_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown payment channel '{method}'. Valid channels: {', '.join(PAYMENT_CHANNELS)}.",
        )
    detail = (channel_detail or "").strip() or None
    if ch == "OTHER":
        if not detail or len(detail) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment channel OTHER requires the channel name (type the name of the payment method).",
            )
        if len(detail) > CHANNEL_DETAIL_MAX:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel name is too long (max {CHANNEL_DETAIL_MAX} characters).",
            )
        return ch, detail
    return ch, None


def channel_display(method: Optional[str], channel_detail: Optional[str] = None) -> str:
    ch = normalize_channel(method)
    label = CHANNEL_LABELS.get(ch, ch)
    if ch == "OTHER" and channel_detail:
        return f"Other ({channel_detail})"
    return label
