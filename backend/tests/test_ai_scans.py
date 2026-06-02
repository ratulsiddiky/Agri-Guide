from base64 import b64decode, b64encode
from io import BytesIO

import bcrypt
import mongomock
import pytest
from bson import ObjectId

import config
from app import create_app


PNG_1X1 = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


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


def _create_farm_for(username, farm_name="Scan Farm"):
    user = config.get_db().users.find_one({"username": username})
    return str(
        config.get_db().farms.insert_one(
            {
                "farm_name": farm_name,
                "crop_type": "Tomato",
                "owner_id": user["_id"],
            }
        ).inserted_id
    )


def test_authenticated_user_can_upload_valid_crop_scan(client):
    token = _login_token(client)
    farm_id = _create_farm_for("farmer_one")

    response = client.post(
        "/api/ai/crop-scan",
        data={
            "image": (BytesIO(PNG_1X1), "healthy_leaf.png"),
            "farm_id": farm_id,
            "crop_type": "Tomato",
        },
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["model_mode"] == "simulated_ai"
    assert payload["model_type"] == "crop_leaf_health_classifier"
    assert payload["future_upgrade_model"] == "MobileNetV2 transfer learning CNN"
    assert payload["label"] in {
        "Healthy Leaf",
        "Early Blight Risk",
        "Powdery Mildew Risk",
        "Nutrient Deficiency Signs",
        "Water Stress Signs",
    }
    assert payload["image_metadata"]["filename"] == "healthy_leaf.png"
    assert payload["farm_id"] == farm_id

    stored_scan = config.get_db().ai_scans.find_one({"_id": ObjectId(payload["scan_id"])})
    assert stored_scan["user_id"] == str(config.get_db().users.find_one({"username": "farmer_one"})["_id"])
    assert stored_scan["farm_id"] == farm_id


def test_crop_scan_missing_image_returns_400(client):
    token = _login_token(client)

    response = client.post(
        "/api/ai/crop-scan",
        data={"crop_type": "Wheat"},
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Image file is required."


def test_crop_scan_invalid_extension_returns_400(client):
    token = _login_token(client)

    response = client.post(
        "/api/ai/crop-scan",
        data={"image": (BytesIO(b"not an image"), "leaf.txt")},
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Invalid image type" in response.get_json()["message"]


def test_user_can_list_only_own_crop_scans(client):
    token = _login_token(client)
    other_token = _login_token(client, username="other_farmer")

    client.post(
        "/api/ai/crop-scan",
        data={"image": (BytesIO(PNG_1X1), "healthy_leaf.png")},
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/ai/crop-scan",
        data={"image": (BytesIO(PNG_1X1), "other_leaf.png")},
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    response = client.get("/api/ai/scans", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["scans"][0]["image_metadata"]["filename"] == "healthy_leaf.png"


def test_farm_scan_access_blocked_for_non_owner(client):
    _login_token(client)
    farm_id = _create_farm_for("farmer_one")
    other_token = _login_token(client, username="other_farmer")

    response = client.get(
        f"/api/farms/{farm_id}/ai-scans",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403
