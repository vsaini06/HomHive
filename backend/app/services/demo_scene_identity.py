"""Exact-byte identity for verified, bundled demo photo families only.

This is not a general room recognizer. User photos and edited/re-encoded
images never inherit relationships from filename, client metadata or category.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _scenes() -> dict:
    path = Path(__file__).with_name("demo_scene_manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def verified_demo_scene(image: bytes) -> dict | None:
    if not image:
        return None
    return _scenes().get(hashlib.sha256(image).hexdigest())


def base_room_category(label: str | None) -> str | None:
    if not isinstance(label, str) or not label.strip():
        return None
    import re
    return re.sub(r"\s+[2-9][0-9]*$", "", label.strip()).casefold()
