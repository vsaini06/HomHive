import argparse
import json
from pathlib import Path

from app.evaluation import load_cases
from app.evaluation.vision import evaluate_with_failures
from app.media.service import detected_image_type
from app.vision.provider import NebiusVisionProvider, VisionExtraction


def run_evaluation(cases, images: Path, provider=None, saved_predictions=None):
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
        try:
            image_path = (base / case.image).resolve()
            if not image_path.is_relative_to(base) or not image_path.is_file():
                raise ValueError("Invalid image path")
            image = image_path.read_bytes()
            content_type = detected_image_type(image)
            if content_type is None:
                raise ValueError("Unsupported image content")
            predictions[case.id] = provider.extract(image, content_type, case.location)
        except Exception as exc:
            # Only record the exception class: provider messages may contain private data.
            failures[case.id] = type(exc).__name__
    return predictions, failures


def main():
    parser = argparse.ArgumentParser(description="Evaluate vision results without storing household observations")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--predictions", type=Path, help="Read saved predictions instead of making model calls")
    args = parser.parse_args()
    cases = load_cases(args.manifest)
    saved = None
    if args.predictions is not None:
        saved = json.loads(args.predictions.read_text(encoding="utf-8"))
        if isinstance(saved, dict) and "predictions" in saved and "report" in saved:
            saved = saved["predictions"]
        if not isinstance(saved, dict):
            raise ValueError("Saved predictions must be an object keyed by case ID")
    predictions, failures = run_evaluation(cases, args.images, saved_predictions=saved)
    report = evaluate_with_failures(cases, predictions, failures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "report": report,
        "predictions": {key: value.model_dump(mode="json") for key, value in predictions.items()},
        "failures": failures,
    }, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
