from datetime import datetime
from typing import Protocol, runtime_checkable

from app.research.models import ResearchResult


@runtime_checkable
class ResearchStorage(Protocol):
    def find_cached(
        self,
        household_id: str,
        cache_key: str,
        now: datetime,
    ) -> ResearchResult | None:
        ...

    def save_cached(
        self,
        household_id: str,
        cache_key: str,
        result: ResearchResult,
        expires_at: datetime,
    ) -> ResearchResult:
        ...
