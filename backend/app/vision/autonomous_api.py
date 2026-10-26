"""Explicit opt-in live scan: independently reviewed plans -> durable lifecycle.

A physical room is anchored to a user-selected reference photograph. Subsequent
scans require independent two-image continuity verification. The reference scan
itself is user enrollment, never an inferred match. Failures never write tasks.
"""
from __future__ import annotations

import base64
import hmac
import logging
from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError

from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, OutcomeVerdict, ReviewedOutcome, RoomContinuity,
)
from app.services.autonomous_scan_bridge import AutonomousScanBridge, ScanOutcomeReview, VerifiedScan
from app.services.open_world_live import preview_verified_scene
from app.services.open_world_planning import ActionProposal

logger = logging.getLogger(__name__)

class ScanRequest(BaseModel):
    reference_media_id: str = Field(min_length=1, max_length=128)


class RoomCategoryCorrection(BaseModel):
    room_category: str = Field(min_length=2, max_length=120)


class WorkWindowRequest(BaseModel):
    timezone: str = Field(min_length=1, max_length=80)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    weekdays: list[int] = Field(min_length=1, max_length=7)


def _image_url(image: bytes, media_type: str):
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"}}


def _check_images(info, image, reference_info, reference_image):
    if not image or not reference_image or info.content_type not in {"image/jpeg", "image/png", "image/webp"} or reference_info.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Unsupported image format")


def verify_room_pair(vision, ref_image: bytes, ref_type: str, image: bytes, media_type: str) -> bool:
    """Two independent image-aware assessments; disagreement means no match."""
    instruction = ("Compare two images of household spaces. Answer ONLY JSON "
        '{"same_physical_room":boolean,"explanation":string}. '
        "A matching room CATEGORY is insufficient. Require stable structural fixtures, layout, "
        "and distinctive persistent landmarks. Different angles, lighting, moved objects, "
        "and changing clutter are possible. If ambiguous or insufficient, respond false.")
    primary = vision.primary.client.chat.completions.create(
        model=vision.primary.model,
        messages=[{"role":"system","content":instruction}, {"role":"user","content":[
            {"type":"text","text":"Reference image, followed by candidate image."},
            _image_url(ref_image, ref_type), _image_url(image, media_type)]}], max_tokens=500)
    from app.services.open_world_live import _read_json_text
    p = _read_json_text(primary.choices[0].message.content) if primary.choices and primary.choices[0].finish_reason != 'length' else {}
    client = vision.independent
    blocks = [
        {"type":"text","text":"Reference image:"},
        {"type":"image","source":{"type":"base64","media_type":ref_type,"data":base64.b64encode(ref_image).decode('ascii')}},
        {"type":"text","text":"Candidate image:"},
        {"type":"image","source":{"type":"base64","media_type":media_type,"data":base64.b64encode(image).decode('ascii')}},
    ]
    response = client.client.post("https://api.anthropic.com/v1/messages", json={
        "model":client.model,"max_tokens":500,"system":instruction,
        "messages":[{"role":"user","content":blocks}]},
        headers={"x-api-key":client.key,"anthropic-version":"2023-06-01"})
    response.raise_for_status()
    content = response.json()
    if content.get("stop_reason") == "max_tokens":
        return False
    a = _read_json_text("\n".join(part.get("text","") for part in content.get("content",[]) if part.get("type")=="text"))
    return p.get("same_physical_room") is True and a.get("same_physical_room") is True


def review_completion(independent, *, task: dict, image: bytes, media_type: str, evidence: list, media_id: str) -> ReviewedOutcome:
    instruction = ("Independently audit ONE existing household task against the CURRENT original photograph "
      "and corroborated visual facts. Respond ONLY JSON "
      '{"verdict":"completed|still_needed|partially_completed|inconclusive",'
      '"criterion_verified":boolean,"claim_ids":["e1"],"explanation":"...",'
      '"progress_percent":null,"next_step":null}. '
      "Track the task as a changing condition, not a done/undone toggle. Compare current evidence "
      "against the ORIGINAL task criteria, describe what remains, and estimate rough completion "
      "percentage 0-100 only when the relevant scene is sufficiently visible. For partial improvement "
      "return partially_completed and an evidence-supported integer 1-99 (prefer cautious rounded 10% "
      "increments such as 20%), with next_step grounded in what remains. For completed return 100; "
      "for still_needed use 0-99 only if assessable; for inconclusive use null and retain old progress. "
      "Percentages are approximate, NOT measured quantities. Never manufacture coverage or infer "
      "invisible changes. Complete ONLY if a new photograph proves the SPECIFIC criterion; clean-looking "
      "surroundings alone are not proof. Cite at least one corroborated claim ID. "
      "If the relevant area is not visible, use inconclusive. If uncertain, do not complete.")
    result = independent.ask(instruction=instruction, payload={"task":task,
       "corroborated_evidence":[e.model_dump(mode="json") for e in evidence]},
       image=image, media_type=media_type, max_tokens=800)
    claim_ids = result.get('claim_ids')
    if not isinstance(claim_ids, list) or not claim_ids or not all(isinstance(c, str) for c in claim_ids):
        raise ValueError("Completion review missing corroborated claim IDs")
    known = {e.id for e in evidence}
    if not set(claim_ids).issubset(known):
        raise ValueError("Completion review cited unsupported claims")
    if type(result.get('criterion_verified')) is not bool:
        raise ValueError("Completion review missing boolean criterion")
    verdict = OutcomeVerdict(result['verdict'])
    explanation = result.get('explanation')
    if not isinstance(explanation, str) or len(explanation.strip()) < 12:
        raise ValueError("Missing independent reasoning")
    percent = result.get('progress_percent')
    if percent is not None and type(percent) is not int:
        raise ValueError("Completion progress must be an integer or null")
    next_step = result.get('next_step')
    if next_step is not None and (not isinstance(next_step, str) or len(next_step) > 350):
        raise ValueError("Invalid remaining-work description")
    return ReviewedOutcome(task_id=task['id'], verdict=verdict,
        criterion_verified=result['criterion_verified'], reviewer_explanation=explanation[:1500],
        progress_percent=percent, next_step=next_step or None,
        evidence=EvidenceReference(media_id=media_id, claim_ids=claim_ids,
            original_image_reviewed=True, independent_review_passed=True))


