from copy import deepcopy

from utils.validators import is_non_empty_string


SENSOR_READING_RANGES = {
    "soil_moisture": (0, 100),
    "temperature": (-10, 60),
    "humidity": (0, 100),
    "light": (0, 120000),
    "ph": (0, 14),
}

SENSOR_READING_DEFAULT_UNITS = {
    "soil_moisture": "%",
    "temperature": "°C",
    "humidity": "%",
    "light": "lux",
    "ph": "pH",
}


def validate_farm_payload(data, partial=False):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."

    allowed_fields = {
        "farm_name",
        "crop_type",
        "address",
        "location",
        "latitude",
        "longitude",
    }
    if partial:
        updates = {key: value for key, value in data.items() if key in allowed_fields}
        if not updates:
            return None, "No valid fields provided."
        if "farm_name" in updates and not is_non_empty_string(updates["farm_name"]):
            return None, "farm_name must be a non-empty string."
        return updates, None

    if not is_non_empty_string(data.get("farm_name")):
        return None, "Please provide at least a farm_name."

    farm = deepcopy(data)
    farm["farm_name"] = farm["farm_name"].strip()
    farm.setdefault("sensors", [])
    farm.setdefault("weather_logs", [])
    farm.setdefault("alerts_history", [])
    return farm, None


def validate_sensor_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."
    if not is_non_empty_string(data.get("sensor_id")):
        return None, "sensor_id is required."
    if not is_non_empty_string(data.get("type")):
        return None, "type is required."

    return {
        "sensor_id": data["sensor_id"].strip(),
        "type": data["type"].strip(),
        "status": data.get("status", True),
        "readings": data.get("readings", []),
    }, None


def validate_sensor_reading_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."

    sensor_type = str(data.get("sensor_type", "")).strip().lower().replace(" ", "_")
    if sensor_type not in SENSOR_READING_RANGES:
        return None, "sensor_type must be one of soil_moisture, temperature, humidity, light, or ph."

    try:
        value = float(data.get("value"))
    except (TypeError, ValueError):
        return None, "value must be a number."

    min_value, max_value = SENSOR_READING_RANGES[sensor_type]
    if value < min_value or value > max_value:
        return None, f"{sensor_type} must be between {min_value} and {max_value}."

    unit = str(data.get("unit") or SENSOR_READING_DEFAULT_UNITS[sensor_type]).strip()
    if not unit:
        return None, "unit is required."

    notes = data.get("notes")
    if notes is not None and not is_non_empty_string(notes):
        return None, "notes must be a non-empty string when provided."

    return {
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit,
        "notes": notes.strip() if isinstance(notes, str) else None,
    }, None


def validate_alert_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."
    if not is_non_empty_string(data.get("alert_type")):
        return None, "alert_type is required."
    if "danger_zone" not in data:
        return None, "danger_zone is required."
    return data, None
