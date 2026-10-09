from app.models import (
    ActionDecision,
    ActionState,
    ThresholdCrossing,
)


def decide_action(
    crossing: ThresholdCrossing | None,
    min_confidence: float = 0.50,
    plan_ahead_hours: float = 8.0,
) -> ActionDecision | None:
    """Decide whether a predicted threshold crossing needs attention yet."""

    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError(
            "Minimum confidence must be between 0 and 1."
        )

    if plan_ahead_hours <= 0:
        raise ValueError(
            "Planning window must be greater than zero."
        )

    if crossing is None:
        return None

    # Once the threshold is already reached, waiting no longer helps.
    if crossing.hours_to_threshold == 0:
        return ActionDecision(
            location=crossing.location,
            category=crossing.category,
            status=ActionState.ACT_NOW,
            hours_to_threshold=0.0,
            confidence=crossing.confidence,
            reason="threshold already reached",
        )

    # Weak forecasts stay visible, but they should not create work yet.
    if crossing.confidence < min_confidence:
        return ActionDecision(
            location=crossing.location,
            category=crossing.category,
            status=ActionState.MONITOR,
            hours_to_threshold=(
                crossing.hours_to_threshold
            ),
            confidence=crossing.confidence,
            reason=(
                "prediction confidence is below "
                "intervention threshold"
            ),
        )

    if (
        crossing.hours_to_threshold
        <= plan_ahead_hours
    ):
        return ActionDecision(
            location=crossing.location,
            category=crossing.category,
            status=ActionState.PLAN,
            hours_to_threshold=(
                crossing.hours_to_threshold
            ),
            confidence=crossing.confidence,
            reason=(
                "threshold predicted within "
                "planning window"
            ),
        )

    return ActionDecision(
        location=crossing.location,
        category=crossing.category,
        status=ActionState.MONITOR,
        hours_to_threshold=(
            crossing.hours_to_threshold
        ),
        confidence=crossing.confidence,
        reason=(
            "threshold prediction is outside "
            "planning window"
        ),
    )