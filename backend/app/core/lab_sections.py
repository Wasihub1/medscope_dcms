"""
MedScope DCMS — Lab sections / rooms (Prompt 10D Part 5, routing added in Prompt 10E Part 7).

Single definition of the laboratory rooms AND of the test -> room mapping.

Principle (Prompt 10E): a test is routed to a ROOM (lab section), never to one specific
technician. Every active LAB_TECH whose staff.lab_section equals the order's room sees and
can work the order. A LAB_TECH must belong to exactly one room.

To change which catalog values go to which room, edit SECTION_KEYWORDS below (one place).
The mapping does not depend on the free-text tests.performing_role being exactly "LAB_TECH".
"""
from typing import Any, Dict, Optional

LAB_SECTIONS: Dict[str, Dict[str, str]] = {
    "HEMATOLOGY": {"name": "Hematology", "room": "Room 101", "department": "Hematology", "destination": "Hematology Room 101"},
    "BIOCHEMISTRY": {"name": "Biochemistry", "room": "Room 102", "department": "Biochemical Tests", "destination": "Biochemistry Room 102"},
    "MICROBIOLOGY": {"name": "Microbiology", "room": "Room 105", "department": "Microbiology", "destination": "Microbiology Lab 105"},
    "ULTRASONOGRAPHY": {"name": "Ultrasonography", "room": "Room 204", "department": "Ultrasonogram", "destination": "Ultrasonography Room 204"},
}

# Lower-case keyword fragments matched against the catalog's free text (default_assignee,
# department, performing_role). First the room destination names are tried, then these.
# Examples covered: "Hematology", "Hematopathologist"; "Biochemistry", "Biochemical Tests",
# "Clinical Biochemist"; "Microbiology", "Microbiology & Parasitology", "Microbiologist";
# "Ultrasonography (USG)", "Ultrasonogram", "USG Technician / Radiologist".
SECTION_KEYWORDS: Dict[str, tuple] = {
    "HEMATOLOGY": ("hematolog", "haematolog", "hematopatholog"),
    "BIOCHEMISTRY": ("biochem",),
    "MICROBIOLOGY": ("microbiolog",),
    "ULTRASONOGRAPHY": ("ultrasono", "usg"),
}


def is_valid_lab_section(code: Optional[str]) -> bool:
    return code is None or code in LAB_SECTIONS


def lab_section_label(code: Optional[str]) -> Optional[str]:
    if not code or code not in LAB_SECTIONS:
        return None
    s = LAB_SECTIONS[code]
    return f"{s['name']} — {s['room']}"


def lab_section_destination(code: Optional[str]) -> Optional[str]:
    """Human room name stored in test_orders.assigned_destination (e.g. 'Microbiology Lab 105')."""
    if not code or code not in LAB_SECTIONS:
        return None
    return LAB_SECTIONS[code]["destination"]


def section_from_text(value: Optional[str]) -> Optional[str]:
    """Maps one free-text value (a room/destination name, department or role label) to a room."""
    v = (value or "").strip().lower()
    if not v:
        return None
    if v.upper() in LAB_SECTIONS:
        return v.upper()
    for code, sec in LAB_SECTIONS.items():
        if v == sec["destination"].lower() or v == sec["room"].lower():
            return code
    for code, words in SECTION_KEYWORDS.items():
        if any(w in v for w in words):
            return code
    return None


def section_for_test_fields(
    department: Optional[str],
    default_assignee: Optional[str] = None,
    performing_role: Optional[str] = None,
) -> Optional[str]:
    """Room for a catalog test from its free-text fields. Order of evidence:
    1. default_assignee (an explicit room such as 'Biochemistry Room 102'),
    2. department, 3. performing_role label. Returns None when no room matches
    (the order is then routed as UNASSIGNED)."""
    for value in (default_assignee, department, performing_role):
        code = section_from_text(value)
        if code:
            return code
    return None


def section_for_test(test: Any) -> Optional[str]:
    """Room for a Test row: the stored tests.lab_section when set, else the mapping."""
    if test is None:
        return None
    stored = getattr(test, "lab_section", None)
    if stored in LAB_SECTIONS:
        return stored
    return section_for_test_fields(
        getattr(test, "department", None),
        getattr(test, "default_assignee", None),
        getattr(test, "performing_role", None),
    )
