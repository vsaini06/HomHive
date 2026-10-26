"""Conservative external duration grounding for independently approved household actions."""
from __future__ import annotations

import logging
import re
from statistics import median

from pydantic import ValidationError
from urllib.parse import urlparse

from app.research.models import ResearchPurpose, ResearchRequest
from app.research.provider import TavilyResearchProvider
from app.services.open_world_planning import ActionProposal, EffortEstimate

logger = logging.getLogger(__name__)

_DURATION = re.compile(
    r"\b(?:about|approximately|around|roughly|typically|usually|takes?|spend|allow|need|time[: ]+)?\s*"
    r"(\d{1,3})(?:\s*(?:-|–|to)\s*(\d{1,3}))?\s*"
    r"(minutes?|mins?|hours?|hrs?)\b", re.IGNORECASE,
)
_CONTEXT = re.compile(r"\b(takes?|time|spend|allow|need|lasts?|typically|usually|approximately|about|around|roughly|minutes?|hours?)\b", re.I)


def reported_minutes(content: str) -> int | None:
    """Read explicit time statements; reject large or ambiguous durations."""
    for match in _DURATION.finditer(content[:2500]):
        surrounding = content[max(0, match.start()-65): min(len(content),match.end()+45)]
        if not _CONTEXT.search(surrounding):
            continue
        lower = int(match.group(1))
        upper = int(match.group(2) or lower)
        if upper < lower:
            continue
        factor = 60 if match.group(3).lower().startswith(("hour", "hr")) else 1
        minutes = ((lower + upper) / 2) * factor
        if 3 <= minutes <= 240:
            return round(minutes)
    return None


def ground_action_effort(action: ActionProposal, *, provider=None) -> ActionProposal:
    """Never manufacture effort: two independent published domains must explicitly report time.

    Search is optional and failure never blocks a safe approved task. Model-only estimates
    are deliberately discarded until corroborated by external material.
    """
    cleaned = action.model_copy(update={"estimated_effort": None})
    if action.hazard_or_professional_help:
        return cleaned
    owned = provider is None
    try:
        if owned:
            provider = TavilyResearchProvider()
        request = ResearchRequest(
            query=f'How long does it usually take to {action.title.strip()}? typical hands-on household task duration minutes',
            purpose=ResearchPurpose.HOUSEHOLD_CONTEXT, max_results=5,
        )
        result = provider.search(request)
        per_domain: dict[str, tuple[int, str]] = {}
        for item in result.evidence:
            url = str(item.url)
            parsed = urlparse(url)
            domain = (parsed.hostname or '').lower().removeprefix('www.')
            if parsed.scheme != 'https' or not domain or domain in per_domain:
                continue
            minutes = reported_minutes(item.content)
            if minutes is not None:
                per_domain[domain] = (minutes, url)
        if len(per_domain) < 2:
            return cleaned
        sampled = list(per_domain.values())[:5]
        values = [minutes for minutes, _ in sampled]
        if max(values) > min(values) * 3:
            return cleaned
        mid = round(median(values))
        low = min(values)
        high = max(values)
        estimate = EffortEstimate(
            minimum_minutes=low, maximum_minutes=high,
            rationale=f'Approximate published task durations from {len(sampled)} independent sources; median {mid} min. Actual time depends on scope and preferences.',
            evidence_ids=action.supporting_evidence_ids,
            externally_verified=True,
            source_urls=[url for _, url in sampled],
        )
        return action.model_copy(update={"estimated_effort": estimate})
    except ValidationError as exc:
        # Report only schema locations and error codes, never provider text or credentials.
        fields = [
            '.'.join(map(str, issue['loc'])) + ':' + issue['type']
            for issue in exc.errors(include_url=False, include_context=False, include_input=False)[:5]
        ]
        logger.warning('Task duration research invalid: %s', ', '.join(fields))
        return cleaned
    except Exception as exc:
        logger.warning('Task duration research unavailable: %s', type(exc).__name__)
        return cleaned
    finally:
        if owned and provider is not None:
            provider.close()
