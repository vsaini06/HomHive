"""Conservative view-focus hints from independently reviewed scene evidence.

A scene focus is not a physical room match, diagnosis, or permanent object identity.
The three display modes keep objects and rooms conceptually separate.
"""
from __future__ import annotations
import re

_OBJECT = re.compile(r"\b(plant|pothos|leaf|leaves|foliage|monstera|fern|orchid|cactus|appliance|dishwasher|refrigerator|dryer|microwave|furnace|washing machine|air conditioner)\b", re.I)
_LANDMARKS = ("door", "window", "sink", "counter", "cabinet", "bed", "desk", "wall", "floor", "ceiling", "shower", "stove", "shelf", "wardrobe", "room layout", "washer", "washing machine", "dryer", "fence", "patio", "shed", "deck", "garden bed", "driveway")
_OUTDOOR_GROUND = re.compile(r"\b(lawn|grass|yard|backyard|garden beds?|patio|fence|shed|landscaping|walkway|driveway)\b", re.I)
_OBJECT_CATEGORIES = {"indoor plants", "houseplants", "plant closeup", "plant close-up", "appliance closeup", "appliance close-up"}
_KNOWN_ROOMS = {"kitchen", "bedroom", "bathroom", "garage", "laundry", "laundry room", "living room", "dining room", "utility", "utility room", "entryway", "closet", "office", "pantry", "balcony", "hallway", "outdoor", "backyard", "yard", "garden", "patio"}


def classify_scene_focus(evidence: list[str], room_category: str | None = None,
                         verified_demo_category: str | None = None) -> dict:
    """Return an evidence-scoped interface hint, never an automatic room assignment."""
    facts = [fact.strip()[:350] for fact in evidence if isinstance(fact, str) and fact.strip()]
    content = " ".join(facts)
    category = (room_category or "").strip().lower()
    demo = (verified_demo_category or "").strip().lower()
    has_object = bool(_OBJECT.search(content))
    landmark_count = sum(bool(re.search(r"\b" + re.escape(word) + r"\b", content, re.I)) for word in _LANDMARKS)
    # The reviewed model supplies an open-world space label. A fixed list of rooms must not
    # force an otherwise supported scene to become unknown.
    has_room = bool(category) and category not in _OBJECT_CATEGORIES and not re.search(
        r"\b(close[ -]?up|macro shot|isolated object|product shot)\b", category, re.I)
    if demo in _OBJECT_CATEGORIES:
        focus, basis = "object", "Verified demo scene is object-focused; room location is not established"
    elif demo and demo == category and has_room and landmark_count < 2:
        focus, basis = "space", "Verified full-scene demo category and independently reviewed room context"
    elif category in {"outdoor", "backyard", "yard", "garden", "patio"} and _OUTDOOR_GROUND.search(content) and landmark_count < 2:
        focus, basis = "space", "Reviewed lawn or outdoor structural context, not a plant close-up"
    elif has_object and has_room and landmark_count >= 2:
        focus, basis = "hybrid", "Reviewed object evidence and multiple spatial landmarks"
    elif (has_object or (facts and not has_room)) and landmark_count < 2:
        focus, basis = "object", "Reviewed object or close-view evidence without sufficient room landmarks"
    elif has_room:
        focus, basis = "space", "Reviewed room context; physical room identity is a separate check"
    else:
        focus, basis = "unknown", "Insufficient corroborated detail to classify the view"
    return {"focus": focus, "basis": basis, "location_confirmed": False}
