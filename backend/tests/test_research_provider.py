import httpx
import pytest

from app.research import ResearchPurpose, ResearchRequest, TavilyResearchProvider


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def response(payload, status=200):
    request = httpx.Request("POST", "https://api.tavily.com/search")
    return httpx.Response(status, json=payload, request=request)


def test_tavily_search_returns_normalized_evidence():
    client = FakeClient(response({
        "request_id": "req-1",
        "results": [
            {
                "title": "Plant care",
                "url": "https://example.com/plant",
                "content": "Keep the soil evenly moist.",
                "score": 0.9,
            }
        ],
    }))
    provider = TavilyResearchProvider(client=client, api_key="secret")

    result = provider.search(
        ResearchRequest(
            query="Monstera watering guidance",
            purpose=ResearchPurpose.PLANT_CARE,
        )
    )

    assert result.provider == "tavily"
    assert result.request_id == "req-1"
    assert result.evidence[0].title == "Plant care"
    assert client.calls[0][0] == "https://api.tavily.com/search"
    body = client.calls[0][1]["json"]
    assert body["search_depth"] == "advanced"
    assert body["safe_search"] is True


def test_tavily_uses_bearer_authorization():
    client = FakeClient(response({"results": []}))
    provider = TavilyResearchProvider(client=client, api_key="secret")
    provider.search(
        ResearchRequest(
            query="washer maintenance manual",
            purpose=ResearchPurpose.APPLIANCE_GUIDANCE,
        )
    )
    assert client.calls[0][1]["headers"]["Authorization"] == "Bearer secret"


def test_tavily_http_failure_is_explicit():
    provider = TavilyResearchProvider(
        client=FakeClient(response({"detail": "error"}, status=500)),
        api_key="secret",
    )
    with pytest.raises(RuntimeError, match="Tavily search failed"):
        provider.search(
            ResearchRequest(
                query="plant guidance",
                purpose=ResearchPurpose.PLANT_CARE,
            )
        )


def test_tavily_invalid_payload_is_rejected():
    provider = TavilyResearchProvider(
        client=FakeClient(response({"unexpected": []})),
        api_key="secret",
    )
    with pytest.raises(ValueError, match="Invalid Tavily response"):
        provider.search(
            ResearchRequest(
                query="plant guidance",
                purpose=ResearchPurpose.PLANT_CARE,
            )
        )