def run_autonomous_scan(*, household_id, media_id, reference_media_id, media, bridge, build_pipeline,
                        require_room_category=False):
    current = media.get_image(household_id, media_id)
    reference = media.get_image(household_id, reference_media_id)
    if not current or not reference:
        raise LookupError("Media not found")
    info, image = current
    ref_info, ref_image = reference
    _check_images(info, image, ref_info, ref_image)
    # Reference media ID is an explicit user-enrolled anchor, not a room category.
    room_id = f"reference:{reference_media_id}"
    vision, planner, reviewer = build_pipeline()
    independent = getattr(vision, 'independent', None)
    try:
        if media_id != reference_media_id:
            same = verify_room_pair(vision, ref_image, ref_info.content_type, image, info.content_type)
            if not same:
                return {"status":"held_unverified_room","saved":False,"created":[],"existing":[],"completed":{},"approved_actions":0}
        room = RoomContinuity(physical_room_id=room_id, same_physical_room_verified=True,
            reason="First photo establishes a new room reference" if media_id == reference_media_id else "Two independent visual room comparisons")
        active_tasks = [task for task in bridge.get_tasks(household_id)
            if task['room_id'] == room_id and task['status'] not in ('dismissed', 'completed')]
        preview = preview_verified_scene(image=image, media_type=info.content_type, media_id=media_id,
            vision=vision, planner=planner, reviewer=reviewer,
            existing_tasks=[{"title": t["title"], "action": t["action"]} for t in active_tasks])
        evidence = preview.corroborated_evidence
        if require_room_category and not preview.room_category:
            return {"status": "held_unverified_room", "saved": False, "created": [],
                    "existing": [], "completed": {}, "approved_actions": 0}
        # Finish outcome verification before ANY writes, including new discoveries.
        verdicts = []
        if active_tasks and evidence:
            for task in (t for t in active_tasks if t.get("source_media_id") != media_id):
                verdicts.append(review_completion(independent, task=task, image=image,
                    media_type=info.content_type, evidence=evidence, media_id=media_id))
        completion = bridge.reconcile_verified_scan(household_id, ScanOutcomeReview(
            media_id=media_id, room=room, corroborated_evidence=evidence, outcomes=verdicts)) if verdicts else {}
        from app.services.effort_research import ground_action_effort
        approved = [ground_action_effort(ActionProposal.model_validate(action))
                    for action in preview.approved_actions]
        review_summary = {
            "room_category": preview.room_category,
            "verification": preview.verification,
            "evidence": [item.description[:350] for item in evidence[:12]],
            "proposed_count": preview.proposed_count or (len(approved) + len(preview.rejected_actions)),
            "approved_count": len(approved),
            "progress_results": completion,
            "proposal_reviews": [{
                "title": str(item.get("title", ""))[:180],
                "decision": str(item.get("decision", ""))[:24],
                "reason": str(item["reason"])[:120] if item.get("reason") else None,
                "reviewer_explanation": str(item["reviewer_explanation"])[:400]
                    if item.get("reviewer_explanation") else None,
            } for item in preview.proposal_reviews[:20]],
        }
        discovered = bridge.persist_verified_scan(household_id, VerifiedScan(
            media_id=media_id, corroborated_evidence=evidence, approved_actions=approved,
            independently_reviewed=True, original_media_reviewed=True, room=room,
            room_category=preview.room_category))
        return {"status":"reviewed","saved":True,"created":discovered['created'],
            "existing":discovered['existing'],"completed":completion,
            "approved_actions":len(approved),"rejected_actions":preview.rejected_actions,
            "room_id":room_id,"room_category":preview.room_category,
            "review_summary": review_summary}
    finally:
        if independent is not None and hasattr(independent.client, 'close'):
            independent.client.close()


