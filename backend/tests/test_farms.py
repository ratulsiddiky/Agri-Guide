from base64 import b64encode

import bcrypt
import mongomock
import pytest

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
