from datetime import datetime, timedelta, timezone
import random
import requests
from bson import ObjectId
from flask import Blueprint, jsonify, make_response, request
from pymongo.errors import PyMongoError

from blueprints.farms.models import (
    validate_alert_payload,
    validate_farm_payload,
    validate_sensor_reading_payload,
    validate_sensor_payload,
)
import config
from decorators import jwt_required
from extensions import limiter
from utils.validators import serialize_document, validate_farm_input

farms_bp = Blueprint("farms_bp", __name__)


def _error_response(message, status_code, **extra):
    payload = {"message": message}
    payload.update(extra)
    return make_response(jsonify(payload), status_code)


def _farms_collection():
    return config.get_db().farms


def _sensor_value(sensor_type):
    ranges = {
        "soil_moisture": (45, 70, "%"),
        "temperature": (18, 26, "°C"),
        "humidity": (55, 75, "%"),
        "light": (20000, 50000, "lux"),
        "ph": (5.8, 7.2, "pH"),
    }
    low, high, unit = ranges[sensor_type]
    value = random.randint(low, high) if sensor_type == "light" else round(random.uniform(low, high), 1)
    return value, unit


def _generate_default_sensors(farm_id, user_id, timestamp=None):
    timestamp = timestamp or datetime.now(timezone.utc)
    farm_id_text = str(farm_id)
    user_id_text = str(user_id)
    sensors = []

    for sensor_type in ["soil_moisture", "temperature", "humidity", "light", "ph"]:
        value, unit = _sensor_value(sensor_type)
        sensors.append(
            {
                "sensor_id": f"{sensor_type.upper()}-{farm_id_text[-6:]}",
                "farm_id": farm_id_text,
                "user_id": user_id_text,
                "type": sensor_type,
                "value": value,
                "unit": unit,
                "status": "active",
                "timestamp": timestamp,
                "source": "auto_generated_demo_sensor",
                "readings": [
                    {
                        "value": value,
                        "unit": unit,
                        "timestamp": timestamp,
                        "source": "auto_generated_demo_sensor",
                    }
                ],
            }
        )

    return sensors


def _sensor_type(sensor):
    return str(sensor.get("type", "")).strip().lower().replace(" ", "_")


def _sensor_numeric_value(sensor):
    value = sensor.get("value")
    readings = sensor.get("readings", [])
    if value is None and isinstance(readings, list) and readings:
        latest = readings[-1]
        if isinstance(latest, dict):
            value = latest.get("value")

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sensor_timestamp(sensor):
    timestamp = sensor.get("timestamp")
    readings = sensor.get("readings", [])
    if timestamp is None and isinstance(readings, list) and readings:
        latest = readings[-1]
        if isinstance(latest, dict):
            timestamp = latest.get("timestamp")
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    return str(timestamp or "")


def _format_sensor_value(sensor):
    value = sensor.get("value")
    readings = sensor.get("readings", [])
    if value is None and isinstance(readings, list) and readings:
        latest = readings[-1]
        if isinstance(latest, dict):
            value = latest.get("value")
    unit = sensor.get("unit", "")
    return f"{value}{unit}" if value is not None else "No reading"


def _latest_sensor_reading(sensor):
    readings = sensor.get("readings", [])
    if isinstance(readings, list) and readings:
        latest = readings[-1]
        if isinstance(latest, dict):
            return latest
    return None


def _normalise_sensor_reading_entry(farm_id, current_user, sensor_type, value, unit, notes=None):
    timestamp = datetime.now(timezone.utc)
    return {
        "farm_id": str(farm_id),
        "user_id": str(current_user["_id"]),
        "username": current_user.get("username"),
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit,
        "notes": notes,
        "timestamp": timestamp,
        "source": "manual_sensor_reading",
    }


def _manual_sensor_id(sensor_type, farm_id):
    return f"MANUAL-{sensor_type.upper()}-{str(farm_id)[-6:]}"


