from app.models import (
    InterventionDecision,
    InterventionStatus,
    ThresholdPrediction,
)


def decide_intervention(
    prediction: ThresholdPrediction | None,
    minimum_confidence: float = 0.50,
    planning_window_hours: float = 8.0,
) -> InterventionDecision | None:
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError(
            "Minimum confidence must be between 0 and 1."
        )

    if planning_window_hours <= 0:
        raise ValueError(
            "Planning window must be greater than zero."
        )

    if prediction is None:
        return None

    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError(
            "Minimum confidence must be between 0 and 1."
        )

    if planning_window_hours <= 0:
        raise ValueError(
            "Planning window must be greater than zero."
        )

    if prediction.hours_to_threshold == 0:
        return InterventionDecision(
            location=prediction.location,
            category=prediction.category,
            status=InterventionStatus.ACT_NOW,
            hours_to_threshold=0.0,
            confidence=prediction.confidence,
            reason="threshold already reached",
        )

    if prediction.confidence < minimum_confidence:
        return InterventionDecision(
            location=prediction.location,
            category=prediction.category,
            status=InterventionStatus.MONITOR,
            hours_to_threshold=(
                prediction.hours_to_threshold
            ),
            confidence=prediction.confidence,
            reason="prediction confidence is below intervention threshold",
        )

    if (
        prediction.hours_to_threshold
        <= planning_window_hours
    ):
        return InterventionDecision(
            location=prediction.location,
            category=prediction.category,
            status=InterventionStatus.PLAN,
            hours_to_threshold=(
                prediction.hours_to_threshold
            ),
            confidence=prediction.confidence,
            reason="threshold predicted within planning window",
        )

    return InterventionDecision(
        location=prediction.location,
        category=prediction.category,
        status=InterventionStatus.MONITOR,
        hours_to_threshold=(
            prediction.hours_to_threshold
        ),
        confidence=prediction.confidence,
        reason="threshold prediction is outside planning window",
    )