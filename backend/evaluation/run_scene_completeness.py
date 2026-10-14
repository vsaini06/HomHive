import argparse
import json
from pathlib import Path

from app.evaluation.scene import ReferenceEntity, score_scene_inventory
from app.vision.scene import SceneInventory


def main():
    parser = argparse.ArgumentParser(description="Score a scene inventory against a reviewed object reference")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reference_payload = json.loads(args.reference.read_text(encoding="utf-8"))
    if not isinstance(reference_payload, list):
        raise ValueError("Reference inventory must be a JSON array")

    reference = [ReferenceEntity.model_validate(item) for item in reference_payload]
    prediction = SceneInventory.model_validate_json(args.prediction.read_text(encoding="utf-8"))
    result = score_scene_inventory(reference, prediction)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"Recall: {result.recall:.4f}; precision: {result.precision:.4f}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
