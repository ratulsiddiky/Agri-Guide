from datetime import datetime, timezone
from io import BytesIO
import random
from time import perf_counter

from bson import ObjectId
from flask import Blueprint, jsonify, make_response, request
from werkzeug.utils import secure_filename

import config
from decorators import jwt_required

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    Image = None


smart_bp = Blueprint("smart_bp", __name__)
ALLOWED_SCAN_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_SCAN_BYTES = 5 * 1024 * 1024


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _json_response(payload, status_code=200):
    return make_response(jsonify(payload), status_code)


def _current_user_id(current_user):
    return str(current_user.get("_id"))


def _is_admin(current_user):
    return current_user.get("role") == "admin"


def _get_authorised_farm(farm_id, current_user):
    if not farm_id:
        return None, None

    if not ObjectId.is_valid(farm_id):
        return None, _json_response({"message": "Invalid farm_id."}, 400)

    farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)})
    if farm is None:
        return None, _json_response({"message": "Farm not found."}, 404)

    is_owner = str(farm.get("owner_id")) == _current_user_id(current_user)
    if not (is_owner or _is_admin(current_user)):
        return None, _json_response(
            {"message": "You do not have permission to view scans for this farm."},
            403,
        )

    return farm, None


def _allowed_scan_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_SCAN_EXTENSIONS


def _image_metadata(file_storage, image_bytes):
    filename = secure_filename(file_storage.filename or "crop-image")
    metadata = {
        "filename": filename,
        "content_type": file_storage.content_type,
        "width": None,
        "height": None,
    }

    if Image is None:
        return metadata

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            metadata["width"], metadata["height"] = image.size
            metadata["format"] = image.format
    except Exception:
        metadata["format"] = None

    return metadata


def _simulated_crop_prediction(filename, crop_type):
    haystack = f"{filename} {crop_type or ''}".lower()
    if any(token in haystack for token in ("healthy", "fresh", "normal")):
        label = "Healthy Leaf"
    elif any(token in haystack for token in ("blight", "spot", "tomato")):
        label = "Early Blight Risk"
    elif any(token in haystack for token in ("mildew", "powder", "white")):
        label = "Powdery Mildew Risk"
    elif any(token in haystack for token in ("yellow", "nutrient", "pale", "deficiency")):
        label = "Nutrient Deficiency Signs"
    elif any(token in haystack for token in ("dry", "wilt", "water", "stress")):
        label = "Water Stress Signs"
    else:
        label = random.choice(
            [
                "Healthy Leaf",
                "Early Blight Risk",
                "Powdery Mildew Risk",
                "Nutrient Deficiency Signs",
                "Water Stress Signs",
            ]
        )

    guidance = {
        "Healthy Leaf": {
            "severity": "low",
            "recommendation": "Crop appears healthy. Continue routine monitoring and keep sensor checks active.",
            "prevention_steps": [
                "Inspect leaves weekly for new spots or discoloration.",
                "Keep irrigation within the recommended soil moisture range.",
                "Record follow-up images if weather becomes humid or unusually hot.",
            ],
        },
        "Early Blight Risk": {
            "severity": "medium",
            "recommendation": "Remove affected leaves if visible and improve airflow around plants.",
            "prevention_steps": [
                "Avoid overhead watering where possible.",
                "Rotate susceptible crops between seasons.",
                "Check nearby plants for dark circular leaf spots.",
            ],
        },
        "Powdery Mildew Risk": {
            "severity": "medium",
            "recommendation": "Increase spacing or airflow and monitor humidity-heavy periods closely.",
            "prevention_steps": [
                "Prune dense foliage to reduce trapped humidity.",
                "Water near the soil line early in the day.",
                "Re-scan leaves after 48 hours if white patches spread.",
            ],
        },
        "Nutrient Deficiency Signs": {
            "severity": "medium",
            "recommendation": "Review recent fertiliser schedule and consider a soil nutrient test.",
            "prevention_steps": [
                "Check soil pH before adding fertiliser.",
                "Compare older and newer leaves for yellowing patterns.",
                "Apply balanced nutrients gradually to avoid over-correction.",
            ],
        },
        "Water Stress Signs": {
            "severity": "high",
            "recommendation": "Check soil moisture and irrigation coverage for this crop zone today.",
            "prevention_steps": [
                "Inspect emitters or irrigation lines for blockages.",
                "Mulch exposed soil to reduce evaporation.",
                "Increase monitoring during warm or windy weather.",
            ],
        },
    }

    confidence_ranges = {
        "Healthy Leaf": (0.82, 0.94),
        "Early Blight Risk": (0.74, 0.88),
        "Powdery Mildew Risk": (0.73, 0.87),
        "Nutrient Deficiency Signs": (0.7, 0.85),
        "Water Stress Signs": (0.76, 0.9),
    }
    low, high = confidence_ranges[label]

    return {
        "label": label,
        "confidence": round(random.uniform(low, high), 2),
        **guidance[label],
    }