def _upsert_manual_sensor_reading(farm, current_user, reading):
    sensor_type = reading["sensor_type"]
    reading_entry = _normalise_sensor_reading_entry(
        farm["_id"],
        current_user,
        sensor_type,
        reading["value"],
        reading["unit"],
        reading.get("notes"),
    )

    sensors = list(farm.get("sensors", []))
    target_sensor = None
    for sensor in sensors:
        if _sensor_type(sensor) == sensor_type:
            target_sensor = sensor
            break

    if target_sensor is None:
        target_sensor = {
            "sensor_id": _manual_sensor_id(sensor_type, farm["_id"]),
            "farm_id": str(farm["_id"]),
            "user_id": str(current_user["_id"]),
            "type": sensor_type,
            "value": reading["value"],
            "unit": reading["unit"],
            "status": "active",
            "timestamp": reading_entry["timestamp"],
            "source": "manual_sensor_reading",
            "notes": reading.get("notes"),
            "readings": [reading_entry],
        }
        sensors.append(target_sensor)
    else:
        readings = list(target_sensor.get("readings", []))
        readings.append(reading_entry)
        target_sensor["readings"] = readings
        target_sensor["value"] = reading["value"]
        target_sensor["unit"] = reading["unit"]
        target_sensor["timestamp"] = reading_entry["timestamp"]
        target_sensor["user_id"] = str(current_user["_id"])
        target_sensor["source"] = "manual_sensor_reading"
        target_sensor["notes"] = reading.get("notes")

    return sensors, reading_entry, target_sensor


def _iso_timestamp(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _sensor_reading_points(sensor):
    readings = sensor.get("readings", [])
    points = []
    if isinstance(readings, list):
        for reading in readings:
            if not isinstance(reading, dict):
                continue
            try:
                value = float(reading.get("value"))
            except (TypeError, ValueError):
                continue
            points.append(
                {
                    "timestamp": _iso_timestamp(reading.get("timestamp") or sensor.get("timestamp")),
                    "value": value,
                }
            )

    if points:
        return points

    value = _sensor_numeric_value(sensor)
    if value is None:
        return []
    return [{"timestamp": _iso_timestamp(sensor.get("timestamp")), "value": value}]


def _simulated_trend_points(latest_value, sensor_type):
    fallback_values = {
        "soil_moisture": 58.0,
        "temperature": 22.0,
        "humidity": 64.0,
    }
    base = latest_value if latest_value is not None else fallback_values[sensor_type]
    now = datetime.now(timezone.utc)
    offsets = [-5, -3, -1, 2, 0, 1]
    points = []
    for index, offset in enumerate(offsets):
        points.append(
            {
                "timestamp": (now - timedelta(hours=5 - index)).isoformat(),
                "value": round(base + offset, 1),
            }
        )
    return points


def _sensor_history_payload(farm):
    required_types = ["soil_moisture", "temperature", "humidity"]
    sensors_by_type = {
        _sensor_type(sensor): sensor
        for sensor in farm.get("sensors", [])
        if _sensor_type(sensor) in required_types
    }
    stored_points = {
        sensor_type: _sensor_reading_points(sensors_by_type.get(sensor_type, {}))
        for sensor_type in required_types
    }
    has_history = any(len(points) > 1 for points in stored_points.values())
    data_source = "stored_sensor_readings" if has_history else "simulated_from_latest"

    if data_source == "stored_sensor_readings":
        series_points = stored_points
    else:
        series_points = {
            sensor_type: _simulated_trend_points(
                _sensor_numeric_value(sensors_by_type.get(sensor_type, {})),
                sensor_type,
            )
            for sensor_type in required_types
        }

    max_length = max((len(points) for points in series_points.values()), default=0)
    timestamps = []
    for index in range(max_length):
        timestamp = next(
            (
                points[index]["timestamp"]
                for points in series_points.values()
                if index < len(points) and points[index].get("timestamp")
            ),
            "",
        )
        timestamps.append(timestamp)

    series = {}
    for sensor_type, points in series_points.items():
        values = [point["value"] for point in points]
        while len(values) < max_length:
            values.append(values[-1] if values else None)
        series[sensor_type] = values

    return {
        "farm_id": str(farm["_id"]),
        "farm_name": farm.get("farm_name", "Farm"),
        "timestamps": timestamps,
        "series": series,
        "data_source": data_source,
    }


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _farm_coordinates(farm):
    latitude = _to_float(farm.get("latitude"))
    longitude = _to_float(farm.get("longitude"))
    if latitude is not None and longitude is not None:
        return latitude, longitude, "stored_coordinates"

    location = farm.get("location")
    if isinstance(location, dict):
        coordinates = location.get("coordinates", [])
        if isinstance(coordinates, list) and len(coordinates) == 2:
            longitude = _to_float(coordinates[0])
            latitude = _to_float(coordinates[1])
            if latitude is not None and longitude is not None:
                return latitude, longitude, "stored_coordinates"

    area_name = str(farm.get("address", {}).get("area_name", "")).lower()
    if "london" in area_name:
        return 51.5072, -0.1276, "approximate_demo_location"
    return 54.5973, -5.9301, "approximate_demo_location"


def _weather_condition_summary(weather_code):
    summaries = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
    }
    return summaries.get(weather_code, "Weather conditions unavailable")


