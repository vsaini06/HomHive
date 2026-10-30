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
from app.services.open_world_live import _read_json_text, preview_verified_scene
from app.services.open_world_planning import ActionProposal

logger = logging.getLogger(__name__)

class ScanRequest(BaseModel):
    reference_media_id: str = Field(min_length=1, max_length=128)


class RoomCategoryCorrection(BaseModel):
    room_category: str = Field(min_length=2, max_length=120)


class ExistingRoomSelection(BaseModel):
    room_id: str = Field(min_length=1, max_length=128)


class ObjectLocationRequest(BaseModel):
    room_id: str | None = None


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
        "laundry piles moving, and lawn growth or mowing are possible; they are not by themselves "
        "evidence of a different room. Compare multiple stable fixtures across the images. "
        "If ambiguous or insufficient, respond false.")
    if callable(getattr(vision.primary, "compare_rooms", None)):
        p = vision.primary.compare_rooms(ref_image, ref_type, image, media_type)
        if type(p.get("same_physical_room")) is not bool:
            return False
    else:
        primary = vision.primary.client.chat.completions.create(
            model=vision.primary.model,
            messages=[{"role":"system","content":instruction}, {"role":"user","content":[
                {"type":"text","text":"Reference image, followed by candidate image."},
                _image_url(ref_image, ref_type), _image_url(image, media_type)]}], max_tokens=500)
        p = _read_json_text(primary.choices[0].message.content) if primary.choices and primary.choices[0].finish_reason != 'length' else {}
    client = vision.independent
    blocks = [
        {"type":"text","text":"Reference image:"},
        {"type":"image","source":{"type":"base64","media_type":ref_type,"data":base64.b64encode(ref_image).decode('ascii')}},
        {"type":"text","text":"Candidate image:"},
        {"type":"image","source":{"type":"base64","media_type":media_type,"data":base64.b64encode(image).decode('ascii')}},
    ]
    response = client.client.post("https://api.anthropic.com/v1/messages", json={
        "model":client.model,"max_tokens":6500 if client.model.startswith("claude-opus-5-5") else 500,"system":instruction,
        **({"output_config":{"format":{"type":"json_schema", "schema": __import__(
            "app.services.accuracy_models", fromlist=["SCHEMAS"]).SCHEMAS["room_pair"]}}}
            if getattr(client, "strict_structure", False) else {}),
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
      "invisible changes. Disappearance of dirty dishes or clutter from the frame proves only that "
      "the visible area was cleared, NOT that objects were washed, sanitized, dried, safely stored, "
      "or put away. For wash, clean, or sanitize tasks, never verify that action from absence "
      "alone; use inconclusive or conservative partial progress where supported. For clear-space "
      "tasks, visible clearing may count toward that narrow goal, but do not claim unseen storage. "
      "Complete ONLY if a new photograph proves the SPECIFIC criterion; clean-looking "
      "surroundings alone are not proof. Cite at least one corroborated claim ID. "
      "If the relevant area is not visible, use inconclusive. If uncertain, do not complete.")
    result = independent.ask(instruction=instruction, payload={"task":task,
       "corroborated_evidence":[e.model_dump(mode="json") for e in evidence]},
       image=image, media_type=media_type, max_tokens=800,
       **({"schema_kind": "completion"} if getattr(independent, "strict_structure", False) else {}))
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
                        require_room_category=False, user_confirmed_room=False, verified_room_evidence=False,
                        trusted_demo_relationship=False, object_probe=False, object_registry=None):
    current = media.get_image(household_id, media_id)
    reference = media.get_image(household_id, reference_media_id)
    if not current or not reference:
        raise LookupError("Media not found")
    info, image = current
    ref_info, ref_image = reference
    _check_images(info, image, ref_info, ref_image)

    room_id = f"reference:{reference_media_id}"
    vision, planner, reviewer = build_pipeline()
    independent = getattr(vision, 'independent', None)
    try:
        if not object_probe and media_id != reference_media_id and not (user_confirmed_room or verified_room_evidence or trusted_demo_relationship):
            same = verify_room_pair(vision, ref_image, ref_info.content_type, image, info.content_type)
            if not same:
                return {"status":"held_unverified_room","saved":False,"created":[],"existing":[],"completed":{},"approved_actions":0}
        room = RoomContinuity(physical_room_id=room_id, same_physical_room_verified=True,
            reason=("Person explicitly identified the same physical room"
                if user_confirmed_room else "Both photographs belong to the server-verified demo scene family"
                if trusted_demo_relationship else "Previously completed visual views independently matched this room"
                if verified_room_evidence else "First photo establishes a new room reference"
                if media_id == reference_media_id else "Two independent visual room comparisons"))
        from app.services.demo_scene_identity import verified_demo_scene
        from app.coordination.scene_focus import classify_scene_focus
        import hashlib
        demo_scene = verified_demo_scene(image)
        image_hash = hashlib.sha256(image).hexdigest()
        demo_family = demo_scene.get('family') if demo_scene else None
        existing_object = object_registry.lookup(household_id, media_id,
            demo_family=demo_family, image_hash=image_hash) if object_probe and object_registry else None
        active_tasks = [task for task in bridge.get_tasks(household_id)
            if (task.get('object_id') == existing_object if object_probe else task['room_id'] == room_id)
            and task['status'] not in ('dismissed', 'completed')]
        preview = preview_verified_scene(image=image, media_type=info.content_type, media_id=media_id,
            vision=vision, planner=planner, reviewer=reviewer,
            existing_tasks=[{"title": t["title"], "action": t["action"]} for t in active_tasks],
            reference_image=ref_image if media_id != reference_media_id else None,
            reference_media_type=ref_info.content_type if media_id != reference_media_id else None)
        evidence = preview.corroborated_evidence
        if require_room_category and not preview.room_category and not object_probe:
            return {"status": "held_unverified_room", "saved": False, "created": [],
                    "existing": [], "completed": {}, "approved_actions": 0}

        verdicts = []
        if active_tasks and evidence:
            for task in (t for t in active_tasks if t.get("source_media_id") != media_id):
                verdicts.append(review_completion(independent, task=task, image=image,
                    media_type=info.content_type, evidence=evidence, media_id=media_id))
        from app.services.effort_research import ground_action_effort
        approved = [ground_action_effort(ActionProposal.model_validate(action))
                    for action in preview.approved_actions]
        scene_focus = classify_scene_focus(
            [item.description for item in evidence], preview.room_category,
            demo_scene.get('category') if demo_scene else None)
        scene_focus['location_confirmed'] = bool(user_confirmed_room or verified_room_evidence or trusted_demo_relationship)
        if not object_probe and scene_focus['focus'] == 'object':

            return {'status': 'held_object_scope', 'saved': False,
                    'created': [], 'existing': [], 'completed': {}, 'approved_actions': 0}
        if not object_probe and scene_focus['focus'] == 'hybrid' and object_registry is not None:

            known_object_id = object_registry.lookup(household_id, media_id,
                demo_family=demo_family, image_hash=image_hash)
            if known_object_id is not None and room.same_physical_room_verified:
                try:
                    object_registry.set_room(household_id, known_object_id, room_id)
                except LookupError:
                    logger.info('Hybrid object has no registered room yet')
        if object_probe:
            if scene_focus['focus'] != 'object' or not evidence or object_registry is None:
                return {'status': 'not_object', 'saved': False, 'created': [], 'existing': [],
                        'completed': {}, 'approved_actions': 0}
            descriptions = [item.description[:350] for item in evidence]
            facts = ' '.join(descriptions).lower()
            kind = 'plant' if any(word in facts for word in ('plant', 'pothos', 'leaves', 'leaf', 'foliage', 'fern', 'orchid')) else (
                'appliance' if any(word in facts for word in ('appliance', 'refrigerator', 'washer', 'dryer', 'microwave', 'furnace')) else 'object')

            hint = 'Possible Pothos' if kind == 'plant' and 'pothos' in facts else None
            object_id = object_registry.resolve(household_id, media_id, kind,
                demo_family=demo_family, image_hash=image_hash, evidence=descriptions, identity_hint=hint)
            room = RoomContinuity(physical_object_id=object_id,
                same_physical_object_verified=True,
                reason='Object recognized from independently corroborated photograph')
            room_id = None
        completion = bridge.reconcile_verified_scan(household_id, ScanOutcomeReview(
            media_id=media_id, room=room, corroborated_evidence=evidence, outcomes=verdicts)) if verdicts else {}
        review_summary = {
            "room_category": preview.room_category if not object_probe else None,
            "object_id": room.physical_object_id if object_probe else None,
            "scene_focus": scene_focus,
            "room_identity_source": "user_confirmed" if user_confirmed_room else "verified_demo_pair" if trusted_demo_relationship else "model_verified",
            "verification": preview.verification,
            "evidence_reason": (
                "no_visible_claims" if not preview.model_audit.get("primary_claims")
                else "claims_not_corroborated" if not evidence
                else "no_task_proposed" if preview.proposed_count == 0
                else "proposals_not_approved" if not approved
                else "approved_actions"),
            "primary_claim_count": len(preview.model_audit.get("primary_claims", [])),
            "corroborated_claim_count": len(evidence),
            "evidence": [item.description[:350] for item in evidence[:12]],
            "preplan_research": preview.model_audit.get("preplan_research", []),
            "pair_change_count": sum(item.id.startswith("p") for item in evidence),
            "pair_comparison_status": preview.model_audit.get("paired_comparison", {}).get("status"),
            "pair_evidence": [item.description[:350] for item in evidence if item.id.startswith("p")][:12],
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
            room_category=preview.room_category if not object_probe else None))
        return {"status":"reviewed","saved":True,"created":discovered['created'],
            "existing":discovered['existing'],"completed":completion,
            "approved_actions":len(approved),"rejected_actions":preview.rejected_actions,
            "room_id":room_id,"object_id":room.physical_object_id if object_probe else None,
            "room_category":preview.room_category if not object_probe else None,
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

    @router.post('/media/{media_id}/assign-existing-room')
    def assign_existing_room(household_id: str, media_id: str, selection: ExistingRoomSelection,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        if jobs is None:
            raise HTTPException(status_code=503, detail='Autonomous queue disabled')
        if media.get_image(household_id, media_id) is None:
            raise HTTPException(status_code=404, detail='Media not found')
        try:
            return jobs.assign_existing_room(household_id, media_id, selection.room_id)
        except LookupError:
            raise HTTPException(status_code=404, detail='Scan or room not found in your household')
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

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

    @router.get('/autonomous-objects')
    def list_objects(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        from app.services.autonomous_objects import ObjectRegistry
        return {'objects': ObjectRegistry(session_factory).list(household_id)}

    @router.get('/autonomous-objects/{object_id}/photo')
    def object_photo(household_id: str, object_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        from sqlalchemy import select
        from app.services.autonomous_objects import AutonomousObjectRecord
        from fastapi import Response
        with session_factory() as db:
            obj = db.get(AutonomousObjectRecord, (household_id, object_id))
            if obj is None:
                raise HTTPException(status_code=404, detail='Object not found')
            photo_id = obj.reference_media_id
        result = media.get_image(household_id, photo_id)
        if not result:
            raise HTTPException(status_code=404, detail='Object photo unavailable')
        info, data = result
        if info.content_type not in {'image/jpeg','image/png','image/webp'}:
            raise HTTPException(status_code=415, detail='Unsupported image')
        return Response(content=data, media_type=info.content_type,
            headers={'Cache-Control': 'private, max-age=120', 'X-Content-Type-Options': 'nosniff'})

    @router.put('/autonomous-objects/{object_id}/location')
    def update_object_location(household_id: str, object_id: str, request: ObjectLocationRequest,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        from app.services.autonomous_objects import ObjectRegistry
        try:
            return ObjectRegistry(session_factory).set_room(household_id, object_id, request.room_id)
        except LookupError:
            raise HTTPException(status_code=404, detail='Object or space not found')

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

    @router.get('/autonomous-pulse')
    def household_pulse(household_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return bridge.lifecycle.household_pulse(household_id)

    @router.get('/autonomous-tasks/{task_id}/timeline')
    def task_timeline(household_id: str, task_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        try:
            return bridge.lifecycle.task_timeline(household_id, task_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Task not found")

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
