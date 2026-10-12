"""Local scene inventory inspection with no household writes."""

import argparse
import json
from pathlib import Path

from app.media.service import detected_image_type
from app.vision.scene import NebiusSceneProvider


def main():
    parser = argparse.ArgumentParser(description='Inspect a household image without saving observations')
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--location', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    image = args.image.read_bytes()
    content_type = detected_image_type(image)
    if content_type is None:
        raise ValueError('Unsupported image content')
    inventory = NebiusSceneProvider().inventory(image, content_type, args.location)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(inventory.model_dump_json(indent=2), encoding='utf-8')
    print(f'Entities: {len(inventory.entities)}; needs_review: {inventory.needs_review}')
    print(f'Report: {args.output}')


if __name__ == '__main__':
    main()