def _fallback_weather_payload(farm, latitude, longitude, location_source):
    weather_code = 2
    return {
        "farm_id": str(farm["_id"]),
        "farm_name": farm.get("farm_name", "Farm"),
        "latitude": latitude,
        "longitude": longitude,
        "location_source": location_source,
        "temperature_c": 21.8,
        "humidity_percent": 66,
        "wind_speed_kmh": 12.4,
        "precipitation_mm": 0.2,
        "rain_mm": 0.0,
        "weather_code": weather_code,
        "condition_summary": _weather_condition_summary(weather_code),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": "Open-Meteo",
        "data_source": "fallback_simulated_weather",
    }


def _open_meteo_weather_payload(farm, latitude, longitude, location_source, weather_data):
    current = weather_data.get("current", {})
    weather_code = current.get("weather_code")
    return {
        "farm_id": str(farm["_id"]),
        "farm_name": farm.get("farm_name", "Farm"),
        "latitude": latitude,
        "longitude": longitude,
        "location_source": location_source,
        "temperature_c": current.get("temperature_2m"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "precipitation_mm": current.get("precipitation"),
        "rain_mm": current.get("rain"),
        "weather_code": weather_code,
        "condition_summary": _weather_condition_summary(weather_code),
        "timestamp": current.get("time") or datetime.now(timezone.utc).isoformat(),
        "provider": "Open-Meteo",
        "data_source": "open_meteo_current_weather",
    }


def get_farm_if_authorised(farm_id, current_user):
    """
    Fetch a farm and verify authorization in one database query.
    Returns: (farm_object, error_response) tuple
    - On success: (farm, None)
    - On error: (None, error_response)
    """

    if not ObjectId.is_valid(farm_id):
        return (
            None,
            _error_response(
                f"The farm id '{farm_id}' is not valid. Please use a MongoDB ObjectId.",
                400,
            ),
        )

    try:
        farm = _farms_collection().find_one({"_id": ObjectId(farm_id)})
        
        if not farm:
            return (
                None,
                _error_response(
                    f"No farm was found for id '{farm_id}'. Check the link or refresh the list and try again.",
                    404,
                ),
            )

        is_owner = str(farm.get("owner_id")) == str(current_user["_id"])
        is_admin = current_user.get("role") == "admin"
        
        if not (is_owner or is_admin):
            return (
                None,
                _error_response(
                    "You do not have permission to manage this farm. Only the owner or an admin can edit it.",
                    403,
                ),
            )

        return farm, None
        
    except Exception as e:
        return (
            None,
            _error_response(f"Database error: {str(e)}", 500)
        )


@farms_bp.route("/api/farms", methods=["GET"])
@limiter.limit("60 per minute")
def get_all_farms():
    page_raw = request.args.get("page", "1")
    limit_raw = request.args.get("limit", "20")
    try:
        page = max(1, int(page_raw))
        limit = max(1, min(100, int(limit_raw)))
    except (TypeError, ValueError):
        return _error_response(
            f"Invalid pagination parameters: page='{page_raw}' and limit='{limit_raw}' must both be whole numbers.",
            400,
        )

    skip = (page - 1) * limit
    try:
        total = _farms_collection().count_documents({})
        cursor = _farms_collection().find({}).skip(skip).limit(limit)
        farms_list = [serialize_document(farm) for farm in cursor]
    except PyMongoError as exc:
        return _error_response(
            "Unable to load farms right now because the database query failed.",
            500,
            error=str(exc),
        )

    return make_response(
        jsonify(
            {
                "data": farms_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "has_next": skip + len(farms_list) < total,
                },
            }
        ),
        200,
    )


@farms_bp.route("/api/farms/<farm_id>", methods=["GET"])
def get_single_farm(farm_id):
    if not ObjectId.is_valid(farm_id):
        return _error_response("Invalid ID format", 400)

    farm = _farms_collection().find_one({"_id": ObjectId(farm_id)})
    if not farm:
        return _error_response("Farm not found", 404)

    return make_response(jsonify(serialize_document(farm)), 200)


