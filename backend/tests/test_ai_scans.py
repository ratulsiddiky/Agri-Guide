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


def _upload_scan(client, token, filename="healthy_leaf.png", farm_id=None, crop_type="Tomato"):
    data = {
        "image": (BytesIO(PNG_1X1), filename),
        "crop_type": crop_type,
    }
    if farm_id:
        data["farm_id"] = farm_id

    return client.post(
        "/api/ai/crop-scan",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
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
        "Leaf Blight Risk",
        "Powdery Mildew Risk",
        "Rust Disease Risk",
        "Nutrient Deficiency Signs",
        "Pest Damage Signs",
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


def test_owner_can_get_crop_scan_detail(client):
    token = _login_token(client)
    farm_id = _create_farm_for("farmer_one", farm_name="Detail Farm")
    upload_response = _upload_scan(client, token, filename="water_stress_leaf.png", farm_id=farm_id)
    scan_id = upload_response.get_json()["scan_id"]

    response = client.get(
        f"/api/ai/scans/{scan_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["scan_id"] == scan_id
    assert payload["farm_id"] == farm_id
    assert payload["farm_name"] == "Detail Farm"
    assert payload["crop_type"] == "Tomato"
    assert payload["image_metadata"]["filename"] == "water_stress_leaf.png"
    assert payload["recommendation"]
    assert payload["explanation"]
    assert payload["severity_explanation"]
    assert payload["likely_causes"]
    assert payload["possible_causes"]
    assert payload["immediate_actions"]
    assert payload["prevention_plan"]
    assert payload["monitoring_advice"]
    assert payload["advisory_disclaimer"]
    assert payload["created_at"]
    assert "_id" not in payload
    assert "user_id" not in payload
    assert "username" not in payload


def test_other_user_cannot_get_crop_scan_detail(client):
    owner_token = _login_token(client, username="owner_user")
    other_token = _login_token(client, username="other_farmer")
    upload_response = _upload_scan(client, owner_token, filename="owner_leaf.png")
    scan_id = upload_response.get_json()["scan_id"]

    response = client.get(
        f"/api/ai/scans/{scan_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "You do not have permission to view this scan."


def test_admin_can_get_crop_scan_detail_for_other_user(client):
    owner_token = _login_token(client, username="owner_user")
    admin_token = _login_token(client, username="admin_user", role="admin")
    upload_response = _upload_scan(client, owner_token, filename="admin_view_leaf.png")
    scan_id = upload_response.get_json()["scan_id"]

    response = client.get(
        f"/api/ai/scans/{scan_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["scan_id"] == scan_id


def test_crop_scan_detail_requires_authentication(client):
    response = client.get(f"/api/ai/scans/{ObjectId()}")

    assert response.status_code == 401


def test_crop_scan_detail_invalid_id_returns_404(client):
    token = _login_token(client)

    response = client.get(
        "/api/ai/scans/not-a-scan-id",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.get_json()["message"] == "Scan not found."


def test_crop_scan_returns_expanded_advice_and_stores_it(client):
    token = _login_token(client)
    farm_id = _create_farm_for("farmer_one", farm_name="Advice Farm")

    response = client.post(
        "/api/ai/crop-scan",
        data={
            "image": (BytesIO(PNG_1X1), "water_stress_leaf.png"),
            "farm_id": farm_id,
            "crop_type": "Lettuce",
        },
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["severity"] == "high"
    assert isinstance(payload["explanation"], str) and payload["explanation"]
    assert isinstance(payload["severity_explanation"], str) and payload["severity_explanation"]
    assert isinstance(payload["likely_causes"], list) and payload["likely_causes"]
    assert isinstance(payload["possible_causes"], list) and payload["possible_causes"]
    assert isinstance(payload["immediate_actions"], list) and payload["immediate_actions"]
    assert isinstance(payload["prevention_plan"], list) and payload["prevention_plan"]
    assert isinstance(payload["monitoring_advice"], str) and payload["monitoring_advice"]
    assert isinstance(payload["when_to_seek_expert_help"], str) and payload["when_to_seek_expert_help"]
    assert isinstance(payload["confidence_explanation"], str) and payload["confidence_explanation"]
    assert isinstance(payload["advisory_disclaimer"], str) and payload["advisory_disclaimer"]

    stored_scan = config.get_db().ai_scans.find_one({"_id": ObjectId(payload["scan_id"])})
    assert stored_scan["explanation"] == payload["explanation"]
    assert stored_scan["severity_explanation"] == payload["severity_explanation"]
    assert stored_scan["likely_causes"] == payload["likely_causes"]
    assert stored_scan["possible_causes"] == payload["possible_causes"]
    assert stored_scan["immediate_actions"] == payload["immediate_actions"]
    assert stored_scan["prevention_plan"] == payload["prevention_plan"]
    assert stored_scan["monitoring_advice"] == payload["monitoring_advice"]
    assert stored_scan["advisory_disclaimer"] == payload["advisory_disclaimer"]


@pytest.mark.parametrize(
    ("filename", "expected_label"),
    [
        ("healthy_leaf.png", "Healthy Leaf"),
        ("leaf_blight_spots.png", "Leaf Blight Risk"),
        ("powdery_mildew_white.png", "Powdery Mildew Risk"),
        ("orange_rust_leaf.png", "Rust Disease Risk"),
        ("yellow_nutrient_deficiency.png", "Nutrient Deficiency Signs"),
        ("insect_pest_bite_damage.png", "Pest Damage Signs"),
        ("dry_water_stress_leaf.png", "Water Stress Signs"),
    ],
)
def test_crop_scan_keyword_diagnoses_return_richer_advice(client, filename, expected_label):
    token = _login_token(client, username=f"user_{expected_label.split()[0].lower()}")

    response = _upload_scan(client, token, filename=filename, crop_type="")

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["label"] == expected_label
    assert payload["explanation"]
    assert payload["severity_explanation"]
    assert payload["likely_causes"] == payload["possible_causes"]
    assert payload["immediate_actions"]
    assert payload["prevention_plan"]


def test_farm_scan_access_blocked_for_non_owner(client):
    _login_token(client)
    farm_id = _create_farm_for("farmer_one")
    other_token = _login_token(client, username="other_farmer")

    response = client.get(
        f"/api/farms/{farm_id}/ai-scans",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403
