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


def test_dashboard_summary_only_includes_current_user_farms_and_sensors(client):
    farmer_token = _login_token(client, username="farmer_one")
    _login_token(client, username="farmer_two")
    farmer = config.get_db().users.find_one({"username": "farmer_one"})
    other = config.get_db().users.find_one({"username": "farmer_two"})

    config.get_db().farms.insert_many(
        [
            {
                "farm_name": "Owned Farm",
                "owner_id": farmer["_id"],
                "alerts_history": [{"alert_type": "Heat"}],
                "sensors": [
                    {
                        "sensor_id": "soil-owned",
                        "type": "soil_moisture",
                        "value": 50,
                        "unit": "%",
                        "status": "active",
                    },
                    {
                        "sensor_id": "temp-owned",
                        "type": "temperature",
                        "value": 22,
                        "unit": "°C",
                        "status": "active",
                    },
                    {
                        "sensor_id": "hum-owned",
                        "type": "humidity",
                        "value": 62,
                        "unit": "%",
                        "status": "active",
                    },
                ],
            },
            {
                "farm_name": "Other Farm",
                "owner_id": other["_id"],
                "alerts_history": [{"alert_type": "Flood"}],
                "sensors": [
                    {
                        "sensor_id": "soil-other",
                        "type": "soil_moisture",
                        "value": 10,
                        "unit": "%",
                        "status": "active",
                    }
                ],
            },
        ]
    )

    response = client.get(
        "/api/dashboard/summary",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_farms"] == 1
    assert payload["total_sensors"] == 3
    assert payload["average_soil_moisture"] == 50
    assert payload["latest_temperature"] == 22
    assert payload["latest_humidity"] == 62
    assert payload["active_alerts_count"] == 1
    assert [row["sensor"] for row in payload["sensor_rows"]] == [
        "soil-owned",
        "temp-owned",
        "hum-owned",
    ]


def test_farm_sensors_endpoint_works_for_owner(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Sensor Farm",
                "owner_id": owner["_id"],
                "sensors": [
                    {
                        "sensor_id": "soil-001",
                        "farm_id": "farm-ref",
                        "type": "soil_moisture",
                        "value": 55,
                        "unit": "%",
                        "status": "active",
                    }
                ],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/sensors",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["farm_id"] == farm_id
    assert payload["count"] == 1
    assert payload["sensors"][0]["sensor_id"] == "soil-001"


def test_farm_sensors_endpoint_blocks_other_users(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Sensor Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/sensors",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403