@farms_bp.route("/api/farms", methods=["POST"])
@jwt_required
def create_farm(current_user):
    json_data = request.get_json(silent=True)
    
    
    farm_data, error = validate_farm_payload(json_data)
    if error:
        return _error_response(
            f"Unable to create farm: {error}",
            400,
        )
    
    
    _, validation_errors = validate_farm_input(farm_data)
    if validation_errors:
        return _error_response(
            "Validation failed",
            400,
            errors=validation_errors,
        )

    farm_id = ObjectId()
    farm_data["_id"] = farm_id
    farm_data["owner_id"] = current_user["_id"]
    farm_data["created_at"] = datetime.now(timezone.utc)
    if not farm_data.get("sensors"):
        farm_data["sensors"] = _generate_default_sensors(farm_id, current_user["_id"])
    result = _farms_collection().insert_one(farm_data)

    return make_response(
        jsonify({"message": "Farm registered successfully!", "farm_id": str(result.inserted_id)}),
        201,
    )


@farms_bp.route("/api/farms/<farm_id>", methods=["PUT"])
@jwt_required
def update_farm(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)  
    if error_response:
        return error_response

    json_data = request.get_json(silent=True)
    
    
    updates, error = validate_farm_payload(json_data, partial=True)
    if error:
        return _error_response(f"Unable to update farm: {error}", 400)
    
    
    _, validation_errors = validate_farm_input(updates)
    if validation_errors:
        return _error_response(
            "Validation failed",
            400,
            errors=validation_errors,
        )

    try:
        result = _farms_collection().update_one({"_id": ObjectId(farm_id)}, {"$set": updates})
    except PyMongoError as exc:
        return _error_response("Database error while updating farm.", 500, error=str(exc))

    if result.matched_count == 0:
        return _error_response(f"Farm '{farm_id}' was not found in the database.", 404)

    return make_response(jsonify({"message": "Farm updated successfully!"}), 200)


@farms_bp.route("/api/farms/<farm_id>", methods=["DELETE"])
@jwt_required
def delete_farm(current_user, farm_id):
    if current_user.get("role") != "admin":
        return _error_response(
            "Only admin users can delete farms.",
            403,
        )

    if not ObjectId.is_valid(farm_id):
        return _error_response(
            f"The farm id '{farm_id}' is not valid. Please use a MongoDB ObjectId.",
            400,
        )

    result = _farms_collection().delete_one({"_id": ObjectId(farm_id)})
    if result.deleted_count == 0:
        return _error_response(
            f"No farm was found for id '{farm_id}'. Nothing was deleted.",
            404,
        )

    return make_response(jsonify({"message": "Farm deleted successfully"}), 200)


