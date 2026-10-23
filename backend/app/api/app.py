from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker
from strawberry.fastapi import GraphQLRouter

from app.config import load_local_environment
from app.db.session import build_engine, build_session_factory
from app.media.api import build_media_router
from app.evidence import EvidenceIngestion
from app.automation.api import build_automation_router
from app.media.service import MediaService
from app.media.storage import LocalMediaStorage
from app.planning import NebiusPlanningProvider, PlanningService
from app.planning.api import build_planning_router
from app.repositories.sqlalchemy_observation_repository import SQLAlchemyObservationRepository
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository
from app.repositories.sqlalchemy_research_repository import SQLAlchemyResearchRepository
from app.research import ResearchService, TavilyResearchProvider
from app.research.api import build_research_router
from app.services import HouseholdEntityService
from app.vision.api import build_vision_router
from app.vision.provider import NebiusVisionProvider
from app.vision.service import VisionObservationService

from .entity_storage import build_entity_storage
from .graphql.schema import create_schema
from .intelligence import build_intelligence_router


def _allowed_origins() -> list[str]:
    raw = os.environ.get("HOMHIVE_ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app(
    *,
    entity_storage_backend: str | None = None,
    entity_session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    load_local_environment()
    repository, owned_engine = build_entity_storage(
        storage_backend=entity_storage_backend,
        session_factory=entity_session_factory,
    )
    household_entity_service = HouseholdEntityService(repository=repository)

    media_engine = None
    research_provider = None
    media_root = os.environ.get("HOMHIVE_MEDIA_ROOT")
    household_tokens_json = os.environ.get("HOMHIVE_HOUSEHOLD_TOKENS")

    if media_root or household_tokens_json:
        if not (media_root and household_tokens_json):
            raise ValueError("Media storage and household tokens must both be configured")

        tokens = json.loads(household_tokens_json)
        if not isinstance(tokens, dict) or not tokens or not all(
            isinstance(key, str) and key and isinstance(value, str) and value
            for key, value in tokens.items()
        ):
            raise ValueError("Invalid household token configuration")

        media_engine = build_engine()
        session_factory = build_session_factory(media_engine)
        media_service = MediaService(session_factory, LocalMediaStorage(Path(media_root)))
        observation_storage = SQLAlchemyObservationRepository(session_factory)
        task_storage = SQLAlchemyTaskRepository(session_factory)

        research_service = None
        if os.environ.get("TAVILY_API_KEY"):
            research_provider = TavilyResearchProvider()
            research_service = ResearchService(
                research_provider,
                SQLAlchemyResearchRepository(session_factory),
            )

        planning_provider = None
        if os.environ.get("NEBIUS_API_KEY") and os.environ.get("NEBIUS_REASONING_MODEL"):
            planning_provider = NebiusPlanningProvider()

        planning_service = PlanningService(
            task_storage,
            provider=planning_provider,
            research_service=research_service,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if research_provider is not None:
                research_provider.close()
            if owned_engine is not None:
                owned_engine.dispose()
            if media_engine is not None:
                media_engine.dispose()

    app = FastAPI(title="HomHive API", lifespan=lifespan)

    origins = _allowed_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    async def graphql_context():
        return {"household_entity_service": household_entity_service}

    app.include_router(
        GraphQLRouter(create_schema(), context_getter=graphql_context),
        prefix="/graphql",
    )

    if media_engine is not None:
        vision_service = None
        if os.environ.get("NEBIUS_API_KEY"):
            verifier = None
            review_model = os.environ.get("HOMHIVE_OPENAI_REVIEW_MODEL", "").strip()
            if review_model:
                if not os.environ.get("OPENAI_API_KEY"):
                    raise ValueError("OPENAI_API_KEY is required for independent verification")
                from app.vision.verification import OpenAIImageVerifier
                verifier = OpenAIImageVerifier(model=review_model)
            extra_verifier = None
            anthropic_model = os.environ.get('HOMHIVE_ANTHROPIC_REVIEW_MODEL', '').strip()
            if anthropic_model:
                from app.vision.anthropic_verification import AnthropicImageVerifier
                extra_verifier = AnthropicImageVerifier(model=anthropic_model)
            vision_service = VisionObservationService(
                media_service, NebiusVisionProvider(), observation_storage,
                verifier=verifier, additional_verifier=extra_verifier,
                require_verification=True,
            )
        evidence_ingestion = EvidenceIngestion(session_factory, media_service, vision_service)
        app.include_router(build_media_router(
            media_service, tokens, vision_service, evidence_ingestion,
        ))
        app.include_router(
            build_intelligence_router(
                observation_storage,
                task_storage,
                tokens,
            )
        )
        app.include_router(build_planning_router(planning_service, tokens))
        app.include_router(build_automation_router(session_factory, tokens))

        if research_provider is not None:
            app.include_router(
                build_research_router(
                    research_service,
                    tokens,
                )
            )

        if vision_service is not None:
            app.include_router(build_vision_router(vision_service, tokens))

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