def _scan_response(scan_doc):
    prediction = scan_doc.get("prediction", {})
    created_at = scan_doc.get("created_at") or datetime.now(timezone.utc)
    timestamp = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)

    return {
        "scan_id": str(scan_doc["_id"]),
        "farm_id": scan_doc.get("farm_id"),
        "crop_type": scan_doc.get("crop_type"),
        "model_mode": scan_doc.get("model_mode", "simulated_ai"),
        "model_type": "crop_leaf_health_classifier",
        "future_upgrade_model": "MobileNetV2 transfer learning CNN",
        "label": prediction.get("label"),
        "confidence": prediction.get("confidence"),
        "severity": prediction.get("severity"),
        "recommendation": scan_doc.get("recommendation"),
        "prevention_steps": prediction.get("prevention_steps", []),
        "latency_ms": scan_doc.get("latency_ms"),
        "image_metadata": scan_doc.get("image_metadata", {}),
        "timestamp": timestamp,
    }


@smart_bp.route("/api/system/metrics", methods=["GET"])
def get_system_metrics():
    start = perf_counter()
    backend_latency_ms = round((perf_counter() - start) * 1000 + 118.6, 2)

    # Simulated MVP health data. Upgrade path: replace with real DB ping,
    # service telemetry, model registry status, and IoT ingestion freshness.
    return _json_response(
        {
            "api_status": "Online",
            "database_status": "Connected",
            "backend_latency_ms": backend_latency_ms,
            "target_latency_ms": 500,
            "ai_model_mode": "simulated_ai",
            "sensor_data_freshness_seconds": 18,
            "uptime_percentage_target": "99.9%",
            "timestamp": _timestamp(),
        }
    )


@smart_bp.route("/api/sensors/latest", methods=["GET"])
def get_latest_sensor_data():
    # Simulated IoT reading for AT3 MVP demos. Upgrade path: read latest
    # sensor telemetry from a device gateway, message queue, or time-series DB.
    return _json_response(
        {
            "farm_id": "demo-farm-001",
            "temperature_c": 23.5,
            "humidity_percent": 64,
            "soil_moisture_percent": 58.4,
            "light_lux": 42000,
            "source": "simulated_sensor_network",
            "status": "fresh",
            "timestamp": _timestamp(),
        }
    )


@smart_bp.route("/api/ai/detect", methods=["POST"])
def detect_crop_disease():
    # Simulated AI response for AT3 MVP. Upgrade path: replace this with
    # image upload handling and a real CNN inference service.
    return _json_response(
        {
            "mode": "simulated_ai",
            "model_type": "crop_leaf_disease_classifier",
            "cnn_architecture_plan": {
                "baseline": "Custom lightweight CNN",
                "comparison_models": ["MobileNetV2", "ResNet50", "EfficientNetB0"],
                "chosen_for_future_upgrade": "MobileNetV2",
                "reason": "Good balance of accuracy, speed, and mobile/cloud deployment size.",
            },
            "prediction": {
                "label": "Healthy Leaf",
                "confidence": 0.91,
                "recommendation": "Continue normal monitoring",
            },
            "latency_requirement_ms": 500,
            "timestamp": _timestamp(),
        }
    )


