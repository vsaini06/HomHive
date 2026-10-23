import json

from app.evaluation import EvaluationCase
from app.evaluation.vision import evaluate_with_failures
from app.vision.provider import VisionExtraction
from evaluation.run_vision import run_evaluation


def case(name):
    return EvaluationCase(id=name, image=f"{name}.png", location="kitchen", expected={"dish_load": 0.5})


def prediction():
    return VisionExtraction.model_validate({
        "candidates": [{"category": "dish_load", "value": 0.5, "location": "kitchen", "visible_evidence": "Visible dishes"}],
        "needs_review": False,
    })


def test_failed_cases_are_explicit_and_not_scored_as_correct():
    report = evaluate_with_failures([case("a"), case("b")], {"a": prediction()}, {"b": "ValueError"})
    metrics = report["metrics"]
    assert metrics["completed_case_count"] == 1
    assert metrics["failed_case_count"] == 1
    assert metrics["completion_rate"] == 0.5
    assert metrics["category_true_positives"] == 1
    assert report["cases"][1]["status"] == "failed"
    assert report["cases"][1]["predicted"] is None


def test_all_failed_does_not_report_perfect_accuracy():
    report = evaluate_with_failures([case("a")], {}, {"a": "ValueError"})
    assert report["metrics"]["category_precision"] is None
    assert report["metrics"]["category_recall"] is None
    assert report["metrics"]["severity_mae_matched_only"] is None
    assert report["metrics"]["completion_rate"] == 0


def test_result_ids_and_failure_ids_must_be_disjoint():
    import pytest
    with pytest.raises(ValueError):
        evaluate_with_failures([case("a")], {"a": prediction()}, {"a": "ValueError"})


def test_saved_predictions_mark_missing_and_invalid_as_failures(tmp_path):
    cases = [case("a"), case("b"), case("c")]
    values = {"a": prediction().model_dump(mode="json"), "b": {"unexpected": True}}
    predictions, failures = run_evaluation(cases, tmp_path, saved_predictions=values)
    assert list(predictions) == ["a"]
    assert failures == {"b": "InvalidSavedPrediction", "c": "MissingSavedPrediction"}


def test_provider_failure_does_not_abort_next_image(tmp_path, monkeypatch):
    from evaluation import run_vision
    class Provider:
        def extract(self, image, content_type, location):
            if image == b"a":
                raise ValueError("SECRET SHOULD NOT LEAK")
            return prediction()
    (tmp_path / "a.png").write_bytes(b"a")
    (tmp_path / "b.png").write_bytes(b"b")
    monkeypatch.setattr(run_vision, "detected_image_type", lambda image: "image/png")
    predictions, failures = run_vision.run_evaluation([case("a"), case("b")], tmp_path, provider=Provider())
    assert list(predictions) == ["b"]
    assert failures == {"a": "ValueError"}
    assert "SECRET" not in json.dumps(failures)


def test_diagnostic_categories_never_expose_unexpected_messages():
    from evaluation.run_vision import diagnostic_category

    assert diagnostic_category(ValueError("Invalid vision provider response")) == "invalid_response_schema"
    assert diagnostic_category(ValueError("Vision location mismatch: expected 'kitchen', received 'garage'")) == "location_mismatch"
    assert diagnostic_category(ValueError("SECRET provider response")) == "unclassified_value_error"
    assert diagnostic_category(RuntimeError("SECRET")) == "other_error"


def test_diagnostics_capture_failure_without_provider_text(tmp_path, monkeypatch):
    from evaluation import run_vision

    class Provider:
        def extract(self, image, content_type, location):
            raise ValueError("Invalid vision provider response")

    (tmp_path / "a.png").write_bytes(b"image")
    monkeypatch.setattr(run_vision, "detected_image_type", lambda data: "image/png")
    diagnostics = {}
    predictions, failures = run_vision.run_evaluation(
        [case("a")], tmp_path, provider=Provider(), diagnostics=diagnostics
    )
    assert predictions == {}
    assert failures == {"a": "ValueError"}
    assert diagnostics["a"]["status"] == "failure"
    assert diagnostics["a"]["schema_valid"] is False
    assert diagnostics["a"]["error_category"] == "invalid_response_schema"
    assert diagnostics["a"]["elapsed_seconds"] >= 0
    assert "error_message" not in diagnostics["a"]


def test_diagnostics_capture_success_without_changing_results(tmp_path, monkeypatch):
    from evaluation import run_vision

    class Provider:
        def extract(self, image, content_type, location):
            return prediction()

    (tmp_path / "a.png").write_bytes(b"image")
    monkeypatch.setattr(run_vision, "detected_image_type", lambda data: "image/png")
    diagnostics = {}
    predictions, failures = run_vision.run_evaluation(
        [case("a")], tmp_path, provider=Provider(), diagnostics=diagnostics
    )
    assert failures == {}
    assert predictions["a"] == prediction()
    assert diagnostics["a"]["status"] == "success"
    assert diagnostics["a"]["schema_valid"] is True
    assert diagnostics["a"]["elapsed_seconds"] >= 0
