"""Prompt 19B (Module 23): groups the free-text audit `action` strings into the business domains the Owner filters by.

`action` stays free text (no registry/enum). The grouping lives only here, in one place, as exact names plus
prefixes, and is applied both to filter rows (SQL) and to label each row (domain_of). An action that matches no
rule falls into "other", so no row is ever unreachable from the viewer.
"""
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, not_, or_
from sqlalchemy.sql.elements import ColumnElement

# key -> (label, exact action names, action prefixes). Order matters: the first matching rule labels a row.
DOMAINS: List[Tuple[str, str, Tuple[str, ...], Tuple[str, ...]]] = [
    ("discounts", "Discounts", (), ("INVOICE_DISCOUNT_",)),
    ("payments", "Payments & refunds", ("COLLECT_PATIENT_DUE", "COMMISSION_REVERSED", "PRE_LOCK_CANCELLATION", "INVOICE_INITIAL_PAYMENT"),
     ("REFUND_", "ADMIN_REVIEW_REFUND_", "INITIATE_", "DUE_")),
    ("bills", "Bills", ("CONFIRM_INVOICE", "SAVE_INVOICE_DRAFT", "UPDATE_INVOICE_DRAFT", "INVOICE_DRAFT_DISCARDED",
                        "INVOICE_LINE_UNLOCKED", "PRE_LOCK_INVOICE_CANCELLATION", "INVOICE_REPRINTED"), ()),
    ("reports", "Reports & results", ("DELIVER_REPORT",), ("REPORT_", "RESULT_", "DOCTOR_APPROV")),
    ("stock", "Stock", (), ("STOCK_",)),
    ("accounting", "Accounting & day close", ("POST_ADJUSTING_ENTRY",), ("OPEN_BUSINESS_DAY", "CLOSE_BUSINESS_DAY", "REOPEN_BUSINESS_DAY", "DAY_")),
    ("settings", "Settings", ("SETTING_CHANGED",), ()),
    ("permissions", "Users, permissions & sign-in", ("UPDATE_OWN_PROFILE",), ("AUTH_", "USER_", "ACCOUNT_")),
    ("lab", "Lab workflow", ("ASSIGN_TEST_ORDER", "REASSIGN_ROOM", "UPDATE_ORDER_STATUS", "IMAGING_PERFORMED", "PATIENT_CONTACTED"),
     ("SAMPLE_", "ORDER_", "CULTURE_", "OUTSOURCED_")),
    ("catalog", "Patients, referrers & catalog", ("CREATE_PATIENT", "UPDATE_REFERRER", "CREATE_REFERRER", "CREATE_BASIC_REFERRER",
                                       "TEST_SOFT_DELETED", "TEST_RESTORED"),
     ("REFERRER_", "REFERENCE_RANGE_")),
    ("audit", "Audit log itself", (), ("AUDIT_LOG_",)),
]
OTHER = ("other", "Other")


def domain_labels() -> List[Dict[str, str]]:
    return [{"key": k, "label": l} for k, l, _, _ in DOMAINS] + [{"key": OTHER[0], "label": OTHER[1]}]


def domain_of(action: str) -> str:
    for key, _, exact, prefixes in DOMAINS:
        if action in exact or any(action.startswith(p) for p in prefixes):
            return key
    return OTHER[0]


def _rule(column, exact, prefixes) -> ColumnElement:
    conds = []
    if exact:
        conds.append(column.in_(exact))
    conds.extend(column.startswith(p, autoescape=True) for p in prefixes)
    return or_(*conds)


def domain_condition(column, domain: str) -> Optional[ColumnElement]:
    """SQL condition selecting the rows of one domain, or None when the key is unknown."""
    if domain == OTHER[0]:
        return and_(*[not_(_rule(column, e, p)) for _, _, e, p in DOMAINS])
    for key, _, exact, prefixes in DOMAINS:
        if key == domain:
            # Same first-match-wins rule as domain_of(): exclude what an earlier domain already claimed.
            earlier = []
            for k2, _, e2, p2 in DOMAINS:
                if k2 == key:
                    break
                earlier.append(not_(_rule(column, e2, p2)))
            return and_(_rule(column, exact, prefixes), *earlier)
    return None