@smart_bp.route("/api/ai/crop-scan", methods=["POST"])
@jwt_required
def crop_health_scan(current_user):
    start = perf_counter()
    uploaded_image = request.files.get("image")
    if uploaded_image is None or not uploaded_image.filename:
        return _json_response({"message": "Image file is required."}, 400)

    filename = secure_filename(uploaded_image.filename)
    if not _allowed_scan_file(filename):
        return _json_response(
            {"message": "Invalid image type. Please upload a jpg, jpeg, png, or webp file."},
            400,
        )

    image_bytes = uploaded_image.read()
    if len(image_bytes) > MAX_SCAN_BYTES:
        return _json_response({"message": "Image file is too large. Maximum size is 5 MB."}, 400)

    farm_id = (request.form.get("farm_id") or "").strip()
    crop_type = (request.form.get("crop_type") or "").strip()
    if farm_id:
        _, error_response = _get_authorised_farm(farm_id, current_user)
        if error_response:
            return error_response

    metadata = _image_metadata(uploaded_image, image_bytes)
    prediction = _simulated_crop_prediction(metadata["filename"], crop_type)
    created_at = datetime.now(timezone.utc)
    latency_ms = round((perf_counter() - start) * 1000, 2)
    scan_doc = {
        "user_id": _current_user_id(current_user),
        "username": current_user.get("username"),
        "farm_id": farm_id or None,
        "crop_type": crop_type or None,
        "image_metadata": metadata,
        "prediction": prediction,
        "recommendation": prediction["recommendation"],
        "model_mode": "simulated_ai",
        "latency_ms": latency_ms,
        "created_at": created_at,
    }

    insert_result = config.get_db().ai_scans.insert_one(scan_doc)
    scan_doc["_id"] = insert_result.inserted_id

    return _json_response(_scan_response(scan_doc), 201)


@smart_bp.route("/api/ai/scans", methods=["GET"])
@jwt_required
def list_crop_scans(current_user):
    scans = list(
        config.get_db()
        .ai_scans.find({"user_id": _current_user_id(current_user)})
        .sort("created_at", -1)
        .limit(50)
    )

    return _json_response(
        {
            "count": len(scans),
            "scans": [_scan_response(scan) for scan in scans],
        }
    )


@smart_bp.route("/api/farms/<farm_id>/ai-scans", methods=["GET"])
@jwt_required
def list_farm_crop_scans(current_user, farm_id):
    _, error_response = _get_authorised_farm(farm_id, current_user)
    if error_response:
        return error_response

    scans = list(
        config.get_db()
        .ai_scans.find({"farm_id": farm_id})
        .sort("created_at", -1)
        .limit(50)
    )

    return _json_response(
        {
            "farm_id": farm_id,
            "count": len(scans),
            "scans": [_scan_response(scan) for scan in scans],
        }
    )


@smart_bp.route("/api/irrigation/decision", methods=["GET"])
def get_irrigation_decision():
    soil_moisture_percent = 58.4
    temperature_c = 23.5

    # Rule-based MVP decision. Upgrade path: combine live soil data,
    # evapotranspiration, weather forecasts, and crop stage rules.
    return _json_response(
        {
            "soil_moisture_percent": soil_moisture_percent,
            "temperature_c": temperature_c,
            "decision": "No irrigation required",
            "recommended_action": "Maintain normal monitoring schedule",
            "priority": "low",
            "rule_used": "If soil moisture is between 45% and 70%, irrigation is not required.",
            "timestamp": _timestamp(),
        }
    )


@smart_bp.route("/api/weather/alert", methods=["GET"])
def get_weather_alert():
    # Simulated weather alert. Upgrade path: connect to a weather provider API
    # and generate farm-specific warnings from forecast thresholds.
    return _json_response(
        {
            "location": "Demo Farm Region",
            "alert_level": "Medium",
            "message": "High temperature expected later today",
            "recommended_action": "Monitor soil moisture more frequently",
            "mode": "simulated_weather_alert",
            "timestamp": _timestamp(),
        }
    )


@smart_bp.route("/api/sensors/failover-test", methods=["GET"])
def get_sensor_failover_test():
    # Simulated failover/interpolation response. Upgrade path: calculate this
    # from recent valid sensor windows and neighbouring sensor readings.
    return _json_response(
        {
            "sensor_status": "offline_simulation",
            "failover_mode": "interpolated_reading",
            "logic": "Used the last valid soil moisture reading and nearby sensor trend to estimate current value.",
            "last_valid_reading": {
                "sensor_id": "SM-204",
                "soil_moisture_percent": 57.8,
                "timestamp": "2026-05-25T08:10:00+00:00",
            },
            "interpolated_reading": {
                "sensor_id": "SM-204",
                "soil_moisture_percent": 58.4,
                "method": "linear_interpolation",
                "timestamp": _timestamp(),
            },
            "confidence": "Medium",
            "alert": "Sensor offline. Showing interpolated value until live readings resume.",
        }
    )
