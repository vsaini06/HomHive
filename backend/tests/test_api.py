from fastapi.testclient import TestClient

from app.api.app import app

client = TestClient(app)

#-tests-

#-1-
def test_health_check():
    response = client.get(
        "/health"
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }

#-2-
def test_graphql_entity_query():
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
def test_graphql_returns_only_requested_fields():
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
def test_graphql_rejects_unknown_field():
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
def test_graphql_entity_returns_null_when_not_found():
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
def test_graphql_entity_argument_selects_requested_entity():
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
def test_graphql_entities_query():
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
def test_graphql_entities_filter_by_location():
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
def test_graphql_entities_filter_by_entity_type():
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
def test_graphql_entities_filter_by_location_and_type():
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