"""Conservative view-focus hints from independently reviewed scene evidence.

A scene focus is not a physical room match, diagnosis, or permanent object identity.
The three display modes keep objects and rooms conceptually separate.
"""
from __future__ import annotations
import re

_OBJECT = re.compile(r"\b(plant|pothos|leaf|leaves|foliage|monstera|fern|orchid|cactus|appliance|dishwasher|refrigerator|dryer|microwave|furnace|washing machine|air conditioner)\b", re.I)
_LANDMARKS = ("door", "window", "sink", "counter", "cabinet", "bed", "desk", "wall", "floor", "ceiling", "shower", "stove", "shelf", "wardrobe", "room layout")
_OBJECT_CATEGORIES = {"indoor plants", "houseplants", "plant closeup", "plant close-up", "appliance closeup", "appliance close-up"}
_KNOWN_ROOMS = {"kitchen", "bedroom", "bathroom", "garage", "laundry", "laundry room", "living room", "dining room", "utility", "utility room", "entryway", "closet", "office", "pantry", "balcony", "hallway"}


def classify_scene_focus(evidence: list[str], room_category: str | None = None,
                         verified_demo_category: str | None = None) -> dict:
    """Return an evidence-scoped interface hint, never an automatic room assignment."""
    facts = [fact.strip()[:350] for fact in evidence if isinstance(fact, str) and fact.strip()]
    content = " ".join(facts)
    category = (room_category or "").strip().lower()
    demo = (verified_demo_category or "").strip().lower()
    has_object = bool(_OBJECT.search(content))
    landmark_count = sum(bool(re.search(r"\b" + re.escape(word) + r"\b", content, re.I)) for word in _LANDMARKS)
    has_room = category in _KNOWN_ROOMS
    if demo in _OBJECT_CATEGORIES:
        focus, basis = "object", "Verified demo scene is object-focused; room location is not established"
    elif has_object and has_room and landmark_count >= 2:
        focus, basis = "hybrid", "Reviewed object evidence and multiple spatial landmarks"
    elif has_object and (not has_room or landmark_count < 2):
        focus, basis = "object", "Reviewed object evidence without sufficient room landmarks"
    elif has_room:
        focus, basis = "space", "Reviewed room context; physical room identity is a separate check"
    else:
        focus, basis = "unknown", "Insufficient corroborated detail to classify the view"
    return {"focus": focus, "basis": basis, "location_confirmed": False}
