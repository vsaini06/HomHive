from app.coordination.scene_focus import classify_scene_focus


def test_object_closeup_from_verified_family():
    result = classify_scene_focus(["Yellow leaves on a potted plant beside a window"], None, "Indoor plants")
    assert result["focus"] == "object"
    assert not result["location_confirmed"]


def test_hybrid_spatial_landmarks():
    result = classify_scene_focus(["Plant with yellow leaves beside the bedroom window, desk, and wall"], "Bedroom")
    assert result["focus"] == "hybrid"


def test_broad_room():
    result = classify_scene_focus(["The kitchen has a counter, sink, and cabinets"], "Kitchen")
    assert result["focus"] == "space"


def test_object_without_room():
    assert classify_scene_focus(["Dishwasher displays error code E2"], None)["focus"] == "object"


def test_no_observation_unknown():
    assert classify_scene_focus([], None)["focus"] == "unknown"


def test_room_category_never_becomes_identity():
    assert not classify_scene_focus(["Kitchen counter"], "Kitchen")["location_confirmed"]
