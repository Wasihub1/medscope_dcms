from typing import List, Optional
from pydantic import BaseModel


class SearchResultItem(BaseModel):
    id: str | int
    category: str  # PATIENT, INVOICE, TEST, REPORT
    title: str
    subtitle: str
    badge: Optional[str] = None
    navigation_url: str


class GlobalSearchResponse(BaseModel):
    query: str
    total_matches: int
    patients: List[SearchResultItem]
    invoices: List[SearchResultItem]
    tests: List[SearchResultItem]
    reports: List[SearchResultItem]
    samples: List[SearchResultItem] = []

