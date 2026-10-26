import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app

@pytest.fixture
def client() -> TestClient:
    test_app = create_app()
    return TestClient(
        test_app
    )

#-tests-

#-1-
def test_health_check(
    client: TestClient,
):
    response = client.get(
        "/health"
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }

#-2-
def test_graphql_entity_query(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_plant_001") {
                        id
                        name
                        location
                        identity
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entity": {
                "id": "entity_plant_001",
                "name": "Living Room Plant",
                "location": "living_room",
                "identity": "Monstera deliciosa",
            }
        }
    }

#-3-
def test_graphql_returns_only_requested_fields(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_plant_001") {
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entity": {
                "name": "Living Room Plant",
            }
        }
    }

#-4-
def test_graphql_rejects_unknown_field(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_plant_001") {
                        favoriteFood
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "errors" in body
    assert body["data"] is None
    assert (
        "Cannot query field 'favoriteFood'"
        in body["errors"][0]["message"]
    )

#-5-
def test_graphql_entity_returns_null_when_not_found(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "does_not_exist") {
                        id
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entity": None,
        }
    }

#-6-
def test_graphql_entity_argument_selects_requested_entity(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_washer_001") {
                        id
                        name
                        identity
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entity": {
                "id": "entity_washer_001",
                "name": "Laundry Room Washer",
                "identity": "LG WM4000HWA",
            }
        }
    }

#-7-
def test_graphql_entities_query(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entities {
                        id
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entities": [
                {
                    "id": "entity_plant_001",
                    "name": "Living Room Plant",
                },
                {
                    "id": "entity_washer_001",
                    "name": "Laundry Room Washer",
                },
            ]
        }
    }

#-8-
def test_graphql_entities_filter_by_location(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entities(location: "living_room") {
                        id
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entities": [
                {
                    "id": "entity_plant_001",
                    "name": "Living Room Plant",
                }
            ]
        }
    }

#-9-
def test_graphql_entities_filter_by_entity_type(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entities(entityType: PLANT) {
                        id
                        name
                        entityType
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entities": [
                {
                    "id": "entity_plant_001",
                    "name": "Living Room Plant",
                    "entityType": "PLANT",
                }
            ]
        }
    }

#-10-
def test_graphql_entities_filter_by_location_and_type(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entities(
                        location: "living_room"
                        entityType: PLANT
                    ) {
                        id
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "entities": [
                {
                    "id": "entity_plant_001",
                }
            ]
        }
    }

#-11-
def test_graphql_rename_entity_mutation(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    renameEntity(
                        id: "entity_plant_001"
                        name: "My Monstera"
                    ) {
                        id
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "renameEntity": {
                "id": "entity_plant_001",
                "name": "My Monstera",
            }
        }
    }

#-12-
def test_graphql_rename_unknown_entity_returns_null(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    renameEntity(
                        id: "does_not_exist"
                        name: "New Name"
                    ) {
                        id
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "renameEntity": None,
        }
    }

#-13-
def test_graphql_rename_entity_rejects_empty_name(
    client: TestClient,
):
    response = client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    renameEntity(
                        id: "entity_plant_001"
                        name: "   "
                    ) {
                        id
                        name
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "errors" in body
    assert body["data"] == {
        "renameEntity": None,
    }    
    assert (
        "Entity name cannot be empty."
        in body["errors"][0]["message"]
    )

#-14-
def test_graphql_mutation_changes_shared_state(
    client: TestClient,
):
    rename_response = client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    renameEntity(
                        id: "entity_plant_001"
                        name: "Temporary Name"
                    ) {
                        name
                    }
                }
            """
        },
    )
    assert rename_response.status_code == 200

    query_response = client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_plant_001") {
                        name
                    }
                }
            """
        },
    )
    assert query_response.json() == {
        "data": {
            "entity": {
                "name": "Temporary Name",
            }
        }
    }

    client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    renameEntity(
                        id: "entity_plant_001"
                        name: "Living Room Plant"
                    ) {
                        name
                    }
                }
            """
        },
    )

#-15-
def test_separate_app_instances_have_isolated_state(
    client: TestClient,
):
    first_app = create_app()
    second_app = create_app()

    first_client = TestClient(
        first_app
    )
    second_client = TestClient(
        second_app
    )

    rename_response = first_client.post(
        "/graphql",
        json={
            "query": """
                mutation {
                    renameEntity(
                        id: "entity_plant_001"
                        name: "App One Plant"
                    ) {
                        name
                    }
                }
            """
        },
    )
    assert rename_response.status_code == 200

    first_response = first_client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_plant_001") {
                        name
                    }
                }
            """
        },
    )
    assert first_response.json() == {
        "data": {
            "entity": {
                "name": "App One Plant",
            }
        }
    }

    second_response = second_client.post(
        "/graphql",
        json={
            "query": """
                query {
                    entity(id: "entity_plant_001") {
                        name
                    }
                }
            """
        },
    )
    assert second_response.json() == {
        "data": {
            "entity": {
                "name": "Living Room Plant",
            }
        }
    }

@pytest.fixture(autouse=True)
def _use_standalone_graphql_mode(monkeypatch):
    """GraphQL entity tests exercise the standalone, non-household API."""
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "false")
    monkeypatch.setenv("HOMHIVE_MEDIA_ROOT", "")
    monkeypatch.setenv("HOMHIVE_HOUSEHOLD_TOKENS", "")
    monkeypatch.setenv("HOMHIVE_ENTITY_STORAGE", "memory")



def test_private_household_mode_does_not_expose_unscoped_graphql(monkeypatch, tmp_path):
    """Standalone entity mutations must not be available to private households."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'private.sqlite'}")
    monkeypatch.setenv("HOMHIVE_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("HOMHIVE_HOUSEHOLD_TOKENS", '{"home":"test-token"}')
    monkeypatch.setenv("HOMHIVE_ACCOUNT_SIGNING_SECRET", "")
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    app = create_app()
    assert not any(getattr(route, "path", None) == "/graphql" for route in app.routes)
