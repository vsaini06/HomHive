from app.models import TaskStatus
from app.repositories.task_storage import TaskStorage
from app.research import ResearchRequest, ResearchResult, ResearchService
from app.services.task_ranking import rank_tasks

from .feasibility import build_deterministic_plan
from .models import HouseholdPlan, PlanningContext, TaskFeasibility
from .provider import PlanningProvider


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
        active_tasks = [
            task
            for task in self._tasks.list_tasks(household_id)
            if task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
        ]
        ranked = rank_tasks(active_tasks)
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