@farms_bp.route("/api/farms/<farm_id>/sensors", methods=["POST"])
@jwt_required
def add_sensor(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    sensor, error = validate_sensor_payload(request.get_json(silent=True))
    if error:
        return _error_response(
            f"Unable to add sensor to farm '{farm_id}': {error}",
            400,
        )

    _farms_collection().update_one({"_id": ObjectId(farm_id)}, {"$push": {"sensors": sensor}})
    return make_response(jsonify({"message": "Sensor added to farm!", "sensor": sensor}), 201)


@farms_bp.route("/api/farms/<farm_id>/sensors/readings", methods=["POST"])
@jwt_required
def add_sensor_reading(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    reading, error = validate_sensor_reading_payload(request.get_json(silent=True))
    if error:
        return _error_response(
            f"Unable to add sensor reading to farm '{farm_id}': {error}",
            400,
        )

    sensors, reading_entry, updated_sensor = _upsert_manual_sensor_reading(farm, current_user, reading)
    update_fields = {
        "sensors": sensors,
        "updated_at": datetime.now(timezone.utc),
    }
    _farms_collection().update_one({"_id": ObjectId(farm_id)}, {"$set": update_fields})

    return make_response(
        jsonify(
            {
                "message": "Sensor reading added successfully.",
                "farm_id": str(farm_id),
                "sensor_type": reading["sensor_type"],
                "reading": serialize_document(reading_entry),
                "sensor": serialize_document(updated_sensor),
            }
        ),
        201,
    )


@farms_bp.route("/api/farms/<farm_id>/sensors", methods=["GET"])
@jwt_required
def get_farm_sensors(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    sensors = farm.get("sensors", [])
    return make_response(
        jsonify(
            {
                "farm_id": str(farm["_id"]),
                "count": len(sensors),
                "sensors": serialize_document(sensors),
            }
        ),
        200,
    )


@farms_bp.route("/api/farms/<farm_id>/sensors/demo", methods=["POST"])
@jwt_required
def generate_demo_sensors(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    sensors = _generate_default_sensors(farm["_id"], current_user["_id"])
    _farms_collection().update_one(
        {"_id": ObjectId(farm_id)},
        {"$set": {"sensors": sensors}},
    )
    return make_response(
        jsonify(
            {
                "message": "Demo sensors generated.",
                "farm_id": farm_id,
                "count": len(sensors),
                "sensors": serialize_document(sensors),
            }
        ),
        201,
    )


@farms_bp.route("/api/farms/my", methods=["GET"])
@jwt_required
def get_my_farms(current_user):
    page_raw = request.args.get("page", "1")
    limit_raw = request.args.get("limit", "9")
    try:
        page = max(1, int(page_raw))
        limit = max(1, min(100, int(limit_raw)))
    except (TypeError, ValueError):
        return _error_response(
            f"Invalid pagination parameters: page='{page_raw}' and limit='{limit_raw}' must both be whole numbers.",
            400,
        )

    skip = (page - 1) * limit
    query = {"owner_id": current_user["_id"]}
    try:
        total = _farms_collection().count_documents(query)
        cursor = _farms_collection().find(query).skip(skip).limit(limit)
        farms_list = [serialize_document(farm) for farm in cursor]
    except PyMongoError as exc:
        return _error_response(
            "Unable to load your farms right now because the database query failed.",
            500,
            error=str(exc),
        )

    return make_response(
        jsonify(
            {
                "data": farms_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "has_next": skip + len(farms_list) < total,
                },
            }
        ),
        200,
    )


@farms_bp.route("/api/farms/search", methods=["GET"])
@limiter.limit("30 per minute")
def search_farms():
    search_term = request.args.get("q", "").strip()
    if not search_term:
        return _error_response(
            "Search failed because no query was provided. Add a value to the q parameter and try again.",
            400,
        )

    page_raw = request.args.get("page", "1")
    limit_raw = request.args.get("limit", "20")
    try:
        page = max(1, int(page_raw))
        limit = max(1, min(100, int(limit_raw)))
    except (TypeError, ValueError):
        return _error_response(
            f"Invalid pagination parameters: page='{page_raw}' and limit='{limit_raw}' must both be whole numbers.",
            400,
        )

    skip = (page - 1) * limit
    
    # ✅ UPDATED: Search in farm_name, crop_type, and address.area_name
    search_query = {
        "$or": [
            {"farm_name": {"$regex": search_term, "$options": "i"}},
            {"crop_type": {"$regex": search_term, "$options": "i"}},
            {"address.area_name": {"$regex": search_term, "$options": "i"}}
        ]
    }

    try:
        total = _farms_collection().count_documents(search_query)
        search_results = _farms_collection().find(search_query).skip(skip).limit(limit)
        farms_list = [serialize_document(farm) for farm in search_results]
    except PyMongoError as exc:
        return _error_response(
            "Search failed because of a database error.",
            500,
            error=str(exc),
        )
    
    return make_response(
        jsonify({
            "results_count": len(farms_list),
            "total": total,
            "data": farms_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "has_next": skip + len(farms_list) < total,
            }
        }), 
        200
    )


@farms_bp.route("/api/farms/<farm_id>/sync_weather", methods=["POST"])
@jwt_required
def sync_weather(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user) 
    if error_response:
        return error_response

    coordinates = farm.get("location", {}).get("coordinates", [])
    if len(coordinates) != 2:
        return make_response(jsonify({"message": "Farm location is incomplete."}), 400)

    lng, lat = coordinates
    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}&current_weather=true"
    )

    try:
        response = requests.get(weather_url, timeout=3)
        response.raise_for_status()
        weather_data = response.json()
    except requests.RequestException as exc:
        return _error_response(
            "Unable to sync weather data right now. The external service is too slow.",
            503,
            error=str(exc),
        )

    current_weather = weather_data.get("current_weather", {})
    new_log = {
        "timestamp": datetime.now(timezone.utc),
        "temperature_celsius": current_weather.get("temperature"),
        "windspeed": current_weather.get("windspeed"),
        "conditions": "Synced from Open-Meteo API",
    }

    _farms_collection().update_one({"_id": ObjectId(farm_id)}, {"$push": {"weather_logs": new_log}})
    return make_response(jsonify({"message": "Weather synced!", "new_log": new_log}), 200)


