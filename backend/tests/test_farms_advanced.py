from base64 import b64encode

import bcrypt
import mongomock
import pytest
from bson import ObjectId

import config
from app import create_app
from blueprints.farms import farms as farms_routes


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


def test_search_farms(client, monkeypatch):
    expected_farm_id = ObjectId()
    expected_doc = {
        "_id": expected_farm_id,
        "farm_name": "North Field",
        "crop_type": "Wheat",
    }

    class _FakeFarmsCollection:
        def count_documents(self, query):
            return 1 if "north" in str(query).lower() else 0
        
        def find(self, query):
            self.data = [expected_doc] if "north" in str(query).lower() else []
            return self
        
        def skip(self, n):
            return self
        
        def limit(self, n):
            return self.data

    monkeypatch.setattr(farms_routes, "_farms_collection", lambda: _FakeFarmsCollection())

    response = client.get("/api/farms/search?q=north")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results_count"] == 1
    assert payload["total"] == 1
    assert payload["data"][0]["farm_name"] == "North Field"
    assert payload["data"][0]["_id"] == str(expected_farm_id)


def test_sync_weather(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Weather Farm",
                "owner_id": owner["_id"],
                "location": {"type": "Point", "coordinates": [74.8, 31.5]},
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    class _FakeWeatherResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "current_weather": {
                    "temperature": 24.6,
                    "windspeed": 12.3,
                }
            }

    monkeypatch.setattr(farms_routes.requests, "get", lambda *args, **kwargs: _FakeWeatherResponse())

    response = client.post(
        f"/api/farms/{farm_id}/sync_weather",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Weather synced!"
    assert payload["new_log"]["temperature_celsius"] == 24.6
    assert payload["new_log"]["windspeed"] == 12.3


def test_get_farm_insights(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Insight Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "alerts_history": [],
                "weather_logs": [
                    {"temperature_celsius": 20.0, "windspeed": 10.0},
                    {"temperature_celsius": 30.0, "windspeed": 20.0},
                ],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/insights",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Insights generated"
    assert payload["dashboard_data"]["farm_name"] == "Insight Farm"
    assert payload["dashboard_data"]["average_temp"] == 25.0
    assert payload["dashboard_data"]["average_wind"] == 15.0


def test_broadcast_alert_admin_only(client):
    token = _login_token(client, username="normal_user", role="user")

    response = client.post(
        "/api/farms/alerts/broadcast",
        json={
            "alert_type": "Flood",
            "danger_zone": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [74.0, 31.0],
                        [75.0, 31.0],
                        [75.0, 32.0],
                        [74.0, 32.0],
                        [74.0, 31.0],
                    ]
                ],
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.get_json()["message"] == "Only admin users can broadcast emergency alerts."


def test_irrigation_check(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Moisture Farm",
                "owner_id": owner["_id"],
                "sensors": [
                    {
                        "sensor_id": "soil-001",
                        "type": "Soil Moisture",
                        "readings": [{"value": 12.5}],
                    }
                ],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/irrigation_check",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "WARNING"
    assert payload["moisture"] == 12.5