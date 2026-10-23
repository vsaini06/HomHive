"""Claim-level independent visual corroboration with non-sensitive diagnostics."""
from __future__ import annotations

from dataclasses import dataclass

from .provider import VisionExtraction, VisionCandidate, SpaceCategory
from .verification import IndependentReview


@dataclass(frozen=True)
class ClaimDecision:
    category: str
    status: str
    reason: str


def supported_claims(proposed: VisionExtraction, reviews: tuple[IndependentReview, ...]) -> tuple[list[VisionCandidate], list[ClaimDecision], bool]:
    """Require all configured reviewers for each retained claim; room only if independently supported."""
    if not reviews:
        return [], [ClaimDecision(c.category.value, 'unresolved', 'no_reviewers') for c in proposed.candidates], False
    room = proposed.space_category or SpaceCategory.UNKNOWN
    room_supported = room != SpaceCategory.UNKNOWN and all(
        r.room_supported and r.space_category == room for r in reviews
    )
    accepted: list[VisionCandidate] = []
    decisions: list[ClaimDecision] = []
    for candidate in proposed.candidates:
        assessments = []
        malformed = False
        for review in reviews:
            keys = [c for c in review.claims if c.category == candidate.category.value]
            if len(keys) != 1:
                malformed = True
                break
            assessments.append(keys[0])
        if malformed:
            decisions.append(ClaimDecision(candidate.category.value, 'unresolved', 'missing_or_duplicate_review'))
        elif all(c.visible and c.evidence_supported and c.workload_supported for c in assessments):
            accepted.append(candidate)
            decisions.append(ClaimDecision(candidate.category.value, 'corroborated', 'independent_visual_support'))
        else:
            decisions.append(ClaimDecision(candidate.category.value, 'disputed', 'insufficient_visual_support'))
    if room != SpaceCategory.UNKNOWN and not room_supported:
        return [], [ClaimDecision(c.category.value, "unresolved", "room_not_corroborated") for c in proposed.candidates], False
    return accepted, decisions, room_supported