@farms_bp.route("/api/farms/<farm_id>/weather", methods=["GET"])
@jwt_required
def get_farm_weather(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    latitude, longitude, location_source = _farm_coordinates(farm)
    weather_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "rain",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "timezone": "auto",
    }

    try:
        response = requests.get(weather_url, params=params, timeout=4)
        response.raise_for_status()
        payload = _open_meteo_weather_payload(
            farm,
            latitude,
            longitude,
            location_source,
            response.json(),
        )
    except requests.RequestException:
        payload = _fallback_weather_payload(farm, latitude, longitude, location_source)

    return make_response(jsonify(serialize_document(payload)), 200)


@farms_bp.route("/api/farms/alerts/broadcast", methods=["POST"])
@jwt_required
def broadcast_alert(current_user):
    if current_user.get("role") != "admin":
        return _error_response(
            "Only admin users can broadcast emergency alerts.",
            403,
        )

    data, error = validate_alert_payload(request.get_json(silent=True))
    if error:
        return _error_response(
            f"Unable to broadcast alert: {error}",
            400,
        )

    geo_query = {"location": {"$geoWithin": {"$geometry": data["danger_zone"]}}}
    alert_entry = {
        "alert_type": data["alert_type"],
        "timestamp": datetime.utcnow(),
        "message": f"EMERGENCY: {data['alert_type']} warning issued!",
        "issued_by": current_user.get("username", "admin"),
    }

    try:
        update_result = _farms_collection().update_many(
            geo_query,
            {"$push": {"alerts_history": alert_entry}},
        )
    except PyMongoError as exc:
        return _error_response(
            "Unable to broadcast alert because the geospatial database update failed.",
            500,
            error=str(exc),
        )

    return make_response(
        jsonify(
            {
                "message": "Alert broadcast!",
                "farms_notified": update_result.matched_count,
            }
        ),
        200,
    )


