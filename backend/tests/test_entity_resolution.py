import pytest
from pydantic import ValidationError

from app.models import (
    EntityIdentificationCandidate,
    EntityResolutionResult,
    EntityResolutionStatus,
    EntityType,
    HouseholdEntity,
    EntityMatchEvidence,
)

from app.services import (
    generate_match_evidence,
    is_entity_compatible,
    resolve_entity,
    resolve_entity_automatically,
)

#-tests-

#-1-
def test_entity_resolution_match():
    result = EntityResolutionResult(
        status=EntityResolutionStatus.MATCH,
        matched_entity_id="entity_plant_001",
        confidence=0.94,
        reasons=[
            "same location",
            "same identified species",
        ],
    )

    assert result.status == EntityResolutionStatus.MATCH
    assert result.matched_entity_id == "entity_plant_001"
    assert result.confidence == 0.94

#-2-
def test_entity_resolution_create():
    result = EntityResolutionResult(
        status=EntityResolutionStatus.CREATE,
        confidence=0.91,
        reasons=[
            "no compatible existing entity",
        ],
    )

    assert result.status == EntityResolutionStatus.CREATE
    assert result.matched_entity_id is None

#-3-
def test_entity_resolution_uncertain():
    result = EntityResolutionResult(
        status=EntityResolutionStatus.UNCERTAIN,
        confidence=0.55,
        reasons=[
            "multiple similar entities in location",
        ],
    )

    assert result.status == EntityResolutionStatus.UNCERTAIN
    assert result.matched_entity_id is None

#-4-
def test_resolution_rejects_confidence_above_one():
    with pytest.raises(ValidationError):
        EntityResolutionResult(
            status=EntityResolutionStatus.MATCH,
            matched_entity_id="entity_001",
            confidence=1.1,
        )

#-5-
def test_resolution_rejects_negative_confidence():
    with pytest.raises(ValidationError):
        EntityResolutionResult(
            status=EntityResolutionStatus.UNCERTAIN,
            confidence=-0.1,
        )

#-6-
def test_matching_entity_is_compatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )

    assert is_entity_compatible(
        candidate,
        "living_room",
        entity,
    )

#-7-
def test_different_entity_type_is_incompatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="living_room",
    )

    assert not is_entity_compatible(
        candidate,
        "living_room",
        entity,
    )

#-8-
def test_different_entity_type_is_incompatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="living_room",
    )

    assert not is_entity_compatible(
        candidate,
        "living_room",
        entity,
    )

#-9-
def test_different_location_is_incompatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Bedroom Plant",
        location="bedroom",
        identity="Monstera deliciosa",
    )

    assert not is_entity_compatible(
        candidate,
        "living_room",
        entity,
    )

#-10-
def test_conflicting_identity_is_incompatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Ficus lyrata",
    )

    assert not is_entity_compatible(
        candidate,
        "living_room",
        entity,
    )

#-11-
def test_unknown_candidate_identity_can_be_compatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity=None,
        confidence=0.80,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )

    assert is_entity_compatible(
        candidate,
        "living_room",
        entity,
    )

#-12-
def test_resolve_entity_creates_when_no_compatible_entity():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[],
    )

    assert result.status == EntityResolutionStatus.CREATE
    assert result.matched_entity_id is None
    assert result.confidence == 0.90

#-13-
def test_single_compatible_entity_without_evidence_is_uncertain():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    existing_entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[
            existing_entity,
        ],
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None

#-14-
def test_resolve_entity_is_uncertain_with_multiple_compatible_entities():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    first_entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Plant One",
        location="living_room",
        identity="Monstera deliciosa",
    )
    second_entity = HouseholdEntity(
        id="entity_plant_002",
        entity_type=EntityType.PLANT,
        name="Plant Two",
        location="living_room",
        identity="Monstera deliciosa",
    )
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[
            first_entity,
            second_entity,
        ],
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None

#-15-
def test_resolve_entity_ignores_incompatible_entities():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.90,
    )
    washer = HouseholdEntity(
        id="entity_washer_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="laundry_room",
        identity="LG WM4000HWA",
    )
    monstera = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )
    evidence = EntityMatchEvidence(
        entity_id="entity_plant_001",
        score=0.92,
        reasons=[
            "matching visible attributes",
        ],
    )
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[
            washer,
            monstera,
        ],
        match_evidence=[
            evidence,
        ],
    )

    assert (
        result.status
        == EntityResolutionStatus.MATCH
    )
    assert (
        result.matched_entity_id
        == "entity_plant_001"
    )

#-16-
def test_strong_match_evidence_resolves_entity():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.95,
    )
    entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )
    evidence = EntityMatchEvidence(
        entity_id="entity_plant_001",
        score=0.92,
        reasons=[
            "matching visible attributes",
            "same physical placement",
        ],
    )
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[entity],
        match_evidence=[evidence],
    )

    assert result.status == EntityResolutionStatus.MATCH
    assert (
        result.matched_entity_id
        == "entity_plant_001"
    )
    assert result.confidence == 0.92

#-17-
def test_weak_match_evidence_remains_uncertain():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.95,
    )
    entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )
    evidence = EntityMatchEvidence(
        entity_id="entity_plant_001",
        score=0.60,
        reasons=[
            "same general appearance",
        ],
    )
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[entity],
        match_evidence=[evidence],
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None