def build_autonomous_router(media, household_tokens: Mapping[str, str], session_factory, build_pipeline, jobs=None):
    router = APIRouter(prefix="/households/{household_id}", tags=["autonomous-lifecycle"])
    bearer = HTTPBearer(auto_error=False)
    bridge = AutonomousScanBridge(AutonomousLifecycle(session_factory))
    def check(household_id: str, credentials: HTTPAuthorizationCredentials | None):
        expected = household_tokens.get(household_id)
        if expected is None or credentials is None or not hmac.compare_digest(credentials.credentials, expected):
            raise HTTPException(status_code=403, detail="Access denied")
    @router.post('/autonomous-rooms/{reference_media_id}', status_code=201)
    def enroll_room(household_id: str, reference_media_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        if jobs is None:
            raise HTTPException(status_code=503, detail='Autonomous queue disabled')
        if media.get_image(household_id, reference_media_id) is None:
            raise HTTPException(status_code=404, detail='Media not found')
        return {'room_id': jobs.enroll(household_id, reference_media_id), 'reference_media_id': reference_media_id}

    @router.put('/autonomous-rooms/{room_id}/category')
    def correct_room_category(household_id: str, room_id: str, correction: RoomCategoryCorrection,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        if jobs is None:
            raise HTTPException(status_code=503, detail='Autonomous queue disabled')
        try:
            return jobs.correct_room_category(household_id, room_id, correction.room_category)
        except LookupError:
            raise HTTPException(status_code=404, detail='Space not found')
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @router.get('/autonomous-rooms')
    def list_rooms(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {'rooms': jobs.rooms(household_id) if jobs is not None else []}

    @router.post('/media/{media_id}/autonomous-queue')
    def retry_scan(household_id: str, media_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        if jobs is None:
            raise HTTPException(status_code=503, detail="Autonomous queue is not enabled")
        if media.get_image(household_id, media_id) is None:
            raise HTTPException(status_code=404, detail="Media not found")
        try:
            return {"job_id": jobs.retry(household_id, media_id)}
        except LookupError as exc:
            return {"job_id": jobs.enqueue(household_id, media_id)}

    @router.post('/media/{media_id}/autonomous-recheck')
    def recheck_completed_scan(household_id: str, media_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        if jobs is None:
            raise HTTPException(status_code=503, detail='Autonomous queue disabled')
        if media.get_image(household_id, media_id) is None:
            raise HTTPException(status_code=404, detail='Media not found')
        try:
            return {'job_id': jobs.recheck_completed(household_id, media_id)}
        except LookupError:
            raise HTTPException(status_code=404, detail='Completed scan not found')
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @router.get('/autonomous-scan-jobs')
    def list_scan_jobs(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {'jobs': jobs.jobs(household_id) if jobs is not None else []}

    @router.get('/autonomous-alerts')
    def get_alerts(household_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {"alerts": bridge.lifecycle.alerts(household_id)}

    @router.post('/autonomous-alerts/{alert_id}/read')
    def mark_alert_read(household_id: str, alert_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        try:
            return bridge.lifecycle.read_alert(household_id, alert_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Notification not found")

    @router.get('/autonomous-work-window')
    def get_work_window(household_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {"window": bridge.lifecycle.get_availability(household_id)}

    @router.put('/autonomous-work-window')
    def update_work_window(household_id: str, request: WorkWindowRequest,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        try:
            window = bridge.lifecycle.set_availability(household_id,
                timezone_name=request.timezone, start_time=request.start_time,
                end_time=request.end_time, weekdays=request.weekdays)
            return {"window": window}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @router.get('/autonomous-tasks')
    def list_tasks(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {'tasks': bridge.get_tasks(household_id)}
    @router.post('/autonomous-tasks/{task_id}/decisions/{decision}')
    def task_decision(household_id: str, task_id: str, decision: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        try:
            return bridge.lifecycle.decide(household_id, task_id, decision)
        except LookupError:
            raise HTTPException(status_code=404, detail="Task not found")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @router.post('/media/{media_id}/autonomous-scan')
    def scan(household_id: str, media_id: str, request: ScanRequest,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        try:
            return run_autonomous_scan(household_id=household_id, media_id=media_id,
                reference_media_id=request.reference_media_id, media=media,
                bridge=bridge, build_pipeline=build_pipeline)
        except LookupError:
            raise HTTPException(status_code=404, detail="Media not found")
        except Exception as exc:
            if isinstance(exc, ValidationError):
                logger.warning('Autonomous scan schema error: fields=%s', [
                    {'field':'.'.join(map(str,x['loc'])),'type':x['type']}
                    for x in exc.errors(include_input=False)])
            else:
                logger.warning('Autonomous scan held: error_type=%s', type(exc).__name__)
            raise HTTPException(status_code=503, detail="Autonomous scan incomplete; review before trusting task state") from exc
    return router
