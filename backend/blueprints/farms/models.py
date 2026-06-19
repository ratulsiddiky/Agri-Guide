from copy import deepcopy

from utils.validators import is_non_empty_string

LOCATION_SOURCES = {
    "browser_geolocation",
    "manual_coordinates",
    "manual_address",
    "approximate_demo_location",
}

ADDRESS_FIELDS = {
    "address_line",
    "city",
    "region",
    "postcode",
    "country",
}


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


def _clean_optional_string(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _coordinate(value, field_name, minimum, maximum):
    if value in (None, ""):
        return None, None
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None, f"{field_name} must be a number."
    if coordinate < minimum or coordinate > maximum:
        return None, f"{field_name} must be between {minimum} and {maximum}."
    return coordinate, None


def _normalise_address(updates):
    address = updates.get("address")
    if not isinstance(address, dict):
        address = {}

    region = _clean_optional_string(updates.get("region"))
    if region is None:
        region = _clean_optional_string(address.get("area_name"))
    postcode = _clean_optional_string(updates.get("postcode"))
    if postcode is None:
        postcode = _clean_optional_string(address.get("postcode"))

    for field in ADDRESS_FIELDS:
        if field in updates:
            cleaned = _clean_optional_string(updates.get(field))
            if cleaned is None:
                updates.pop(field, None)
            else:
                updates[field] = cleaned

    if region:
        updates["region"] = region
        address["area_name"] = region
    if postcode:
        updates["postcode"] = postcode
        address["postcode"] = postcode
    if address:
        updates["address"] = address


def _normalise_location_fields(updates):
    latitude_present = "latitude" in updates and updates.get("latitude") not in (None, "")
    longitude_present = "longitude" in updates and updates.get("longitude") not in (None, "")
    if latitude_present != longitude_present:
        return "latitude and longitude must be provided together."

    if latitude_present and longitude_present:
        latitude, error = _coordinate(updates.get("latitude"), "latitude", -90, 90)
        if error:
            return error
        longitude, error = _coordinate(updates.get("longitude"), "longitude", -180, 180)
        if error:
            return error
        updates["latitude"] = latitude
        updates["longitude"] = longitude
        updates["location"] = {
            "type": "Point",
            "coordinates": [longitude, latitude],
        }

    location_source = updates.get("location_source")
    if location_source in (None, ""):
        location_source = None
    elif location_source not in LOCATION_SOURCES:
        return "location_source must be one of browser_geolocation, manual_coordinates, manual_address, or approximate_demo_location."

    if latitude_present and longitude_present:
        if location_source not in {"browser_geolocation", "manual_coordinates"}:
            location_source = "manual_coordinates"
    elif location_source is None and any(updates.get(field) for field in ADDRESS_FIELDS):
        location_source = "manual_address"

    if location_source is not None:
        updates["location_source"] = location_source
    elif "location_source" in updates:
        updates.pop("location_source", None)

    return None


def _normalise_farm_payload(data):
    updates = deepcopy(data)
    if "farm_name" in updates and isinstance(updates["farm_name"], str):
        updates["farm_name"] = updates["farm_name"].strip()
    if "crop_type" in updates and isinstance(updates["crop_type"], str):
        updates["crop_type"] = updates["crop_type"].strip()

    _normalise_address(updates)
    location_error = _normalise_location_fields(updates)
    if location_error:
        return None, location_error
    return updates, None


def validate_farm_payload(data, partial=False):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."

    allowed_fields = {
        "farm_name",
        "crop_type",
        "address",
        "address_line",
        "city",
        "region",
        "postcode",
        "country",
        "location",
        "latitude",
        "longitude",
        "location_source",
    }
    if partial:
        updates = {key: value for key, value in data.items() if key in allowed_fields}
        if not updates:
            return None, "No valid fields provided."
        if "farm_name" in updates and not is_non_empty_string(updates["farm_name"]):
            return None, "farm_name must be a non-empty string."
        updates, error = _normalise_farm_payload(updates)
        if error:
            return None, error
        return updates, None

    if not is_non_empty_string(data.get("farm_name")):
        return None, "Please provide at least a farm_name."

    farm, error = _normalise_farm_payload(data)
    if error:
        return None, error
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
