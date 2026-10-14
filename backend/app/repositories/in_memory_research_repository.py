from datetime import datetime

from app.research.models import ResearchResult


class InMemoryResearchRepository:
    def __init__(self):
        self._entries: dict[tuple[str, str], tuple[ResearchResult, datetime]] = {}

    def find_cached(
        self,
        household_id: str,
        cache_key: str,
        now: datetime,
    ) -> ResearchResult | None:
        entry = self._entries.get((household_id, cache_key))
        if entry is None:
            return None
        result, expires_at = entry
        if expires_at <= now:
            return None
        return result.model_copy(deep=True)

    def save_cached(
        self,
        household_id: str,
        cache_key: str,
        result: ResearchResult,
        expires_at: datetime,
    ) -> ResearchResult:
        self._entries[(household_id, cache_key)] = (result.model_copy(deep=True), expires_at)
        return result.model_copy(deep=True)
