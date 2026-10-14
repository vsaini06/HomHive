from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research.api import build_research_router
from app.research.models import ResearchEvidence, ResearchResult
from app.research.service import ResearchService


class FakeProvider:
    def search(self, request):
        return ResearchResult(
            query=request.query,
            purpose=request.purpose,
            evidence=[
                ResearchEvidence(
                    title="Guide",
                    url="https://example.com/guide",
                    content="Visible plant care guidance.",
                    score=0.8,
                )
            ],
            request_id="req-1",
        )


def test_research_endpoint_is_household_authorized():
    app = FastAPI()
    app.include_router(
        build_research_router(
            ResearchService(FakeProvider()),
            {"home": "secret"},
        )
    )

    with TestClient(app) as client:
        denied = client.post(
            "/households/home/research",
            json={"query": "Monstera watering", "purpose": "plant_care"},
        )
        allowed = client.post(
            "/households/home/research",
            headers={"Authorization": "Bearer secret"},
            json={"query": "Monstera watering", "purpose": "plant_care"},
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["evidence"][0]["title"] == "Guide"
