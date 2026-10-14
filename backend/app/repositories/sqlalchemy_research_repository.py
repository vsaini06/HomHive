from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.db.research_cache_record import ResearchCacheRecord
from app.research.models import ResearchResult


class SQLAlchemyResearchRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def find_cached(
        self,
        household_id: str,
        cache_key: str,
        now: datetime,
    ) -> ResearchResult | None:
        with self._session_factory() as session:
            record = session.get(ResearchCacheRecord, (household_id, cache_key))
            if record is None:
                return None
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return None
            return ResearchResult.model_validate(record.result)

    def save_cached(
        self,
        household_id: str,
        cache_key: str,
        result: ResearchResult,
        expires_at: datetime,
    ) -> ResearchResult:
        now = datetime.now(timezone.utc)
        with self._session_factory.begin() as session:
            record = session.get(ResearchCacheRecord, (household_id, cache_key))
            payload = result.model_dump(mode="json")
            if record is None:
                record = ResearchCacheRecord(
                    household_id=household_id,
                    cache_key=cache_key,
                    purpose=result.purpose.value,
                    query=result.query,
                    result=payload,
                    created_at=now,
                    expires_at=expires_at,
                )
                session.add(record)
            else:
                record.purpose = result.purpose.value
                record.query = result.query
                record.result = payload
                record.created_at = now
                record.expires_at = expires_at
            session.flush()
        return result.model_copy(deep=True)
