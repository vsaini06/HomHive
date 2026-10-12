import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.observation import ConditionType
from app.vision.provider import VisionExtraction


SUPPORTED = frozenset({
    ConditionType.DISH_LOAD,
    ConditionType.LAUNDRY_LOAD,
    ConditionType.PLANT_CONDITION,
    ConditionType.LAWN_CONDITION,
})


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    image: str = Field(min_length=1)
    location: str = Field(min_length=1)
    expected: dict[ConditionType, float] = Field(default_factory=dict)
    tolerance: float = Field(default=0.2, ge=0.0, le=1.0)
    note: str = ""

    @model_validator(mode="after")
    def valid_categories(self):
        if not set(self.expected).issubset(SUPPORTED):
            raise ValueError("Unsupported evaluation category")
        if any(not (0.0 <= value <= 1.0) for value in self.expected.values()):
            raise ValueError("Expected values must be between zero and one")
        return self


def load_cases(path: Path) -> list[EvaluationCase]:
    cases = [EvaluationCase.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate evaluation IDs")
    return cases


def evaluate_results(cases: list[EvaluationCase], predictions: dict[str, VisionExtraction]) -> dict:
    case_ids = {case.id for case in cases}
    if len(case_ids) != len(cases) or set(predictions) != case_ids:
        raise ValueError("Predictions must cover exactly the labeled cases")
    rows = []
    true_positives = false_positives = false_negatives = 0
    severity_errors = []
    within_tolerance = 0
    review_count = 0
    for case in cases:
        result = predictions[case.id]
        expected = case.expected
        actual = {candidate.category: candidate for candidate in result.candidates}
        matched = set(expected) & set(actual)
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        true_positives += len(matched)
        false_positives += len(extra)
        false_negatives += len(missing)
        review_count += int(result.needs_review)
        for category in matched:
            error = abs(expected[category] - actual[category].value)
            severity_errors.append(error)
            within_tolerance += int(error <= case.tolerance)
        rows.append({
            "id": case.id,
            "needs_review": result.needs_review,
            "expected": {key.value: value for key, value in expected.items()},
            "predicted": {key.value: {"value": candidate.value, "visible_evidence": candidate.visible_evidence} for key, candidate in actual.items()},
            "missing_categories": sorted(key.value for key in missing),
            "unexpected_categories": sorted(key.value for key in extra),
            "absolute_errors": {key.value: round(abs(expected[key] - actual[key].value), 6) for key in matched},
        })
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = true_positives / precision_denominator if precision_denominator else None
    recall = true_positives / recall_denominator if recall_denominator else None
    return {
        "case_count": len(cases),
        "metrics": {
            "category_true_positives": true_positives,
            "category_false_positives": false_positives,
            "category_false_negatives": false_negatives,
            "category_precision": precision,
            "category_recall": recall,
            "severity_mae_matched_only": sum(severity_errors) / len(severity_errors) if severity_errors else None,
            "severity_within_tolerance_matched_only": within_tolerance / len(severity_errors) if severity_errors else None,
            "review_rate": review_count / len(cases) if cases else None,
        },
        "cases": rows,
    }


def evaluate_with_failures(
    cases: list[EvaluationCase],
    predictions: dict[str, VisionExtraction],
    failures: dict[str, str],
) -> dict:
    """Score successful predictions and separately account for failed cases.

    Metrics describe only completed predictions; coverage and failure counts
    must be considered alongside them, never interpreted as overall accuracy.
    """
    ids = {case.id for case in cases}
    if len(ids) != len(cases) or (set(predictions) | set(failures)) != ids:
        raise ValueError("Results must cover exactly the labeled cases")
    if set(predictions) & set(failures):
        raise ValueError("A case cannot have a prediction and a failure")
    completed = [case for case in cases if case.id in predictions]
    report = evaluate_results(completed, predictions)
    report["case_count"] = len(cases)
    report["metrics"]["completed_case_count"] = len(completed)
    report["metrics"]["failed_case_count"] = len(failures)
    report["metrics"]["completion_rate"] = len(completed) / len(cases) if cases else None
    for case in cases:
        if case.id in failures:
            report["cases"].append({
                "id": case.id,
                "status": "failed",
                "error": failures[case.id],
                "expected": {key.value: value for key, value in case.expected.items()},
                "predicted": None,
            })
    by_id = {row["id"]: row for row in report["cases"]}
    report["cases"] = [by_id[case.id] for case in cases]
    for row in report["cases"]:
        if "status" not in row:
            row["status"] = "completed"
    return report
