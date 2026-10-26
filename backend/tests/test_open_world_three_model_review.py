from app.services.open_world_live import OpenWorldVision, VisualScene


class Reviewer:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def ask(self, **kwargs):
        self.calls.append(kwargs)
        return self.reply


def scene():
    return VisualScene(room_category="walk-in closet", claims=[
        {"id": "e1", "description": "Clothes scattered across closet floor"},
        {"id": "e2", "description": "Clothing needs to be washed immediately"},
    ])


def test_both_independent_models_review_image_and_disputed_claim_is_withheld():
    primary = Reviewer({})
    claude = Reviewer({"room_supported": True, "claims": [
        {"id": "e1", "supported": True}, {"id": "e2", "supported": True},
    ]})
    openai = Reviewer({"room_supported": True, "claims": [
        {"id": "e1", "supported": True}, {"id": "e2", "supported": False},
    ]})
    vision = OpenWorldVision(primary, claude, openai)
    result = vision.verify(scene(), b"original-image", "image/jpeg")
    assert result.room_supported
    assert [(c.id, c.supported) for c in result.claims] == [("e1", True), ("e2", False)]
    assert claude.calls[0]["image"] == b"original-image"
    assert openai.calls[0]["image"] == b"original-image"


def test_missing_review_claim_fails_closed():
    claude = Reviewer({"room_supported": True, "claims": [
        {"id": "e1", "supported": True}, {"id": "e2", "supported": True},
    ]})
    openai = Reviewer({"room_supported": True, "claims": [{"id": "e1", "supported": True}]})
    vision = OpenWorldVision(Reviewer({}), claude, openai)
    import pytest
    with pytest.raises(ValueError, match="Second independent review"):
        vision.verify(scene(), b"original-image", "image/jpeg")


def test_room_is_not_corrobated_when_one_reviewer_disagrees():
    claude = Reviewer({"room_supported": True, "claims": [
        {"id": "e1", "supported": True}, {"id": "e2", "supported": False},
    ]})
    openai = Reviewer({"room_supported": False, "claims": [
        {"id": "e1", "supported": True}, {"id": "e2", "supported": False},
    ]})
    result = OpenWorldVision(Reviewer({}), claude, openai).verify(
        scene(), b"original-image", "image/jpeg")
    assert not result.room_supported
