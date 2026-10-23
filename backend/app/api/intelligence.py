from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from app.models import TaskStatus

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.repositories.observation_storage import ObservationStorage
from app.repositories.task_storage import TaskStorage
from app.services.household_intelligence import refresh_household_intelligence
from app.services.observation_review import confirm_observation

from .household_auth import build_household_authorizer


class DeferTaskRequest(BaseModel):
    minutes: int = Field(ge=1, le=10080)


class DoneRequest(BaseModel):
    verification_minutes: int = Field(default=90, ge=15, le=10080)


class ObservationReviewRequest(BaseModel):
    confirmed_value: float = Field(ge=0.0, le=1.0)


def build_intelligence_router(
    observation_storage: ObservationStorage,
    task_storage: TaskStorage,
    household_tokens: Mapping[str, str],
) -> APIRouter:
    router = APIRouter(prefix="/households/{household_id}", tags=["intelligence"])
    authorize = build_household_authorizer(household_tokens)

    @router.get("/observations")
    def list_observation_history(household_id: str, _: None = Depends(authorize)):
        # Existing household-scoped storage is the source of truth.
        return [item.model_dump(mode="json") for item in observation_storage.list_observations(household_id)]

    @router.post("/observations/{observation_id}/confirm")
    def confirm(
        household_id: str,
        observation_id: str,
        request: ObservationReviewRequest,
        _: None = Depends(authorize),
    ):
        observation = confirm_observation(
            household_id,
            observation_id,
            request.confirmed_value,
            observation_storage,
        )
        if observation is None:
            raise HTTPException(status_code=404, detail="Observation not found")
        # Confirmation now advances the existing household intelligence pipeline.
        # Unconfirmed model output is never promoted implicitly.
        refresh_household_intelligence(household_id, observation_storage, task_storage)
        return observation.model_dump(mode="json")

    @router.post("/intelligence/refresh")
    def refresh(household_id: str, _: None = Depends(authorize)):
        report = refresh_household_intelligence(
            household_id,
            observation_storage,
            task_storage,
        )
        return report.model_dump(mode="json")

    @router.post("/tasks/{task_id}/accept")
    def accept_task(household_id: str, task_id: str, _: None = Depends(authorize)):
        task = task_storage.find_task(household_id, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != TaskStatus.PENDING:
            raise HTTPException(status_code=409, detail="Task is not pending")
        # Acceptance is a commitment marker, not an execution-state transition.
        # Repeated acceptance must remain idempotent.
        if task.metadata.get("accepted_at"):
            return task.model_dump(mode="json")
        task.metadata = {
            **task.metadata,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        }
        saved = task_storage.save_task(household_id, task)
        return saved.model_dump(mode="json")

    @router.post("/tasks/{task_id}/defer")
    def defer_task(
        household_id: str,
        task_id: str,
        request: DeferTaskRequest,
        _: None = Depends(authorize),
    ):
        task = task_storage.find_task(household_id, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != TaskStatus.PENDING or task.metadata.get("accepted_at"):
            raise HTTPException(status_code=409, detail="Task is not an uncommitted proposal")
        task.metadata = {
            **task.metadata,
            "deferred_until": (
                datetime.now(timezone.utc) + timedelta(minutes=request.minutes)
            ).isoformat(),
        }
        return task_storage.save_task(household_id, task).model_dump(mode="json")

    @router.post("/tasks/{task_id}/dismiss")
    def dismiss_task(household_id: str, task_id: str, _: None = Depends(authorize)):
        task = task_storage.find_task(household_id, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.metadata.get("accepted_at") or task.status == TaskStatus.IN_PROGRESS:
            raise HTTPException(status_code=409, detail="Committed work cannot be dismissed")
        if task.status == TaskStatus.DISMISSED:
            return task.model_dump(mode="json")
        if task.status != TaskStatus.PENDING:
            raise HTTPException(status_code=409, detail="Task is not pending")
        task.status = TaskStatus.DISMISSED
        task.metadata = {
            **task.metadata,
            "dismissed_at": datetime.now(timezone.utc).isoformat(),
        }
        return task_storage.save_task(household_id, task).model_dump(mode="json")

    @router.get("/suggestions")
    def suggestions(household_id: str, _: None = Depends(authorize)):
        """Durable inbox derived from persisted tasks, without a second task store."""
        now = datetime.now(timezone.utc)
        entries = []
        for task in task_storage.list_tasks(household_id):
            if task.status == TaskStatus.DISMISSED:
                continue
            meta = task.metadata
            if meta.get("user_reported_complete_at"):
                status = meta.get("verification_status", "awaiting_evidence")
            elif meta.get("accepted_at"):
                status = "accepted"
            elif _future(meta.get("deferred_until"), now):
                status = "deferred"
            elif task.status == TaskStatus.COMPLETED:
                status = "completed_unverified"
            elif task.status == TaskStatus.IN_PROGRESS:
                status = "in_progress"
            else:
                status = "suggested"
            entries.append({"task_id": task.id, "title": task.description,
                "space": task.task_key.removeprefix("predictive:").split(":")[0],
                "minutes": task.estimated_effort_minutes, "status": status,
                "source_observation_id": task.source_observation_id,
                "verification_due_at": meta.get("verification_due_at")})
        # Suppress predictive duplicates in the inbox; do not delete their provenance.
        observed = {task.task_key for task in task_storage.list_tasks(household_id)
                    if not task.task_key.startswith("predictive:")
                    and task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}}
        return [item for item in entries if not any(
            task.id == item["task_id"] and task.task_key.startswith("predictive:")
            and task.task_key.removeprefix("predictive:") in observed
            for task in task_storage.list_tasks(household_id))]

    @router.post("/tasks/{task_id}/done")
    def report_done(household_id: str, task_id: str, request: DoneRequest,
                    _: None = Depends(authorize)):
        task = task_storage.find_task(household_id, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status == TaskStatus.DISMISSED:
            raise HTTPException(status_code=409, detail="Dismissed task cannot be completed")
        if not task.metadata.get("accepted_at") and task.status != TaskStatus.IN_PROGRESS:
            raise HTTPException(status_code=409, detail="Accept the task before reporting completion")
        if task.metadata.get("user_reported_complete_at"):
            return task.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        task.metadata = {**task.metadata,
            "user_reported_complete_at": now.isoformat(),
            "verification_due_at": (now + timedelta(minutes=request.verification_minutes)).isoformat(),
            "verification_status": "not_due",
            "verification_attempts": 0}
        return task_storage.save_task(household_id, task).model_dump(mode="json")

    @router.post("/tasks/{task_id}/verify")
    def verify_task(household_id: str, task_id: str, _: None = Depends(authorize)):
        """On-demand durable verification evaluation; does not pretend to rescan."""
        task = task_storage.find_task(household_id, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        done_at = _parse_time(task.metadata.get("user_reported_complete_at"))
        if done_at is None:
            raise HTTPException(status_code=409, detail="Completion not reported")
        if task.metadata.get("verification_status") in {"verified_resolved", "verified_persisting"}:
            return task.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        due = _parse_time(task.metadata.get("verification_due_at"))
        if due is not None and due > now:
            return task.model_dump(mode="json")
        from app.automation.verification import evaluate
        task = evaluate(task, household_id, observation_storage, now)
        return task_storage.save_task(household_id, task).model_dump(mode="json")

    return router

def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def _future(value: object, now: datetime) -> bool:
    parsed = _parse_time(value)
    return parsed is not None and parsed > now
