from copy import deepcopy

from utils.validators import is_non_empty_string


def validate_farm_payload(data, partial=False):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."

    allowed_fields = {"farm_name", "crop_type", "address", "location"}
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


def validate_alert_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."
    if not is_non_empty_string(data.get("alert_type")):
        return None, "alert_type is required."
    if "danger_zone" not in data:
        return None, "danger_zone is required."
    return data, None
