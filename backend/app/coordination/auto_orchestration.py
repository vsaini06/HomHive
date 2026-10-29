"""Bounded post-scan research and Nemotron advice, after independently reviewed evidence.

This never writes new tasks or overrides feasibility. Every external call is gated by
verified task changes and a durable scan-job marker. It runs in the existing worker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
import re
from sqlalchemy import select

from app.services.autonomous_jobs import AutonomousScanJob
from app.services.autonomous_lifecycle import AutonomousTaskRecord
from .service import coordination_plan

logger = logging.getLogger(__name__)

_PLANT = re.compile(r"\b(plant|pothos|succulent|houseplant|monstera|ficus|fern|orchid|cactus|aloe|leaf|leaves|foliage)\b", re.I)
_SYMPTOM = re.compile(r"\b(yellow|yellowing|brown|browning|wilting|wilted|droop|dying|disease|spots?|pests?|fungus|unhealthy|discolor|blight)\b", re.I)
_APPLIANCE = re.compile(r"\b(dishwasher|washing machine|refrigerator|fridge|dryer|hvac|furnace|air conditioner|microwave|oven|water heater|appliance|dehumidifier)\b", re.I)
_FAULT = re.compile(r"\b(error|fault|leak|broken|malfunction|odor|smell|not working|failure|warning)\b", re.I)
_HAZARD = re.compile(r"\b(gas leak|electrical shock|live wire|fire|smoke alarm|poison|asbestos|carbon monoxide)\b", re.I)


def research_topic(task: AutonomousTaskRecord):
    """Research condition uncertainty, not every chore or every photographed item."""
    payload = task.task_payload or {}
    evidence = str(payload.get('evidence_summary') or '')[:500]
    combined = ' '.join((task.title, task.action, evidence))
    if _HAZARD.search(combined):
        return None
    from app.research.models import ResearchPurpose
    if _PLANT.search(combined) and _SYMPTOM.search(combined):
        return (ResearchPurpose.PLANT_CARE, f"Houseplant visible symptoms care guidance: {task.title[:140]}")
    if _APPLIANCE.search(combined) and _FAULT.search(combined):
        return (ResearchPurpose.APPLIANCE_GUIDANCE, f"Household appliance issue guidance: {task.title[:140]}")
    return None


def scene_research_topics(summary: dict) -> list[tuple]:
    """Research independently corroborated, visible objects, even without a task.

    Research never itself establishes a species, fault, diagnosis, or task.
    Deliberately send only bounded visual descriptions, not photos or household history.
    """
    from app.research.models import ResearchPurpose
    claims = [str(x).strip()[:240] for x in (summary.get('evidence') or [])
              if isinstance(x, str) and x.strip()]
    if not claims:
        return []
    all_claims = ' '.join(claims)
    if _HAZARD.search(all_claims):
        return []
    result = []
    for pattern, purpose, prefix in (
        (_PLANT, ResearchPurpose.PLANT_CARE,
         'Possible houseplant types, ordinary care, and potential causes of visibly observed symptoms; do not assume a diagnosis:'),
        (_APPLIANCE, ResearchPurpose.APPLIANCE_GUIDANCE,
         'Possible appliance type, standard maintenance, and safe troubleshooting; verify the exact model before product-specific advice:'),
    ):
        relevant = [x for x in claims if pattern.search(x)][:3]
        if relevant:
            query = f"{prefix} {' '.join(relevant)}"[:500]
            result.append((purpose, query))
    return result[:2]




_KNOWN_PLANTS = re.compile(r"\b(pothos|monstera|orchid|aloe|cactus|ficus|fern|snake plant|peace lily|philodendron)\b", re.I)


def visible_object_insights(summary: dict, media_id: str) -> list[dict]:
    """Summarize verified object evidence separately from physical room identity.

    This is an observation-level object reference, not a persistent multi-view
    identity claim. A photo containing a plant does not establish its room.
    """
    raw = summary.get('evidence') or []
    claims = [item.strip()[:240] for item in raw if isinstance(item, str) and item.strip()]
    insights = []
    for kind, matcher, title in (('plant', _PLANT, 'Houseplant'), ('appliance', _APPLIANCE, 'Household appliance')):
        relevant = [item for item in claims if matcher.search(item)][:3]
        if not relevant or any(_HAZARD.search(x) for x in relevant):
            continue
        identity = None
        if kind == 'plant':
            names = [m.group(0).lower() for fact in relevant for m in _KNOWN_PLANTS.finditer(fact)]
            identity = names[0].title() if names else None
        insight = {
            'object_id': f'observed:{media_id}:{kind}',
            'kind': kind,
            'label': f'Possible {identity}' if identity else title,
            'identity_status': 'tentative' if identity else 'unconfirmed',
            'visible_evidence': relevant,
            'explanation': ('Species suggested by reviewed visual wording, not independently diagnosed.'
                if identity else 'Exact identity has not been verified from this photograph.'),
            'research_sources': [],
        }
        insights.append(insight)
    return insights


def plan_signature(plan: dict) -> str:
    """Fingerprint material changes only, not clock seconds or provider wording."""
    observed = {
        'presence': plan['presence']['state'], 'available': plan['availability']['state'],
        'quiet': plan['quiet_hours']['active'],
        'in_window': plan['preferred_minutes_remaining'] > 0,
        'tasks': [(t['task_id'], t['status'], t['priority'], t['duration_max'],
                   t.get('progress_percent')) for t in plan['tasks']],
    }
    return sha256(json.dumps(observed, sort_keys=True).encode('utf-8')).hexdigest()


class HouseholdAutoOrchestrator:
    def __init__(self, sessions, *, provider=None, advice=None):
        self.sessions = sessions
        self.provider = provider
        self.advice = advice

    def _claim(self, job_id: str):
        """Durable at-most-once claim for a completed scan in normal operation."""
        with self.sessions.begin() as db:
            job = db.get(AutonomousScanJob, job_id)
            if not job or job.state != 'completed':
                return None


            summary = dict(job.review_summary or {})
            if not job.room_id and not summary.get('object_id'):
                return None
            if summary.get('automatic_coordination', {}).get('status') in ('running', 'completed'):
                return None
            summary['automatic_coordination'] = {
                'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat()}
            job.review_summary = summary
            return job.household_id, job.media_id, job.room_id, summary

    def _finish(self, job_id: str, result: dict):
        with self.sessions.begin() as db:
            job = db.get(AutonomousScanJob, job_id)
            if job is not None:
                summary = dict(job.review_summary or {})
                summary['automatic_coordination'] = result
                job.review_summary = summary

    def after_scan(self, job_id: str):
        claim = self._claim(job_id)
        if claim is None:
            return None
        household_id, media_id, room_id, summary = claim
        output = {'status': 'completed', 'research_status': 'not_needed',
                  'researched_tasks': 0, 'source_count': 0, 'planning_status': 'not_needed'}
        try:


            updates = summary.get('progress_results') or {}
            if not isinstance(updates, dict):
                updates = {}
            with self.sessions() as db:
                tasks = db.scalars(select(AutonomousTaskRecord).where(
                    AutonomousTaskRecord.household_id == household_id,
                    AutonomousTaskRecord.state.notin_(['completed', 'dismissed'])
                )).all()
                candidates = sorted((task for task in tasks if
                    (task.task_payload or {}).get('evidence', {}).get('media_id') == media_id
                    or (task.id in updates and (
                        (room_id is not None and task.physical_room_id == room_id)
                        or (summary.get('object_id') is not None and task.object_id == summary['object_id'])))),
                    key=lambda task: task.created_at, reverse=True)[:2]
                candidate_ids = [task.id for task in candidates]
            scene_topics = scene_research_topics(summary)
            from .scene_focus import classify_scene_focus
            focus = summary.get('scene_focus')
            if not isinstance(focus, dict):
                focus = classify_scene_focus(summary.get('evidence') or [], summary.get('room_category'))
            output['scene_focus'] = focus
            object_insights = visible_object_insights(summary, media_id)
            if object_insights:
                output['object_insights'] = object_insights
            if not candidate_ids and not scene_topics:
                output['planning_status'] = 'unchanged_scene'
                self._finish(job_id, output)
                return output

            from app.research.provider import TavilyResearchProvider
            from app.research.models import ResearchRequest
            from app.services.effort_research import research_existing_task_duration
            provider = self.provider
            owned = False
            try:
                if provider is None:
                    provider = TavilyResearchProvider()
                    owned = True



                scene_sources = []
                for purpose, query in scene_topics:
                    try:
                        result = provider.search(ResearchRequest(
                            query=query, purpose=purpose, max_results=3))
                        sources = [{'title': item.title[:160], 'url': str(item.url),
                            'excerpt': re.sub(r'[#*\s]+', ' ', item.content[:450]).strip()[:220]}
                            for item in result.evidence[:3] if str(item.url).startswith('https://')]
                        scene_sources.append({'topic': purpose.value, 'sources': sources,
                            'note': 'Possible identification and care guidance, not a visual diagnosis.'})
                        output['source_count'] += len(sources)
                    except Exception as exc:
                        logger.warning('Scene Tavily research unavailable (%s): %s',
                            purpose.value, type(exc).__name__)
                if scene_sources:
                    output['scene_research'] = scene_sources
                    for insight in object_insights:
                        purpose = 'plant_care' if insight['kind'] == 'plant' else 'appliance_guidance'
                        matching = next((item for item in scene_sources if item['topic'] == purpose), None)
                        if matching:
                            insight['research_sources'] = matching['sources']
                    output['research_status'] = 'sources_found' if any(
                        x['sources'] for x in scene_sources) else 'no_supported_sources'
                for task_id in candidate_ids:
                    with self.sessions() as db:
                        task = db.get(AutonomousTaskRecord, (household_id, task_id))
                        if task is None or task.state in ('completed', 'dismissed'):
                            continue
                        payload = dict(task.task_payload or {})
                        topic = research_topic(task)
                        no_sources = len(payload.get('estimate_sources') or []) < 2

                        existing_guidance = payload.get('automatic_guidance')
                        def recently_attempted(key):
                            stamp = payload.get(key)
                            if not isinstance(stamp, str):
                                return False
                            try:
                                previous = datetime.fromisoformat(stamp)
                                return (datetime.now(timezone.utc) - previous.astimezone(timezone.utc)) < timedelta(hours=24)
                            except ValueError:
                                return False
                        can_search_guidance = topic and not existing_guidance and not recently_attempted('guidance_research_attempted_at')
                        scene_guidance = next((x for x in scene_sources
                            if topic and x['topic'] == topic[0].value and x['sources']), None)
                        if can_search_guidance and scene_guidance:
                            can_search_guidance = False
                            with self.sessions.begin() as target_db:
                                target = target_db.get(AutonomousTaskRecord, (household_id, task_id))
                                if target and target.state not in ('completed', 'dismissed'):
                                    target_payload = dict(target.task_payload or {})
                                    target_payload['automatic_guidance'] = {
                                        **scene_guidance,
                                        'retrieved_at': datetime.now(timezone.utc).isoformat()}
                                    target_payload['guidance_research_attempted_at'] = datetime.now(timezone.utc).isoformat()
                                    target.task_payload = target_payload
                                    output['researched_tasks'] += 1
                        can_search_duration = no_sources and not recently_attempted('duration_research_attempted_at')
                        task_title, task_action = task.title, task.action
                        safe_duration = not _HAZARD.search(task_title + ' ' + task_action)
                    if can_search_duration and safe_duration:
                        with self.sessions.begin() as db:
                            record = db.get(AutonomousTaskRecord, (household_id, task_id))
                            if record:
                                payload = dict(record.task_payload or {})
                                payload['duration_research_attempted_at'] = datetime.now(timezone.utc).isoformat()
                                record.task_payload = payload
                        estimate = research_existing_task_duration(task_title, task_action, provider=provider)
                        if estimate is not None:
                            with self.sessions.begin() as db:
                                record = db.get(AutonomousTaskRecord, (household_id, task_id))
                                if record and record.state not in ('completed', 'dismissed'):
                                    payload = dict(record.task_payload or {})
                                    if len(payload.get('estimate_sources') or []) < 2:
                                        record.effort_min = estimate.minimum_minutes
                                        record.effort_max = estimate.maximum_minutes
                                        payload['estimate_sources'] = estimate.source_urls
                                        payload['estimate_rationale'] = estimate.rationale
                                        record.task_payload = payload
                                        output['source_count'] += len(estimate.source_urls)
                    if can_search_guidance:
                        try:
                            with self.sessions.begin() as db:
                                record = db.get(AutonomousTaskRecord, (household_id, task_id))
                                if record:
                                    payload = dict(record.task_payload or {})
                                    payload['guidance_research_attempted_at'] = datetime.now(timezone.utc).isoformat()
                                    record.task_payload = payload
                            purpose, query = topic
                            result = provider.search(ResearchRequest(query=query[:500], purpose=purpose, max_results=3))
                            sources = [{'title': item.title[:160], 'url': str(item.url)}
                                       for item in result.evidence[:3]
                                       if str(item.url).startswith('https://')]
                            if sources:
                                with self.sessions.begin() as db:
                                    record = db.get(AutonomousTaskRecord, (household_id, task_id))
                                    if record and record.state not in ('completed', 'dismissed'):
                                        payload = dict(record.task_payload or {})
                                        if not payload.get('automatic_guidance'):
                                            payload['automatic_guidance'] = {
                                                'topic': purpose.value, 'sources': sources,
                                                'note': 'Research offers possible explanations, not a diagnosis or proof of a condition.',
                                                'retrieved_at': datetime.now(timezone.utc).isoformat()}
                                            record.task_payload = payload
                                            output['researched_tasks'] += 1
                                            output['source_count'] += len(sources)
                        except Exception as exc:
                            logger.warning('Automatic household guidance unavailable: %s', type(exc).__name__)



                for task_id in candidate_ids:
                    with self.sessions.begin() as db:
                        record = db.get(AutonomousTaskRecord, (household_id, task_id))
                        if record is None or not object_insights:
                            continue
                        payload = dict(record.task_payload or {})
                        evidence_text = ' '.join((record.title, record.action,
                            str(payload.get('evidence_summary') or '')))
                        match = next((item for item in object_insights if
                            (_PLANT if item['kind'] == 'plant' else _APPLIANCE).search(evidence_text)), None)
                        if match and (payload.get('evidence') or {}).get('media_id') == media_id:
                            payload['observed_object'] = {key: match[key] for key in
                                ('object_id', 'kind', 'label', 'identity_status', 'visible_evidence', 'explanation')}
                            record.task_payload = payload
                if output['researched_tasks'] or any(x['sources'] for x in scene_sources):
                    output['research_status'] = 'sources_found'
                elif output['source_count']:
                    output['research_status'] = 'duration_sources_found'
                else:
                    output['research_status'] = 'no_supported_sources'
            except Exception as exc:
                logger.warning('Automatic household research unavailable: %s', type(exc).__name__)
                output['research_status'] = 'unavailable'
            finally:
                if owned and provider is not None:
                    provider.close()


            plan = coordination_plan(self.sessions, household_id)
            output['plan_signature'] = plan_signature(plan)
            if plan['tasks']:
                try:
                    from .nemotron import advise_coordination
                    result = (self.advice or advise_coordination)(plan)
                    output['planning_status'] = 'advised' if result.get('source') == 'nebius_token_factory_nvidia_nemotron' else 'deterministic'
                    output['advice'] = {
                        'model': result.get('model'), 'summary': str(result.get('summary') or '')[:320],
                        'reason': str(result.get('reason') or '')[:320],
                        'selected_task_id': result.get('selected_task_id'),
                        'source': result.get('source')}
                except Exception as exc:
                    logger.warning('Automatic Nemotron planning unavailable: %s', type(exc).__name__)
                    output['planning_status'] = 'unavailable'
            self._finish(job_id, output)
            return output
        except Exception as exc:
            logger.warning('Post-scan automation failed: %s', type(exc).__name__)
            output['status'] = 'failed'
            output['planning_status'] = 'unavailable'
            self._finish(job_id, output)
            return output

    def recover_recent_scans(self, *, max_scans: int = 2) -> int:
        """Bounded catch-up for completed reviews missed when worker flag was off.

        Only recent scans with no orchestration marker. Never re-run visual models;
        after_scan's durable marker prevents duplicate Tavily/Nemotron calls.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        with self.sessions() as db:
            jobs = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.state == 'completed',
                AutonomousScanJob.room_id.is_not(None),
                AutonomousScanJob.updated_at >= cutoff,
            ).order_by(AutonomousScanJob.updated_at.desc()).limit(50)).all()
            pending = [job.id for job in jobs if not (
                job.review_summary or {}).get('automatic_coordination')][:max_scans]
        completed = 0
        for job_id in pending:
            if self.after_scan(job_id) is not None:
                completed += 1
        return completed

    def on_context_tick(self) -> int:
        """Replan when saved availability, presence or eligibility materially changes.

        Called by the existing worker's five-minute pulse, never by a page render.
        No paid call when there is still no executable work.
        """
        count = 0
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.state == 'completed'
            ).order_by(AutonomousScanJob.updated_at.desc()).limit(100)).all()
            household_ids = list(dict.fromkeys(row.household_id for row in rows))[:3]
        for household_id in household_ids:
            with self.sessions() as db:
                recent = db.scalars(select(AutonomousScanJob).where(
                    AutonomousScanJob.household_id == household_id,
                    AutonomousScanJob.state == 'completed',
                ).order_by(AutonomousScanJob.updated_at.desc()).limit(25)).all()
                latest = next((j for j in recent if (j.review_summary or {}).get(
                    'automatic_coordination', {}).get('status') == 'completed'), None)
                if latest is None:
                    continue
                job_id = latest.id
            plan = coordination_plan(self.sessions, household_id)
            signature = plan_signature(plan)
            with self.sessions.begin() as db:
                job = db.get(AutonomousScanJob, job_id)
                if job is None:
                    continue
                summary = dict(job.review_summary or {})
                status = dict(summary.get('automatic_coordination') or {})
                if status.get('plan_signature') == signature:
                    continue


                status['plan_signature'] = signature
                summary['automatic_coordination'] = status
                job.review_summary = summary
            if plan['groups'].get('NOW', 0) > 0:
                try:
                    from .nemotron import advise_coordination
                    result = (self.advice or advise_coordination)(plan)
                    advice = {key: result.get(key) for key in (
                        'model', 'summary', 'reason', 'selected_task_id', 'source')}
                    planning_status = 'advised'
                except Exception as exc:
                    logger.warning('Automatic context replanning unavailable: %s', type(exc).__name__)
                    advice = None
                    planning_status = 'unavailable'
            else:
                advice = {'model':None, 'selected_task_id':None,
                    'summary':'No household work is currently ready to start.',
                    'reason':'Approval, availability, timing or duration evidence is still required.',
                    'source':'deterministic_household_constraints'}
                planning_status = 'deterministic'
            with self.sessions.begin() as db:
                job = db.get(AutonomousScanJob, job_id)
                if job is not None:
                    summary = dict(job.review_summary or {})
                    state = dict(summary.get('automatic_coordination') or {})
                    if state.get('plan_signature') == signature:
                        state.update({'planning_status':planning_status, 'advice':advice})
                        summary['automatic_coordination'] = state
                        job.review_summary = summary
                        count += 1
        return count
