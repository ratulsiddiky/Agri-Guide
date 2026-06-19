from base64 import b64encode

import bcrypt
import mongomock
import pytest
from bson import ObjectId

import config
from app import create_app


@pytest.fixture()
def client(monkeypatch):
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["smart_agri_test"]
    config.reset_db_cache()
    monkeypatch.setattr(config, "get_mongo_client", lambda: mock_client)
    monkeypatch.setattr(config, "get_db", lambda: mock_db)

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as test_client:
        yield test_client


def _basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def _login_token(client, username="farmer_one", password="Password123!", role="user"):
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": username,
            "email": f"{username}@example.com",
            "password": hashed_password,
            "role": role,
            "is_verified": True,
        }
    )
    response = client.post("/api/login", headers=_basic_auth(username, password))
    return response.get_json()["token"]


def test_create_farm_requires_authentication(client):
    response = client.post("/api/farms", json={"farm_name": "North Field"})
    assert response.status_code == 401


def test_create_farm_succeeds_for_authenticated_user(client):
    token = _login_token(client)

    response = client.post(
        "/api/farms",
        json={"farm_name": "North Field", "crop_type": "Wheat"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.get_json()["message"] == "Farm registered successfully!"


def test_create_farm_creates_default_sensors(client):
    token = _login_token(client)

    response = client.post(
        "/api/farms",
        json={"farm_name": "Sensor Farm", "crop_type": "Tomatoes"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    farm_id = response.get_json()["farm_id"]
    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})

    sensors = farm["sensors"]
    assert {sensor["type"] for sensor in sensors} == {
        "soil_moisture",
        "temperature",
        "humidity",
        "light",
        "ph",
    }
    assert all(sensor["farm_id"] == farm_id for sensor in sensors)
    assert all(sensor["source"] == "auto_generated_demo_sensor" for sensor in sensors)
    values_by_type = {sensor["type"]: sensor["value"] for sensor in sensors}
    assert 45 <= values_by_type["soil_moisture"] <= 70
    assert 18 <= values_by_type["temperature"] <= 26
    assert 55 <= values_by_type["humidity"] <= 75
    assert 20000 <= values_by_type["light"] <= 50000
    assert 5.8 <= values_by_type["ph"] <= 7.2


def test_create_farm_preserves_coordinates_when_provided(client):
    token = _login_token(client)

    response = client.post(
        "/api/farms",
        json={
            "farm_name": "Map Farm",
            "crop_type": "Barley",
            "latitude": 54.5973,
            "longitude": -5.9301,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    farm_id = response.get_json()["farm_id"]
    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})
    assert farm["latitude"] == 54.5973
    assert farm["longitude"] == -5.9301
    assert farm["location"] == {"type": "Point", "coordinates": [-5.9301, 54.5973]}
    assert farm["location_source"] == "manual_coordinates"


def test_create_farm_with_browser_coordinates(client):
    token = _login_token(client)

    response = client.post(
        "/api/farms",
        json={
            "farm_name": "Geo Farm",
            "crop_type": "Potatoes",
            "address_line": "Field Lane",
            "city": "Belfast",
            "region": "County Antrim",
            "postcode": "BT1 1AA",
            "country": "United Kingdom",
            "latitude": "54.6",
            "longitude": "-5.93",
            "location_source": "browser_geolocation",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    farm_id = response.get_json()["farm_id"]
    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})
    assert farm["latitude"] == 54.6
    assert farm["longitude"] == -5.93
    assert farm["location"] == {"type": "Point", "coordinates": [-5.93, 54.6]}
    assert farm["location_source"] == "browser_geolocation"
    assert farm["address"]["area_name"] == "County Antrim"
    assert farm["address"]["postcode"] == "BT1 1AA"


def test_update_farm_with_coordinates(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Update Location Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.put(
        f"/api/farms/{farm_id}",
        json={
            "latitude": 51.5072,
            "longitude": -0.1276,
            "location_source": "manual_coordinates",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})
    assert farm["latitude"] == 51.5072
    assert farm["longitude"] == -0.1276
    assert farm["location"] == {"type": "Point", "coordinates": [-0.1276, 51.5072]}
    assert farm["location_source"] == "manual_coordinates"


@pytest.mark.parametrize(
    "payload, expected_message",
    [
        ({"farm_name": "Bad Farm", "latitude": 91, "longitude": 0}, "latitude must be between -90 and 90"),
        ({"farm_name": "Bad Farm", "latitude": 0, "longitude": 181}, "longitude must be between -180 and 180"),
        ({"farm_name": "Bad Farm", "latitude": 54.6}, "latitude and longitude must be provided together"),
    ],
)
def test_create_farm_rejects_invalid_coordinates(client, payload, expected_message):
    token = _login_token(client)

    response = client.post(
        "/api/farms",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert expected_message in response.get_json()["message"]


def test_admin_can_delete_farm(client):
    token = _login_token(client, username="admin_user", role="admin")
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Delete Me",
                "owner_id": "someone",
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.delete(
        f"/api/farms/{farm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Farm deleted successfully"
