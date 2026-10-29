import argparse
import json
from time import perf_counter
from pathlib import Path

from app.evaluation import load_cases
from app.evaluation.vision import evaluate_with_failures
from app.media.service import detected_image_type
from app.vision.provider import NebiusVisionProvider, VisionExtraction



def diagnostic_category(exc: Exception) -> str:
    """Return only allowlisted failure categories, never arbitrary provider text."""
    if not isinstance(exc, ValueError):
        return "other_error"
    message = str(exc)
    known = {
        "Invalid image path": "invalid_image_path",
        "Unsupported image content": "unsupported_image",
        "Location is required": "invalid_location",
        "Vision provider returned no text": "missing_response_text",
        "Invalid vision provider response": "invalid_response_schema",
        "Inconsistent vision review status": "invalid_review_status",
        "Vision provider returned unsupported category": "unsupported_category",
        "Vision provider returned empty visual evidence": "empty_visual_evidence",
        "Duplicate vision categories": "duplicate_categories",
    }
    if message.startswith("Vision location mismatch:"):
        return "location_mismatch"
    return known.get(message, "unclassified_value_error")


def run_evaluation(cases, images: Path, provider=None, saved_predictions=None, diagnostics=None):
    predictions = {}
    failures = {}
    if saved_predictions is not None:
        for case in cases:
            if case.id not in saved_predictions:
                failures[case.id] = "MissingSavedPrediction"
                continue
            try:
                predictions[case.id] = VisionExtraction.model_validate(saved_predictions[case.id])
            except ValueError:
                failures[case.id] = "InvalidSavedPrediction"
        return predictions, failures

    if provider is None:
        from app.config.environment import load_local_environment
        load_local_environment()
        provider = NebiusVisionProvider()
    base = images.resolve()
    for case in cases:
        started = perf_counter()
        try:
            image_path = (base / case.image).resolve()
            if not image_path.is_relative_to(base) or not image_path.is_file():
                raise ValueError("Invalid image path")
            image = image_path.read_bytes()
            content_type = detected_image_type(image)
            if content_type is None:
                raise ValueError("Unsupported image content")
            predictions[case.id] = provider.extract(image, content_type, case.location)
            if diagnostics is not None:
                diagnostics[case.id] = {
                    "status": "success",
                    "elapsed_seconds": round(perf_counter() - started, 4),
                    "schema_valid": True,
                }
        except Exception as exc:

            failures[case.id] = type(exc).__name__
            if diagnostics is not None:
                diagnostics[case.id] = {
                    "status": "failure",
                    "elapsed_seconds": round(perf_counter() - started, 4),
                    "schema_valid": False,
                    "error_class": type(exc).__name__,
                    "error_category": diagnostic_category(exc),
                }
    return predictions, failures


def main():
    parser = argparse.ArgumentParser(description="Evaluate vision results without storing household observations")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--predictions", type=Path, help="Read saved predictions instead of making model calls")
    parser.add_argument("--diagnostics", action="store_true", help="Record safe per-case diagnostic information")
    args = parser.parse_args()
    cases = load_cases(args.manifest)
    saved = None
    if args.predictions is not None:
        saved = json.loads(args.predictions.read_text(encoding="utf-8"))
        if isinstance(saved, dict) and "predictions" in saved and "report" in saved:
            saved = saved["predictions"]
        if not isinstance(saved, dict):
            raise ValueError("Saved predictions must be an object keyed by case ID")
    diagnostics = {} if args.diagnostics else None
    predictions, failures = run_evaluation(cases, args.images, saved_predictions=saved, diagnostics=diagnostics)
    report = evaluate_with_failures(cases, predictions, failures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "report": report,
        "predictions": {key: value.model_dump(mode="json") for key, value in predictions.items()},
        "failures": failures,
    }
    if diagnostics is not None:
        output_data["diagnostics"] = diagnostics
    args.output.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
