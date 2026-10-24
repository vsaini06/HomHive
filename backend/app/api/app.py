from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, Response
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
    accounts = None
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
        # Account auth is opt-in until database migration and signing secret are configured.
        account_secret = os.environ.get("HOMHIVE_ACCOUNT_SIGNING_SECRET", "")
        if account_secret:
            if len(account_secret) < 32:
                raise ValueError("Account signing secret must be at least 32 characters")
            from app.auth.service import AccountService, HouseholdTokens
            accounts = AccountService(session_factory)
            tokens = HouseholdTokens(tokens, account_secret)
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

    if accounts is not None:
        from app.auth.service import build_accounts_router
        app.include_router(build_accounts_router(accounts))

        @app.middleware("http")
        async def household_session_bridge(request: Request, call_next):
            # Check membership BEFORE converting a user session to an internal
            # compatibility credential. Never disclose household credentials.
            parts = request.url.path.split("/")
            if len(parts) >= 3 and parts[1] == "households":
                authorization = request.headers.get("authorization", "")
                if authorization.lower().startswith("bearer "):
                    supplied = authorization[7:]
                    household_id = parts[2]
                    if accounts.membership(supplied, household_id):
                        credential = tokens.get(household_id)
                        if credential is not None:
                            request.scope["headers"] = [
                                (key, value) for key, value in request.scope["headers"]
                                if key.lower() != b"authorization"
                            ] + [(b"authorization", ("Bearer " + credential).encode())]
            return await call_next(request)

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
        autonomous_jobs = None
        if os.environ.get("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "").lower() == "true":
            from app.services.autonomous_jobs import AutonomousJobService
            autonomous_jobs = AutonomousJobService(session_factory)
        app.include_router(build_media_router(
            media_service, tokens, vision_service, evidence_ingestion,
            after_upload=autonomous_jobs.enqueue if autonomous_jobs is not None else None,
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
            from app.services.household_intelligence import refresh_household_intelligence
            app.include_router(build_vision_router(
                vision_service, tokens,
                after_observations=lambda household_id: refresh_household_intelligence(
                    household_id, observation_storage, task_storage
                ),
            ))
            # Explicit opt-in preview: does not alter legacy observations or tasks.
            # Any failure is reported as incomplete, never as successful verification.
            if (os.environ.get("HOMHIVE_ENABLE_OPEN_WORLD_PREVIEW", "").lower() == "true"
                and os.environ.get("OPENAI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY")
                and os.environ.get("HOMHIVE_OPENAI_REVIEW_MODEL")
                and os.environ.get("HOMHIVE_ANTHROPIC_REVIEW_MODEL")):
                from app.vision.open_world_api import build_open_world_preview_router
                from app.services.open_world_live import (OpenAIJsonClient, AnthropicJsonClient,
                    OpenWorldVision, OpenWorldPlanner, OpenWorldActionReviewer)
                def open_world_pipeline():
                    import httpx
                    from openai import OpenAI
                    primary = OpenAIJsonClient(OpenAI(timeout=45, max_retries=1),
                        os.environ["HOMHIVE_OPENAI_REVIEW_MODEL"])
                    independent = AnthropicJsonClient(httpx.Client(timeout=60),
                        os.environ["HOMHIVE_ANTHROPIC_REVIEW_MODEL"], os.environ["ANTHROPIC_API_KEY"])
                    return (OpenWorldVision(primary, independent),
                            OpenWorldPlanner(primary), OpenWorldActionReviewer(independent))
                app.include_router(build_open_world_preview_router(media_service, tokens, open_world_pipeline))
                if os.environ.get("HOMHIVE_ENABLE_AUTONOMOUS_SCAN", "").lower() == "true":
                    from app.vision.autonomous_api import build_autonomous_router
                    app.include_router(build_autonomous_router(media_service, tokens, session_factory, open_world_pipeline,
                        jobs=autonomous_jobs))
                    if autonomous_jobs is not None:
                        from app.services.autonomous_scan_bridge import AutonomousScanBridge
                        from app.services.autonomous_lifecycle import AutonomousLifecycle
                        from app.vision.autonomous_api import run_autonomous_scan
                        scan_bridge = AutonomousScanBridge(AutonomousLifecycle(session_factory))
                        app.state.autonomous_process_one = lambda: autonomous_jobs.process_one(
                            media=media_service, bridge=scan_bridge, build_pipeline=open_world_pipeline,
                            scan=run_autonomous_scan)


    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
