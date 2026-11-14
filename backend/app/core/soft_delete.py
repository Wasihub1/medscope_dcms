"""Prompt 11: the one soft-delete rule (Category A: User, Doctor, 3rd Party, Catalog Test).

A soft-deleted row keeps every column and every reference; it only carries
deleted_at / deleted_by_id / delete_reason and is hidden from NEW selection. "Deleted" is a
separate state from the existing `active` flag. History of delete/restore cycles is the
append-only audit log (SOFT_DELETE_* / RESTORE_* actions), not the row itself.
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

REASON_MAX_LEN = 500
REASON_PREFIX = "reason: "


def clean_reason(reason: Optional[str]) -> str:
    """Delete reason is mandatory: non-empty after trimming, at most 500 characters."""
    text = (reason or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to delete this item.")
    if len(text) > REASON_MAX_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The reason is too long (maximum {REASON_MAX_LEN} characters).",
        )
    return text


def is_deleted(row) -> bool:
    return getattr(row, "deleted_at", None) is not None


def audit_text_with_reason(summary: str, reason: Optional[str]) -> str:
    """Audit after_value text for delete rows; the reason is parsed back by extract_reason()."""
    return f"{summary} | {REASON_PREFIX}{reason}" if reason else summary


def extract_reason(text: Optional[str]) -> Optional[str]:
    if not text or REASON_PREFIX not in text:
        return None
    return text.split(REASON_PREFIX, 1)[1].strip() or None
