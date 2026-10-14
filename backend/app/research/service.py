from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app.repositories.research_storage import ResearchStorage

from .models import ResearchRequest, ResearchResult
from .provider import ResearchProvider


def research_cache_key(request: ResearchRequest) -> str:
    normalized = " ".join(request.query.lower().split())
    raw = f"{request.purpose.value}:{normalized}".encode("utf-8")
    return sha256(raw).hexdigest()


class ResearchService:
    def __init__(
        self,
        provider: ResearchProvider,
        storage: ResearchStorage | None = None,
        cache_ttl: timedelta = timedelta(hours=24),
    ):
        self._provider = provider
        self._storage = storage
        self._cache_ttl = cache_ttl

    def research(self, household_id: str, request: ResearchRequest) -> ResearchResult:
        if not household_id:
            raise ValueError("household_id must not be empty")

        now = datetime.now(timezone.utc)
        cache_key = research_cache_key(request)

        if self._storage is not None:
            cached = self._storage.find_cached(household_id, cache_key, now)
            if cached is not None:
                return cached

        result = self._provider.search(request)

        if self._storage is not None:
            self._storage.save_cached(
                household_id,
                cache_key,
                result,
                now + self._cache_ttl,
            )

        return result
