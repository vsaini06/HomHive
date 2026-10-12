import json

import pytest
from pydantic import ValidationError

from app.evaluation import EvaluationCase, evaluate_results, load_cases
from app.vision.provider import VisionExtraction


def prediction(category="dish_load", value=0.8):
    return VisionExtraction.model_validate({"candidates": [{"category": category, "value": value, "location": "kitchen", "visible_evidence": "Visible household condition"}], "needs_review": False})


def test_perfect_match():
    case = EvaluationCase(id="a", image="a.jpg", location="kitchen", expected={"dish_load": 0.8})
    report = evaluate_results([case], {"a": prediction()})
    assert report["metrics"]["category_precision"] == 1.0
    assert report["metrics"]["severity_mae_matched_only"] == 0.0


def test_omissions_are_not_zeros():
    case = EvaluationCase(id="a", image="a.jpg", location="kitchen", expected={"dish_load": 0.0})
    review = VisionExtraction(candidates=[], needs_review=True)
    report = evaluate_results([case], {"a": review})
    assert report["metrics"]["category_false_negatives"] == 1
    assert report["metrics"]["severity_mae_matched_only"] is None


def test_hallucinated_category_counted():
    case = EvaluationCase(id="a", image="a.jpg", location="kitchen", expected={})
    report = evaluate_results([case], {"a": prediction()})
    assert report["metrics"]["category_false_positives"] == 1
    assert report["metrics"]["category_precision"] == 0.0


def test_absolute_error_and_tolerance():
    case = EvaluationCase(id="a", image="a.jpg", location="kitchen", expected={"dish_load": 0.5}, tolerance=0.2)
    report = evaluate_results([case], {"a": prediction(value=0.8)})
    assert report["metrics"]["severity_mae_matched_only"] == pytest.approx(0.3)
    assert report["metrics"]["severity_within_tolerance_matched_only"] == 0


def test_missing_or_extra_predictions_rejected():
    case = EvaluationCase(id="a", image="a.jpg", location="kitchen")
    with pytest.raises(ValueError):
        evaluate_results([case], {})
    with pytest.raises(ValueError):
        evaluate_results([case], {"a": prediction(), "b": prediction()})


def test_duplicate_manifest_ids_rejected(tmp_path):
    manifest = tmp_path / "cases.json"
    manifest.write_text(json.dumps([{"id": "x", "image": "a.jpg", "location": "kitchen"}] * 2))
    with pytest.raises(ValueError):
        load_cases(manifest)


def test_out_of_range_label_rejected():
    with pytest.raises(ValidationError):
        EvaluationCase(id="a", image="a.jpg", location="kitchen", expected={"dish_load": 1.4})


def test_unsupported_label_rejected():
    with pytest.raises(ValidationError):
        EvaluationCase(id="a", image="a.jpg", location="kitchen", expected={"maintenance_status": 0.2})
