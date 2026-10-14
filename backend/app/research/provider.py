import os
from typing import Protocol

import httpx

from app.config import load_local_environment

from .models import ResearchEvidence, ResearchRequest, ResearchResult


class ResearchProvider(Protocol):
    def search(self, request: ResearchRequest) -> ResearchResult:
        ...


class TavilyResearchProvider:
    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None):
        load_local_environment()
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if not self._api_key:
            raise ValueError("TAVILY_API_KEY is required")
        self._client = client or httpx.Client(timeout=15.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search(self, request: ResearchRequest) -> ResearchResult:
        try:
            response = self._client.post(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": request.query,
                    "search_depth": "advanced",
                    "chunks_per_source": 3,
                    "max_results": request.max_results,
                    "topic": "general",
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                    "include_usage": True,
                    "safe_search": True,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Tavily search failed") from exc

        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("Invalid Tavily response")

        evidence = []
        for item in payload["results"]:
            if not isinstance(item, dict):
                raise ValueError("Invalid Tavily result")
            try:
                evidence.append(
                    ResearchEvidence(
                        title=item["title"],
                        url=item["url"],
                        content=item["content"],
                        score=item.get("score"),
                        published_date=item.get("published_date"),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ValueError("Invalid Tavily result") from exc

        return ResearchResult(
            query=request.query,
            purpose=request.purpose,
            evidence=evidence,
            request_id=payload.get("request_id"),
        )
