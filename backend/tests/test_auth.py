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


def test_signup_creates_user(client):
    response = client.post(
        "/api/users/signup",
        json={
            "username": "new_farmer",
            "email": "new_farmer@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 201
    assert "Account created for new_farmer" in response.get_json()["message"]


def test_login_requires_verified_user(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "farmer_one",
            "email": "farmer_one@example.com",
            "password": password,
            "role": "user",
            "is_verified": False,
        }
    )

    response = client.post("/api/login", headers=_basic_auth("farmer_one", "Password123!"))
    assert response.status_code == 403
    assert response.get_json()["message"] == "Please verify your email before logging in."


def test_logout_blacklists_token(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "admin_user",
            "email": "admin@example.com",
            "password": password,
            "role": "admin",
            "is_verified": True,
        }
    )

    login_response = client.post(
        "/api/login",
        headers=_basic_auth("admin_user", "Password123!"),
    )
    token = login_response.get_json()["token"]

    logout_response = client.get(
        "/api/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout_response.status_code == 200
    assert config.get_db().blacklist.find_one({"token": token}) is not None
