from base64 import b64encode
from datetime import datetime, timedelta, timezone

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


def test_search_farms_only_returns_current_user_matches(client):
    farmer_token = _login_token(client, username="farmer_one")
    _login_token(client, username="farmer_two")
    farmer = config.get_db().users.find_one({"username": "farmer_one"})
    other = config.get_db().users.find_one({"username": "farmer_two"})

    config.get_db().farms.insert_many(
        [
            {"farm_name": "North Field", "owner_id": farmer["_id"], "crop_type": "Wheat"},
            {"farm_name": "North Other", "owner_id": other["_id"], "crop_type": "Wheat"},
            {"farm_name": "South Field", "owner_id": farmer["_id"], "crop_type": "Corn"},
        ]
    )

    response = client.get(
        "/api/farms/search?q=north",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results_count"] == 1
    assert payload["total"] == 1
    assert payload["data"][0]["farm_name"] == "North Field"


def test_admin_search_farms_returns_all_matches(client):
    admin_token = _login_token(client, username="admin_user", role="admin")
    _login_token(client, username="farmer_one")
    admin = config.get_db().users.find_one({"username": "admin_user"})
    farmer = config.get_db().users.find_one({"username": "farmer_one"})

    config.get_db().farms.insert_many(
        [
            {"farm_name": "North Admin", "owner_id": admin["_id"], "crop_type": "Wheat"},
            {"farm_name": "North Farmer", "owner_id": farmer["_id"], "crop_type": "Wheat"},
        ]
    )

    response = client.get(
        "/api/farms/search?q=north",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results_count"] == 2
    assert {farm["farm_name"] for farm in payload["data"]} == {"North Admin", "North Farmer"}


def test_search_farms_requires_authentication(client):
    response = client.get("/api/farms/search?q=north")

    assert response.status_code == 401


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
    assert payload["new_log"]["location_source"] == "manual_coordinates"


def test_sync_weather_without_exact_coordinates_uses_fallback(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Fallback Weather Farm",
                "owner_id": owner["_id"],
                "address": {"area_name": "County Antrim"},
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
                    "temperature": 18.2,
                    "windspeed": 8.5,
                }
            }

    weather_calls = []

    def _fake_weather_get(url, *args, **kwargs):
        weather_calls.append(url)
        return _FakeWeatherResponse()

    monkeypatch.setattr(farms_routes.requests, "get", _fake_weather_get)

    response = client.post(
        f"/api/farms/{farm_id}/sync_weather",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["new_log"]["temperature_celsius"] == 18.2
    assert payload["new_log"]["location_source"] == "approximate_demo_location"
    assert "latitude=54.5973" in weather_calls[0]
    assert "longitude=-5.9301" in weather_calls[0]


def test_sync_weather_blocks_other_users(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Sync Farm",
                "owner_id": owner["_id"],
                "location": {"type": "Point", "coordinates": [-5.93, 54.6]},
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.post(
        f"/api/farms/{farm_id}/sync_weather",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403


def test_add_sensor_blocks_other_users(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Sensor Add Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.post(
        f"/api/farms/{farm_id}/sensors",
        json={"sensor_id": "soil-1", "type": "soil_moisture"},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403
    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})
    assert farm["sensors"] == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "insights",
        "irrigation_check",
        "sensor-history",
    ],
)
def test_farm_read_subroutes_block_other_users(client, endpoint):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Read Farm",
                "owner_id": owner["_id"],
                "sensors": [{"sensor_id": "soil-1", "type": "soil_moisture", "readings": [{"value": 50}]}],
                "weather_logs": [{"temperature_celsius": 20.0, "windspeed": 5.0}],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/{endpoint}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403


def test_farm_coordinates_prefers_top_level_exact_coordinates():
    farm = {
        "latitude": 10.5,
        "longitude": 20.25,
        "location": {"type": "Point", "coordinates": [99, 88]},
        "location_source": "browser_geolocation",
    }

    assert farms_routes._farm_coordinates(farm) == (10.5, 20.25, "browser_geolocation")


def test_farm_coordinates_reads_geojson_for_legacy_farms():
    farm = {"location": {"type": "Point", "coordinates": [-0.1276, 51.5072]}}

    assert farms_routes._farm_coordinates(farm) == (51.5072, -0.1276, "manual_coordinates")


def test_farm_coordinates_fallback_still_works_for_old_farms():
    farm = {"farm_name": "Old Farm", "address": {"area_name": "County Antrim"}}

    assert farms_routes._farm_coordinates(farm) == (54.5973, -5.9301, "approximate_demo_location")


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

    insertion = config.get_db().farms.insert_many(
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
    owned_farm_id = str(insertion.inserted_ids[0])

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
    assert payload["location_source"] == "approximate_demo_location"
    assert payload["latitude"] == 54.5973
    assert payload["longitude"] == -5.9301
    assert payload["primary_farm_id"] == owned_farm_id
    assert "timezone" not in payload


def test_dashboard_summary_sensor_rows_include_source_labels_and_clean_units(client):
    token = _login_token(client, username="source_owner")
    owner = config.get_db().users.find_one({"username": "source_owner"})
    config.get_db().farms.insert_one(
        {
            "farm_name": "Source Farm",
            "owner_id": owner["_id"],
            "alerts_history": [],
            "weather_logs": [],
            "sensors": [
                {
                    "sensor_id": "lux-demo",
                    "type": "light",
                    "value": 34599,
                    "unit": "lux",
                    "status": "active",
                    "source": "auto_generated_demo_sensor",
                },
                {
                    "sensor_id": "ph-manual",
                    "type": "ph",
                    "value": 5.8,
                    "unit": "pH",
                    "status": "active",
                    "source": "auto_generated_demo_sensor",
                    "readings": [
                        {
                            "value": "6.0",
                            "unit": "pH",
                            "source": "manual_sensor_reading",
                        }
                    ],
                },
                {
                    "sensor_id": "temp-iot",
                    "type": "temperature",
                    "value": 23.9,
                    "unit": "°C",
                    "status": "active",
                    "source": "iot_sensor",
                },
                {
                    "sensor_id": "soil-live",
                    "type": "soil_moisture",
                    "value": 58,
                    "unit": "%",
                    "status": "active",
                    "source": "live_sensor",
                },
                {
                    "sensor_id": "unknown-source",
                    "type": "humidity",
                    "value": 64,
                    "unit": "%",
                    "status": "active",
                },
            ],
        }
    )

    response = client.get(
        "/api/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = {row["sensor"]: row for row in response.get_json()["sensor_rows"]}
    assert rows["lux-demo"]["value"] == "34,599 lux"
    assert rows["lux-demo"]["source"] == "auto_generated_demo_sensor"
    assert rows["lux-demo"]["source_label"] == "Demo sensor"
    assert rows["ph-manual"]["value"] == "6.0 pH"
    assert rows["ph-manual"]["source"] == "manual_sensor_reading"
    assert rows["ph-manual"]["source_label"] == "Manual reading"
    assert rows["temp-iot"]["value"] == "23.9°C"
    assert rows["temp-iot"]["source_label"] == "IoT sensor"
    assert rows["soil-live"]["value"] == "58%"
    assert rows["soil-live"]["source_label"] == "IoT sensor"
    assert rows["unknown-source"]["source"] == ""
    assert rows["unknown-source"]["source_label"] == "Unknown source"


def test_dashboard_summary_uses_latest_synced_weather_log(client, monkeypatch):
    token = _login_token(client, username="weather_owner")
    owner = config.get_db().users.find_one({"username": "weather_owner"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Synced Weather Farm",
                "owner_id": owner["_id"],
                "latitude": 54.5973,
                "longitude": -5.9301,
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
            return {"current_weather": {"temperature": 19.4, "windspeed": 17.6}}

    monkeypatch.setattr(farms_routes.requests, "get", lambda *args, **kwargs: _FakeWeatherResponse())

    sync_response = client.post(
        f"/api/farms/{farm_id}/sync_weather",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sync_response.status_code == 200

    summary_response = client.get(
        "/api/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert summary_response.status_code == 200
    payload = summary_response.get_json()
    assert payload["latest_temperature"] == 19.4
    assert payload["weather"]["data_source"] == "latest_weather_log"
    assert payload["weather"]["temperature_c"] == 19.4
    assert payload["weather"]["wind_speed_kmh"] == 17.6
    assert payload["weather"]["farm_id"] == farm_id
    assert payload["weather_alert"]["data_source"] == "latest_weather_log"


def test_dashboard_summary_uses_latest_ai_scan_for_current_user(client):
    token = _login_token(client, username="scan_owner")
    _login_token(client, username="other_scan_owner")
    owner = config.get_db().users.find_one({"username": "scan_owner"})
    other = config.get_db().users.find_one({"username": "other_scan_owner"})
    now = datetime.now(timezone.utc)
    config.get_db().ai_scans.insert_many(
        [
            {
                "user_id": str(owner["_id"]),
                "prediction": {"label": "Healthy Leaf", "confidence": 0.91, "recommendation": "Old demo"},
                "recommendation": "Old demo",
                "model_mode": "simulated_ai",
                "ai_mode": "simulated_ai",
                "created_at": now - timedelta(hours=2),
            },
            {
                "user_id": str(owner["_id"]),
                "prediction": {
                    "label": "Tomato early blight",
                    "confidence": 0.968,
                    "recommendation": "Remove affected lower leaves.",
                },
                "recommendation": "Remove affected lower leaves.",
                "explanation": "The image is most consistent with tomato early blight.",
                "model_mode": "custom_trained_model",
                "ai_mode": "custom_trained_model",
                "created_at": now,
            },
            {
                "user_id": str(other["_id"]),
                "prediction": {"label": "Other user disease", "confidence": 0.99},
                "recommendation": "Private other-user advice",
                "model_mode": "custom_trained_model",
                "ai_mode": "custom_trained_model",
                "created_at": now + timedelta(hours=1),
            },
        ]
    )

    response = client.get(
        "/api/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    ai_card = payload["ai_crop_detection"]
    assert ai_card["data_source"] == "latest_ai_scan"
    assert ai_card["label"] == "Tomato early blight"
    assert ai_card["confidence"] == 0.968
    assert ai_card["model_mode"] == "custom_trained_model"
    assert ai_card["ai_mode"] == "custom_trained_model"
    assert ai_card["recommendation"] == "Remove affected lower leaves."
    assert ai_card["label"] != "Healthy Leaf"
    assert ai_card["label"] != "Other user disease"


def test_dashboard_summary_does_not_leak_other_user_weather_or_scan_data(client):
    token = _login_token(client, username="private_owner")
    _login_token(client, username="other_private_owner")
    owner = config.get_db().users.find_one({"username": "private_owner"})
    other = config.get_db().users.find_one({"username": "other_private_owner"})
    now = datetime.now(timezone.utc)
    config.get_db().farms.insert_many(
        [
            {
                "farm_name": "Owned Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [{"timestamp": now, "temperature_celsius": 18.0, "windspeed": 5.0}],
                "alerts_history": [],
            },
            {
                "farm_name": "Other Farm",
                "owner_id": other["_id"],
                "sensors": [],
                "weather_logs": [{"timestamp": now + timedelta(hours=1), "temperature_celsius": 41.0, "windspeed": 44.0}],
                "alerts_history": [],
            },
        ]
    )
    config.get_db().ai_scans.insert_one(
        {
            "user_id": str(other["_id"]),
            "prediction": {"label": "Other user private scan", "confidence": 0.99},
            "recommendation": "Private advice",
            "created_at": now,
        }
    )

    response = client.get(
        "/api/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_farms"] == 1
    assert payload["weather"]["temperature_c"] == 18.0
    assert payload["ai_crop_detection"]["data_source"] == "fallback_demo"
    assert payload["ai_crop_detection"]["label"] == "No scans yet"


def test_dashboard_summary_returns_safe_fallbacks_without_weather_or_scans(client):
    token = _login_token(client, username="fallback_owner")
    owner = config.get_db().users.find_one({"username": "fallback_owner"})
    config.get_db().farms.insert_one(
        {
            "farm_name": "Empty Farm",
            "owner_id": owner["_id"],
            "sensors": [],
            "weather_logs": [],
            "alerts_history": [],
        }
    )

    response = client.get(
        "/api/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["weather"]["data_source"] == "fallback_demo"
    assert payload["weather"]["temperature_c"] is None
    assert payload["latest_sensor_readings"]["data_source"] == "fallback_demo"
    assert payload["ai_crop_detection"]["data_source"] == "fallback_demo"
    assert payload["ai_crop_detection"]["label"] == "No scans yet"
    assert payload["irrigation_decision"]["data_source"] == "fallback_demo"


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


def test_sensor_history_endpoint_works_for_owner(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Trend Farm",
                "owner_id": owner["_id"],
                "sensors": [
                    {
                        "sensor_id": "soil-001",
                        "type": "soil_moisture",
                        "readings": [
                            {"value": 50, "timestamp": "2026-06-01T08:00:00+00:00"},
                            {"value": 54, "timestamp": "2026-06-01T09:00:00+00:00"},
                        ],
                    },
                    {
                        "sensor_id": "temp-001",
                        "type": "temperature",
                        "readings": [
                            {"value": 20, "timestamp": "2026-06-01T08:00:00+00:00"},
                            {"value": 22, "timestamp": "2026-06-01T09:00:00+00:00"},
                        ],
                    },
                    {
                        "sensor_id": "hum-001",
                        "type": "humidity",
                        "readings": [
                            {"value": 61, "timestamp": "2026-06-01T08:00:00+00:00"},
                            {"value": 64, "timestamp": "2026-06-01T09:00:00+00:00"},
                        ],
                    },
                ],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/sensor-history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["farm_id"] == farm_id
    assert payload["farm_name"] == "Trend Farm"
    assert payload["data_source"] == "stored_sensor_readings"
    assert payload["timestamps"] == [
        "2026-06-01T08:00:00+00:00",
        "2026-06-01T09:00:00+00:00",
    ]
    assert payload["series"]["soil_moisture"] == [50.0, 54.0]
    assert payload["series"]["temperature"] == [20.0, 22.0]
    assert payload["series"]["humidity"] == [61.0, 64.0]


def test_sensor_history_endpoint_blocks_other_users(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Trend Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/sensor-history",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403


def test_farm_weather_endpoint_works_for_owner(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Weather Detail Farm",
                "owner_id": owner["_id"],
                "latitude": 54.5973,
                "longitude": -5.9301,
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
                "current": {
                    "time": "2026-06-01T10:00",
                    "temperature_2m": 18.7,
                    "relative_humidity_2m": 72,
                    "wind_speed_10m": 14.2,
                    "precipitation": 0.1,
                    "rain": 0.0,
                    "weather_code": 2,
                }
            }

    monkeypatch.setattr(farms_routes.requests, "get", lambda *args, **kwargs: _FakeWeatherResponse())

    response = client.get(
        f"/api/farms/{farm_id}/weather",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["farm_id"] == farm_id
    assert payload["farm_name"] == "Weather Detail Farm"
    assert payload["latitude"] == 54.5973
    assert payload["longitude"] == -5.9301
    assert payload["location_source"] == "manual_coordinates"
    assert payload["temperature_c"] == 18.7
    assert payload["humidity_percent"] == 72
    assert payload["wind_speed_kmh"] == 14.2
    assert payload["precipitation_mm"] == 0.1
    assert payload["rain_mm"] == 0.0
    assert payload["condition_summary"] == "Partly cloudy"
    assert payload["provider"] == "Open-Meteo"
    assert payload["data_source"] == "open_meteo_current_weather"


def test_farm_weather_endpoint_blocks_other_users(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Weather Farm",
                "owner_id": owner["_id"],
                "latitude": 54.5973,
                "longitude": -5.9301,
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/weather",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403


def test_farm_weather_missing_coordinates_uses_fallback_safely(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Approx Weather Farm",
                "owner_id": owner["_id"],
                "address": {"area_name": "County Antrim"},
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    def _raise_request_error(*args, **kwargs):
        raise farms_routes.requests.RequestException("Open-Meteo unavailable")

    monkeypatch.setattr(farms_routes.requests, "get", _raise_request_error)

    response = client.get(
        f"/api/farms/{farm_id}/weather",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["farm_id"] == farm_id
    assert payload["latitude"] == 54.5973
    assert payload["longitude"] == -5.9301
    assert payload["location_source"] == "approximate_demo_location"
    assert payload["data_source"] == "fallback_simulated_weather"
    assert payload["provider"] == "Open-Meteo"


def test_add_sensor_reading_updates_history_for_owner(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Manual Reading Farm",
                "owner_id": owner["_id"],
                "sensors": [
                    {
                        "sensor_id": "soil-001",
                        "type": "soil_moisture",
                        "value": 48,
                        "unit": "%",
                        "status": "active",
                        "readings": [
                            {
                                "value": 48,
                                "unit": "%",
                                "timestamp": "2026-06-01T08:00:00+00:00",
                                "source": "auto_generated_demo_sensor",
                            }
                        ],
                    }
                ],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.post(
        f"/api/farms/{farm_id}/sensors/readings",
        json={
            "sensor_type": "soil_moisture",
            "value": 32,
            "unit": "%",
            "notes": "Afternoon manual reading",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["farm_id"] == farm_id
    assert payload["sensor_type"] == "soil_moisture"
    assert payload["reading"]["notes"] == "Afternoon manual reading"

    history_response = client.get(
        f"/api/farms/{farm_id}/sensor-history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert history_response.status_code == 200
    history = history_response.get_json()
    assert history["data_source"] == "stored_sensor_readings"
    assert history["series"]["soil_moisture"] == [48.0, 32.0]


def test_add_sensor_reading_blocks_other_user(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Private Manual Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.post(
        f"/api/farms/{farm_id}/sensors/readings",
        json={"sensor_type": "temperature", "value": 19, "unit": "°C"},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403


def test_add_sensor_reading_creates_sensor_when_missing(client):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Blank Farm",
                "owner_id": owner["_id"],
                "sensors": [],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    response = client.post(
        f"/api/farms/{farm_id}/sensors/readings",
        json={"sensor_type": "temperature", "value": 22, "unit": "°C"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})
    assert farm["sensors"][0]["type"] == "temperature"
    assert farm["sensors"][0]["readings"][-1]["value"] == 22


def test_action_plan_owner_can_access_and_gets_plan(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {
                "farm_name": "Action Farm",
                "owner_id": owner["_id"],
                "sensors": [
                    {"sensor_id": "soil-001", "type": "soil_moisture", "readings": [{"value": 18}]}
                ],
                "weather_logs": [],
                "alerts_history": [],
            }
        ).inserted_id
    )

    class _FakeWeatherResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"current": {"temperature_2m": 20, "relative_humidity_2m": 60, "wind_speed_10m": 5, "precipitation": 0.0, "rain": 0.0, "weather_code": 1}}

    weather_calls = []

    def _fake_weather_get(*args, **kwargs):
        weather_calls.append({"args": args, "kwargs": kwargs})
        return _FakeWeatherResponse()

    monkeypatch.setattr(farms_routes.requests, "get", _fake_weather_get)

    response = client.get(
        f"/api/farms/{farm_id}/action-plan",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["farm_id"] == farm_id
    assert payload["priority"] in ("high", "medium", "low")
    assert "irrigation_advice" in payload
    assert payload["weather_advice"] == "Current: Mainly clear. Temp 20°C."
    assert "open_meteo_current_weather" in payload["data_sources"]
    assert weather_calls[0]["kwargs"]["params"]["current"] == (
        "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
    )
    assert weather_calls[0]["kwargs"]["params"]["timezone"] == "auto"


def test_action_plan_blocks_other_user(client):
    _login_token(client, username="owner_user")
    intruder_token = _login_token(client, username="intruder_user")
    owner = config.get_db().users.find_one({"username": "owner_user"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {"farm_name": "Private Action Farm", "owner_id": owner["_id"], "sensors": [], "weather_logs": [], "alerts_history": []}
        ).inserted_id
    )

    response = client.get(
        f"/api/farms/{farm_id}/action-plan",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 403


def test_action_plan_missing_sensors_returns_partial_plan(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = str(
        config.get_db().farms.insert_one(
            {"farm_name": "NoSensor Farm", "owner_id": owner["_id"], "sensors": [], "weather_logs": [], "alerts_history": []}
        ).inserted_id
    )

    def _raise_request_error(*args, **kwargs):
        raise farms_routes.requests.RequestException("Open-Meteo unavailable")

    monkeypatch.setattr(farms_routes.requests, "get", _raise_request_error)

    response = client.get(
        f"/api/farms/{farm_id}/action-plan",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["irrigation_advice"].startswith("Soil moisture data missing")
    assert payload["weather_advice"] == "Current: Partly cloudy. Temp 21.8°C."
    assert "None°C" not in payload["weather_advice"]
    assert "fallback_simulated_weather" in payload["data_sources"]


def test_action_plan_ai_scan_influences_recommendation(client, monkeypatch):
    token = _login_token(client)
    owner = config.get_db().users.find_one({"username": "farmer_one"})
    farm_id = config.get_db().farms.insert_one(
        {"farm_name": "AI Farm", "owner_id": owner["_id"], "sensors": [{"sensor_id": "soil-1", "type": "soil_moisture", "readings": [{"value": 35}]}], "weather_logs": [], "alerts_history": []}
    ).inserted_id

    # insert ai scan indicating water stress
    config.get_db().ai_scans.insert_one({
        "user_id": str(owner["_id"]),
        "farm_id": str(farm_id),
        "prediction": {"label": "Water Stress Signs", "severity": "high", "confidence": 0.85},
        "recommendation": "Check irrigation coverage",
        "created_at": __import__("datetime").datetime.utcnow(),
    })

    class _FakeWeatherResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"current": {"temperature_2m": 22, "relative_humidity_2m": 60, "wind_speed_10m": 5, "precipitation": 0.0, "rain": 0.0, "weather_code": 1}}

    monkeypatch.setattr(farms_routes.requests, "get", lambda *args, **kwargs: _FakeWeatherResponse())

    response = client.get(f"/api/farms/{str(farm_id)}/action-plan", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.get_json()
    # AI scan should be included as a data source and its detection mentioned in reasons
    assert "ai_scan" in payload["data_sources"]
    assert any("AI scan detected" in r or "Water Stress" in r for r in payload["reasons"]) or any("AI scan" in a for a in payload["recommended_actions"])