@farms_bp.route("/api/farms/<farm_id>/insights", methods=["GET"])
@jwt_required
def get_farm_insights(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    pipeline = [
        {"$match": {"_id": ObjectId(farm_id)}},
        {"$unwind": "$weather_logs"},
        {
            "$group": {
                "_id": "$_id",
                "farm_name": {"$first": "$farm_name"},
                "average_temp": {"$avg": "$weather_logs.temperature_celsius"},
                "average_wind": {"$avg": "$weather_logs.windspeed"},
            }
        },
    ]

    try:
        result = list(_farms_collection().aggregate(pipeline))
    except PyMongoError as exc:
        return _error_response(
            "Unable to generate farm insights because the database aggregation failed.",
            500,
            error=str(exc),
        )

    if not result:
        return _error_response(
            "There is not enough weather log data to generate insights for this farm yet.",
            404,
        )

    insights = serialize_document(result[0])
    if insights.get("average_temp") is not None:
        insights["average_temp"] = round(insights["average_temp"], 2)
    if insights.get("average_wind") is not None:
        insights["average_wind"] = round(insights["average_wind"], 2)

    return make_response(jsonify({"message": "Insights generated", "dashboard_data": insights}), 200)


@farms_bp.route("/api/farms/<farm_id>/irrigation_check", methods=["GET"])
@jwt_required
def check_irrigation(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)  
    if error_response:
        return error_response

    moisture_level = None
    for sensor in farm.get("sensors", []):
        if _sensor_type(sensor) == "soil_moisture":
            moisture_level = _sensor_numeric_value(sensor)
            break

    if moisture_level is None:
        return _error_response(
            "No soil moisture sensor data is available for this farm, so irrigation status cannot be calculated.",
            404,
        )

    try:
        moisture_val = float(moisture_level)
    except (TypeError, ValueError):
        return _error_response(
            f"The latest soil moisture reading '{moisture_level}' is not a valid number.",
            400,
        )

    status = "WARNING" if moisture_val < 20.0 else "OK"
    return make_response(jsonify({"status": status, "moisture": moisture_val}), 200)


@farms_bp.route("/api/farms/<farm_id>/sensor-history", methods=["GET"])
@jwt_required
def get_sensor_history(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    return make_response(jsonify(serialize_document(_sensor_history_payload(farm))), 200)


@farms_bp.route("/api/farms/<farm_id>/action-plan", methods=["GET"])
@jwt_required
def get_action_plan(current_user, farm_id):
    farm, error_response = get_farm_if_authorised(farm_id, current_user)
    if error_response:
        return error_response

    plan = {
        "farm_id": str(farm.get("_id")),
        "farm_name": farm.get("farm_name", "Farm"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "priority": "low",
        "overall_status": "No urgent actions detected",
        "irrigation_advice": "No data",
        "crop_health_advice": "No data",
        "weather_advice": "No data",
        "sensor_advice": "No data",
        "recommended_actions": [],
        "reasons": [],
        "data_sources": [],
        "confidence": "low",
    }

    # Latest sensors
    sensors = farm.get("sensors", []) or []
    sensor_map = { _sensor_type(s): s for s in sensors }
    soil = sensor_map.get("soil_moisture")
    soil_val = _sensor_numeric_value(soil) if soil else None
    if soil is not None:
        plan["data_sources"].append("sensors")
        plan["sensor_advice"] = _format_sensor_value(soil)

    # Sensor history
    history = _sensor_history_payload(farm)
    if history.get("data_source"):
        plan["data_sources"].append(history["data_source"])

    # Weather
    lat, lng, loc_src = _farm_coordinates(farm)
    try:
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lng}&current_weather=true"
        )
        resp = requests.get(weather_url, timeout=3)
        resp.raise_for_status()
        weather_payload = _open_meteo_weather_payload(farm, lat, lng, loc_src, resp.json())
        plan["data_sources"].append("open_meteo_current_weather")
    except Exception:
        weather_payload = _fallback_weather_payload(farm, lat, lng, loc_src)
        plan["data_sources"].append("fallback_simulated_weather")

    plan["weather_advice"] = (
        f"Current: {weather_payload.get('condition_summary')}. "
        f"Temp {weather_payload.get('temperature_c')}°C."
    )

    # AI scan influence
    latest_scan = config.get_db().ai_scans.find_one({"farm_id": str(farm.get("_id"))}, sort=[("created_at", -1)])
    if latest_scan:
        plan["data_sources"].append("ai_scan")
        prediction = latest_scan.get("prediction", {})
        label = prediction.get("label") or latest_scan.get("recommendation")
        severity = prediction.get("severity") or prediction.get("severity")
        plan["crop_health_advice"] = label or "AI scan available"
        if prediction.get("severity") == "high" or prediction.get("severity") == "medium":
            plan["recommended_actions"].append("Inspect crop area highlighted by latest AI scan and act on recommendations.")
            plan["reasons"].append(f"AI scan detected: {label}")

    # Irrigation logic
    precip = weather_payload.get("precipitation_mm") or 0
    if soil_val is None:
        plan["irrigation_advice"] = "Soil moisture data missing. Check sensors or take manual reading."
        plan["recommended_actions"].append("Verify soil moisture with sensor or manual probe.")
        plan["reasons"].append("No recent soil moisture sensor available")
        plan["priority"] = "medium"
    else:
        try:
            moisture = float(soil_val)
        except Exception:
            moisture = None

        if moisture is None:
            plan["irrigation_advice"] = "Invalid soil moisture reading"
        else:
            if moisture < 25 and (precip or 0) < 1.0:
                plan["irrigation_advice"] = "Irrigate today — soil moisture is low."
                plan["recommended_actions"].append("Irrigate affected zones today to reach optimal moisture.")
                plan["reasons"].append(f"Low soil moisture: {moisture}")
                plan["priority"] = "high"
            elif moisture < 40:
                plan["irrigation_advice"] = "Consider irrigation in next 24-48 hours."
                plan["recommended_actions"].append("Monitor soil moisture and irrigate if it falls below 30%.")
                plan["reasons"].append(f"Moderate soil moisture: {moisture}")
                if plan["priority"] != "high":
                    plan["priority"] = "medium"
            else:
                plan["irrigation_advice"] = "Soil moisture is within acceptable range."

    # Priority and overall status synthesis
    if plan["priority"] == "high":
        plan["overall_status"] = "High priority: immediate attention required"
    elif plan["priority"] == "medium":
        plan["overall_status"] = "Medium priority: monitor and act soon"
    else:
        plan["overall_status"] = "Low priority: routine monitoring"

    # Confidence heuristics
    confidence = "low"
    if latest_scan and sensors and weather_payload:
        confidence = "high"
    elif sensors or latest_scan or weather_payload:
        confidence = "medium"
    plan["confidence"] = confidence

    # Trim duplicates in data_sources
    plan["data_sources"] = list(dict.fromkeys(plan["data_sources"]))

    return make_response(jsonify(plan), 200)


@farms_bp.route("/api/dashboard/summary", methods=["GET"])
@jwt_required
def get_dashboard_summary(current_user):
    query = {"owner_id": current_user["_id"]}
    try:
        farms = list(_farms_collection().find(query))
    except PyMongoError as exc:
        return _error_response(
            "Unable to load dashboard summary because the database query failed.",
            500,
            error=str(exc),
        )

    sensors = []
    soil_values = []
    temperature_sensors = []
    humidity_sensors = []
    active_alerts_count = 0
    sensor_rows = []

    for farm in farms:
        farm_name = farm.get("farm_name", "Farm")
        farm_sensors = farm.get("sensors", [])
        sensors.extend(farm_sensors)
        active_alerts_count += len(farm.get("alerts_history", []))

        for sensor in farm_sensors:
            sensor_type = _sensor_type(sensor)
            value = _sensor_numeric_value(sensor)
            if sensor_type == "soil_moisture" and value is not None:
                soil_values.append(value)
            if sensor_type == "temperature":
                temperature_sensors.append(sensor)
            if sensor_type == "humidity":
                humidity_sensors.append(sensor)
            sensor_rows.append(
                {
                    "sensor": sensor.get("sensor_id", "Unknown"),
                    "farm": farm_name,
                    "type": sensor.get("type", "Unknown"),
                    "value": _format_sensor_value(sensor),
                    "status": str(sensor.get("status", "unknown")),
                }
            )

    average_soil_moisture = round(sum(soil_values) / len(soil_values), 1) if soil_values else None
    latest_temperature_sensor = max(temperature_sensors, key=_sensor_timestamp, default=None)
    latest_humidity_sensor = max(humidity_sensors, key=_sensor_timestamp, default=None)
    latest_temperature = _sensor_numeric_value(latest_temperature_sensor) if latest_temperature_sensor else None
    latest_humidity = _sensor_numeric_value(latest_humidity_sensor) if latest_humidity_sensor else None

    if average_soil_moisture is None:
        irrigation_recommendation = "Add soil moisture sensors to calculate irrigation guidance."
    elif average_soil_moisture < 45:
        irrigation_recommendation = "Irrigation recommended: average soil moisture is below the target range."
    elif average_soil_moisture > 70:
        irrigation_recommendation = "No irrigation recommended: soil moisture is above the target range."
    else:
        irrigation_recommendation = "No irrigation required: soil moisture is in the optimal range."

    return make_response(
        jsonify(
            {
                "total_farms": len(farms),
                "total_sensors": len(sensors),
                "average_soil_moisture": average_soil_moisture,
                "latest_temperature": latest_temperature,
                "latest_humidity": latest_humidity,
                "active_alerts_count": active_alerts_count,
                "irrigation_recommendation": irrigation_recommendation,
                "sensor_rows": sensor_rows[:8],
            }
        ),
        200,
    )


@farms_bp.route("/api/farms/region/<region_name>/insights", methods=["GET"])
def get_regional_insights(region_name):
    pipeline = [
        {"$match": {"address.area_name": region_name}},
        {"$limit": 500},
        {"$unwind": "$weather_logs"},
        {
            "$group": {
                "_id": region_name,
                "community_avg_temp": {"$avg": "$weather_logs.temperature_celsius"},
                "unique_farms": {"$addToSet": "$_id"},
            }
        },
        {
            "$project": {
                "community_avg_temp": {"$round": ["$community_avg_temp", 2]},
                "total_farms_included": {"$size": "$unique_farms"},
            }
        },
    ]

    try:
        result = list(_farms_collection().aggregate(pipeline))
    except PyMongoError as exc:
        return _error_response(
            f"Unable to generate regional insights for '{region_name}' because the database aggregation failed.",
            500,
            error=str(exc),
        )

    if not result:
        return _error_response(
            f"No farms with weather logs were found for region '{region_name}'.",
            404,
        )

    return make_response(jsonify({"message": "Community averages", "data": serialize_document(result[0])}), 200)
