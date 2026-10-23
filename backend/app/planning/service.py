from app.models import TaskStatus
from datetime import datetime, timezone
from app.repositories.task_storage import TaskStorage
from app.research import ResearchRequest, ResearchResult, ResearchService
from app.services.task_ranking import rank_tasks

from .feasibility import build_deterministic_plan
from .models import HouseholdPlan, PlanningContext, TaskFeasibility
from .provider import PlanningProvider


def _is_deferred(value: object, now: datetime) -> bool:
    if not isinstance(value, str):
        return False
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return deadline.tzinfo is not None and deadline > now
    except ValueError:
        return False


class PlanningService:
    def __init__(
        self,
        tasks: TaskStorage,
        provider: PlanningProvider | None = None,
        research_service: ResearchService | None = None,
    ):
        self._tasks = tasks
        self._provider = provider
        self._research_service = research_service

    def create_plan(
        self,
        household_id: str,
        context: PlanningContext,
        research_requests: list[ResearchRequest] | None = None,
    ) -> tuple[HouseholdPlan, list[TaskFeasibility], list[ResearchResult]]:
        # Planning is a commitment workflow. Discovery proposals are not
        # executable until explicitly accepted by the household member.
        now = datetime.now(timezone.utc)
        eligible = [
            task for task in self._tasks.list_tasks(household_id)
            if task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
            and bool(task.metadata.get("accepted_at"))
            and not _is_deferred(task.metadata.get("deferred_until"), now)
        ]
        # Forecast and observed proposals may represent the same chore.
        # Keep the observed task when both are committed, deterministically.
        unique = {}
        for task in sorted(eligible, key=lambda item: (item.task_key.startswith("predictive:"), item.created_at, item.id)):
            condition_key = task.task_key.removeprefix("predictive:")
            unique.setdefault(condition_key, task)
        ranked = rank_tasks(list(unique.values()))
        fallback, feasibility = build_deterministic_plan(ranked, context)

        research_results = []
        for request in research_requests or []:
            if self._research_service is None:
                raise ValueError("Research provider is not configured")
            research_results.append(self._research_service.research(household_id, request))

        if self._provider is None or not ranked:
            return fallback, feasibility, research_results

        try:
            plan = self._provider.plan(ranked, context, feasibility, research_results)
        except (RuntimeError, ValueError):
            return fallback, feasibility, research_results

        return plan, feasibility, research_results
