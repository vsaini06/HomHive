from app.models import (
    EntityCandidate,
    EntityMatchAssessment,
    EntityResolution,
    EntityResolutionStatus,
    HouseholdEntity,
)


# HomHive only links an observation to a known object when the evidence
# is strong enough that an automatic match is unlikely to surprise the user.
AUTO_MATCH_SCORE_THRESHOLD = 0.80


def candidate_can_match_entity(
    candidate: EntityCandidate,
    observed_location: str,
    entity: HouseholdEntity,
) -> bool:
    """Check whether an existing household entity is a plausible match."""

    if candidate.entity_type != entity.entity_type:
        return False

    if observed_location != entity.location:
        return False

    # Two known identities that disagree should never be treated as the same object.
    if (
        candidate.identity is not None
        and entity.identity is not None
        and candidate.identity != entity.identity
    ):
        return False

    return True


def assess_entity_match(
    candidate: EntityCandidate,
    entity: HouseholdEntity,
) -> EntityMatchAssessment:
    """Score how well a recognized candidate matches one known household entity."""

    match_score = 0.0
    match_reasons: list[str] = []

    if (
        candidate.identity is not None
        and entity.identity is not None
        and candidate.identity == entity.identity
    ):
        match_score += 0.50
        match_reasons.append(
            "exact identity match"
        )

    shared_attribute_names = set(
        candidate.attributes
    ).intersection(
        entity.attributes
    )

    matching_attribute_names = [
        attribute_name
        for attribute_name in shared_attribute_names
        if (
            candidate.attributes[attribute_name]
            == entity.attributes[attribute_name]
        )
    ]

    conflicting_attribute_names = [
        attribute_name
        for attribute_name in shared_attribute_names
        if (
            candidate.attributes[attribute_name]
            != entity.attributes[attribute_name]
        )
    ]

    if shared_attribute_names:
        matching_attribute_ratio = (
            len(matching_attribute_names)
            / len(shared_attribute_names)
        )

        match_score += (
            matching_attribute_ratio * 0.50
        )

        if matching_attribute_names:
            match_reasons.append(
                "matching entity attributes"
            )

        if conflicting_attribute_names:
            match_reasons.append(
                "conflicting entity attributes"
            )

            # Conflicting known details should block an automatic match,
            # even when the remaining evidence looks strong.
            match_score = min(
                match_score,
                AUTO_MATCH_SCORE_THRESHOLD - 0.01,
            )

    return EntityMatchAssessment(
        entity_id=entity.id,
        score=round(
            match_score,
            4,
        ),
        reasons=match_reasons,
    )


def resolve_entity(
    candidate: EntityCandidate,
    observed_location: str,
    household_entities: list[HouseholdEntity],
    match_assessments: list[EntityMatchAssessment] | None = None,
) -> EntityResolution:
    """Decide whether a candidate matches an existing entity or needs a new one."""

    possible_matches = [
        entity
        for entity in household_entities
        if candidate_can_match_entity(
            candidate=candidate,
            observed_location=observed_location,
            entity=entity,
        )
    ]

    if not possible_matches:
        return EntityResolution(
            status=EntityResolutionStatus.CREATE,
            confidence=candidate.confidence,
            reasons=[
                "no compatible existing entity",
            ],
        )

    assessment_by_entity = {
        assessment.entity_id: assessment
        for assessment in (
            match_assessments or []
        )
    }

    strong_matches: list[
        EntityMatchAssessment
    ] = []

    for entity in possible_matches:
        assessment = assessment_by_entity.get(
            entity.id
        )

        if (
            assessment is not None
            and assessment.score
            >= AUTO_MATCH_SCORE_THRESHOLD
        ):
            strong_matches.append(
                assessment
            )

    if len(strong_matches) == 1:
        matched_entity = strong_matches[0]

        return EntityResolution(
            status=EntityResolutionStatus.MATCH,
            matched_entity_id=(
                matched_entity.entity_id
            ),
            confidence=matched_entity.score,
            reasons=matched_entity.reasons,
        )

    if len(strong_matches) > 1:
        return EntityResolution(
            status=EntityResolutionStatus.UNCERTAIN,
            confidence=max(
                assessment.score
                for assessment in strong_matches
            ),
            reasons=[
                "multiple entities have strong match evidence",
            ],
        )

    return EntityResolution(
        status=EntityResolutionStatus.UNCERTAIN,
        confidence=candidate.confidence,
        reasons=[
            "compatible entities exist but match evidence is insufficient",
        ],
    )


def resolve_entity_candidate(
    candidate: EntityCandidate,
    observed_location: str,
    household_entities: list[HouseholdEntity],
) -> EntityResolution:
    """Assess possible matches and resolve a candidate in one call."""

    possible_matches = [
        entity
        for entity in household_entities
        if candidate_can_match_entity(
            candidate=candidate,
            observed_location=observed_location,
            entity=entity,
        )
    ]

    match_assessments = [
        assess_entity_match(
            candidate=candidate,
            entity=entity,
        )
        for entity in possible_matches
    ]

    return resolve_entity(
        candidate=candidate,
        observed_location=observed_location,
        household_entities=household_entities,
        match_assessments=match_assessments,
    )