#-18-
def test_multiple_strong_matches_remain_uncertain():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.95,
    )
    first = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Plant One",
        location="living_room",
        identity="Monstera deliciosa",
    )
    second = HouseholdEntity(
        id="entity_002",
        entity_type=EntityType.PLANT,
        name="Plant Two",
        location="living_room",
        identity="Monstera deliciosa",
    )
    evidence = [
        EntityMatchEvidence(
            entity_id="entity_001",
            score=0.91,
        ),
        EntityMatchEvidence(
            entity_id="entity_002",
            score=0.89,
        ),
    ]
    result = resolve_entity(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[
            first,
            second,
        ],
        match_evidence=evidence,
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None

#-19-
def test_match_evidence_scores_exact_identity():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.95,
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )
    evidence = generate_match_evidence(
        candidate,
        entity,
    )

    assert evidence.score == 0.50
    assert (
        "exact identity match"
        in evidence.reasons
    )

#-20-
def test_match_evidence_scores_matching_attributes():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.APPLIANCE,
        identity="LG WM4000HWA",
        confidence=0.95,
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="laundry_room",
        identity="LG WM4000HWA",
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    evidence = generate_match_evidence(
        candidate,
        entity,
    )

    assert evidence.score == 1.0

#-21-
def test_match_evidence_scores_partial_attribute_match():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.APPLIANCE,
        identity=None,
        confidence=0.90,
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="laundry_room",
        attributes={
            "color": "white",
            "door": "top_load",
        },
    )
    evidence = generate_match_evidence(
        candidate,
        entity,
    )

    assert evidence.score == 0.25

#-22-
def test_match_evidence_is_zero_without_shared_evidence():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity=None,
        confidence=0.80,
        attributes={},
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Plant",
        location="living_room",
        identity="Monstera deliciosa",
        attributes={
            "pot_color": "white",
        },
    )
    evidence = generate_match_evidence(
        candidate,
        entity,
    )

    assert evidence.score == 0.0
    assert evidence.reasons == []

#-23-
def test_automatic_resolution_creates_when_no_entity_is_compatible():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.95,
    )
    result = resolve_entity_automatically(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[],
    )

    assert (
        result.status
        == EntityResolutionStatus.CREATE
    )
    assert result.matched_entity_id is None

#-24-
def test_automatic_resolution_matches_with_strong_evidence():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.APPLIANCE,
        identity="LG WM4000HWA",
        confidence=0.95,
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    entity = HouseholdEntity(
        id="entity_washer_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="laundry_room",
        identity="LG WM4000HWA",
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    result = resolve_entity_automatically(
        candidate=candidate,
        observed_location="laundry_room",
        known_entities=[entity],
    )

    assert (
        result.status
        == EntityResolutionStatus.MATCH
    )
    assert (
        result.matched_entity_id
        == "entity_washer_001"
    )
    assert result.confidence == 1.0

#-25-
def test_automatic_resolution_does_not_match_on_identity_alone():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.95,
    )
    entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )
    result = resolve_entity_automatically(
        candidate=candidate,
        observed_location="living_room",
        known_entities=[entity],
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None

#-26-
def test_automatic_resolution_is_uncertain_for_multiple_strong_matches():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.APPLIANCE,
        identity="LG WM4000HWA",
        confidence=0.95,
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    first = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer One",
        location="laundry_room",
        identity="LG WM4000HWA",
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    second = HouseholdEntity(
        id="entity_002",
        entity_type=EntityType.APPLIANCE,
        name="Washer Two",
        location="laundry_room",
        identity="LG WM4000HWA",
        attributes={
            "color": "white",
            "door": "front_load",
        },
    )
    result = resolve_entity_automatically(
        candidate=candidate,
        observed_location="laundry_room",
        known_entities=[
            first,
            second,
        ],
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None

#-27-
def test_conflicting_attributes_prevent_strong_match():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.APPLIANCE,
        identity="LG WM4000HWA",
        confidence=0.95,
        attributes={
            "color": "white",
            "door": "front_load",
            "control": "digital",
        },
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="laundry_room",
        identity="LG WM4000HWA",
        attributes={
            "color": "white",
            "door": "front_load",
            "control": "analog",
        },
    )
    evidence = generate_match_evidence(
        candidate,
        entity,
    )

    assert evidence.score < 0.80
    assert (
        "conflicting entity attributes"
        in evidence.reasons
    )

#-28-
def test_conflicting_attributes_keep_automatic_resolution_uncertain():
    candidate = EntityIdentificationCandidate(
        entity_type=EntityType.APPLIANCE,
        identity="LG WM4000HWA",
        confidence=0.95,
        attributes={
            "color": "white",
            "door": "front_load",
            "control": "digital",
        },
    )
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Washer",
        location="laundry_room",
        identity="LG WM4000HWA",
        attributes={
            "color": "white",
            "door": "front_load",
            "control": "analog",
        },
    )
    result = resolve_entity_automatically(
        candidate=candidate,
        observed_location="laundry_room",
        known_entities=[entity],
    )

    assert (
        result.status
        == EntityResolutionStatus.UNCERTAIN
    )
    assert result.matched_entity_id is None