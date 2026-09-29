from app.models import (
    EntityIdentificationCandidate,
    EntityResolutionResult,
    EntityResolutionStatus,
    HouseholdEntity,
    EntityMatchEvidence,
)

MATCH_THRESHOLD = 0.80

def is_entity_compatible(
    candidate: EntityIdentificationCandidate,
    observed_location: str,
    entity: HouseholdEntity,
) -> bool:
    if candidate.entity_type != entity.entity_type:
        return False
    if observed_location != entity.location:
        return False
    if (
        candidate.identity is not None
        and entity.identity is not None
        and candidate.identity != entity.identity
    ):
        return False
    return True

def generate_match_evidence(
    candidate: EntityIdentificationCandidate,
    entity: HouseholdEntity,
) -> EntityMatchEvidence:
    score = 0.0
    reasons: list[str] = []

    if (
        candidate.identity is not None
        and entity.identity is not None
        and candidate.identity == entity.identity
    ):
        score += 0.50
        reasons.append(
            "exact identity match"
        )

    shared_attributes = set(
        candidate.attributes
    ).intersection(
        entity.attributes
    )

    matching_attributes = [
        attribute
        for attribute in shared_attributes
        if (
            candidate.attributes[attribute]
            == entity.attributes[attribute]
        )
    ]

    conflicting_attributes = [
        attribute
        for attribute in shared_attributes
        if (
            candidate.attributes[attribute]
            != entity.attributes[attribute]
        )
    ]

    if shared_attributes:
        attribute_match_ratio = (
            len(matching_attributes)
            / len(shared_attributes)
        )

        score += (
            attribute_match_ratio * 0.50
        )

        if matching_attributes:
            reasons.append(
                "matching entity attributes"
            )

        if conflicting_attributes:
            reasons.append(
                "conflicting entity attributes"
            )

            score = min(
                score,
                MATCH_THRESHOLD - 0.01,
            )

    return EntityMatchEvidence(
        entity_id=entity.id,
        score=round(score, 4),
        reasons=reasons,
    )

def resolve_entity(
    candidate: EntityIdentificationCandidate,
    observed_location: str,
    known_entities: list[HouseholdEntity],
    match_evidence: list[EntityMatchEvidence] | None = None,
) -> EntityResolutionResult:
    compatible_entities = [
        entity
        for entity in known_entities
        if is_entity_compatible(
            candidate,
            observed_location,
            entity,
        )
    ]
    if not compatible_entities:
        return EntityResolutionResult(
            status=EntityResolutionStatus.CREATE,
            confidence=candidate.confidence,
            reasons=[
                "no compatible existing entity",
            ],
        )
    evidence_by_entity = {
        evidence.entity_id: evidence
        for evidence in (match_evidence or [])
    }

    strong_matches = []
    for entity in compatible_entities:
        evidence = evidence_by_entity.get(
            entity.id
        )
        if (
            evidence is not None
            and evidence.score >= MATCH_THRESHOLD
        ):
            strong_matches.append(evidence)
    if len(strong_matches) == 1:
        match = strong_matches[0]

        return EntityResolutionResult(
            status=EntityResolutionStatus.MATCH,
            matched_entity_id=match.entity_id,
            confidence=match.score,
            reasons=match.reasons,
        )
    if len(strong_matches) > 1:
        return EntityResolutionResult(
            status=EntityResolutionStatus.UNCERTAIN,
            confidence=max(
                match.score
                for match in strong_matches
            ),
            reasons=[
                "multiple entities have strong match evidence",
            ],
        )

    return EntityResolutionResult(
        status=EntityResolutionStatus.UNCERTAIN,
        confidence=candidate.confidence,
        reasons=[
            "compatible entities exist but match evidence is insufficient",
        ],
    )

def resolve_entity_automatically(
    candidate: EntityIdentificationCandidate,
    observed_location: str,
    known_entities: list[HouseholdEntity],
) -> EntityResolutionResult:
    compatible_entities = [
        entity
        for entity in known_entities
        if is_entity_compatible(
            candidate,
            observed_location,
            entity,
        )
    ]

    match_evidence = [
        generate_match_evidence(
            candidate,
            entity,
        )
        for entity in compatible_entities
    ]

    return resolve_entity(
        candidate=candidate,
        observed_location=observed_location,
        known_entities=known_entities,
        match_evidence=match_evidence,
    )