from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.research_cache_record import ResearchCacheRecord
from app.repositories.in_memory_research_repository import InMemoryResearchRepository
from app.repositories.sqlalchemy_research_repository import SQLAlchemyResearchRepository
from app.research import ResearchEvidence, ResearchPurpose, ResearchRequest, ResearchResult
from app.research.service import ResearchService


class CountingProvider:
    def __init__(self):
        self.calls = 0

    def search(self, request):
        self.calls += 1
        return ResearchResult(
            query=request.query,
            purpose=request.purpose,
            evidence=[
                ResearchEvidence(
                    title="Guide",
                    url="https://example.com/guide",
                    content="Evidence",
                    score=0.9,
                )
            ],
            request_id=f"request-{self.calls}",
        )


def request():
    return ResearchRequest(
        query="Monstera watering guidance",
        purpose=ResearchPurpose.PLANT_CARE,
    )


def test_research_service_reuses_household_scoped_cache():
    provider = CountingProvider()
    service = ResearchService(provider, InMemoryResearchRepository())

    first = service.research("home", request())
    second = service.research("home", request())

    assert provider.calls == 1
    assert second.request_id == first.request_id


def test_research_cache_does_not_cross_households():
    provider = CountingProvider()
    service = ResearchService(provider, InMemoryResearchRepository())

    service.research("home-one", request())
    service.research("home-two", request())

    assert provider.calls == 2


def test_sql_research_cache_survives_repository_instances(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'research.sqlite3'}")
    Base.metadata.create_all(engine, tables=[ResearchCacheRecord.__table__])
    sessions = sessionmaker(engine, expire_on_commit=False)
    provider = CountingProvider()

    ResearchService(
        provider,
        SQLAlchemyResearchRepository(sessions),
        cache_ttl=timedelta(hours=1),
    ).research("home", request())

    restored = ResearchService(
        provider,
        SQLAlchemyResearchRepository(sessions),
        cache_ttl=timedelta(hours=1),
    ).research("home", request())

    assert provider.calls == 1
    assert restored.request_id == "request-1"
    engine.dispose()
