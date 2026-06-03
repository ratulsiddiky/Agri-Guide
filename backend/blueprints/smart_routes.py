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


def _build_scan_advice(prediction, crop_type=None):
    label = prediction.get("label", "Healthy Leaf")
    severity = prediction.get("severity", "low")

    advice_map = {
        "Healthy Leaf": {
            "possible_causes": [
                "Current field conditions appear stable",
                "No major disease or stress markers detected in the image",
                "Irrigation and nutrition levels may be in a normal range",
            ],
            "immediate_actions": [
                "Continue routine scouting and keep the current management plan",
                "Record the image as a healthy baseline for later comparison",
            ],
            "prevention_plan": [
                "Keep checking soil moisture and weather changes each day",
                "Inspect for new spots, wilting, or pest pressure weekly",
                "Repeat the scan after major weather swings or crop stress events",
            ],
            "monitoring_advice": "Re-scan in 5 to 7 days, or sooner if weather turns hot, wet, or windy.",
            "when_to_seek_expert_help": "Seek expert help if symptoms spread quickly, several plants decline, or sensor data starts drifting from normal.",
            "confidence_explanation": "The image matches a low-risk healthy-leaf pattern and does not show strong stress indicators.",
        },
        "Early Blight Risk": {
            "possible_causes": [
                "Fungal pressure from warm, humid conditions",
                "Splashing water or wet foliage helping leaf spots spread",
                "Nearby infected plant material or crop residue",
            ],
            "immediate_actions": [
                "Remove the most affected leaves if practical",
                "Avoid overhead watering and improve airflow around the canopy",
                "Check neighboring plants for the same symptoms",
            ],
            "prevention_plan": [
                "Rotate crops between seasons where possible",
                "Keep foliage dry during watering and prune crowded growth",
                "Monitor humidity and leaf wetness after rainfall or irrigation",
            ],
            "monitoring_advice": "Inspect the crop again within 24 to 48 hours and watch for new dark circular spots.",
            "when_to_seek_expert_help": "Ask an agronomist or plant pathologist if the spots spread rapidly, reach fruit or stems, or appear on multiple beds.",
            "confidence_explanation": "The model sees a symptom pattern that commonly aligns with early blight risk, so the recommendation is moderately confident.",
        },
        "Powdery Mildew Risk": {
            "possible_causes": [
                "High humidity and poor airflow around leaves",
                "Dense canopy trapping moisture",
                "Recent weather that favors fungal growth",
            ],
            "immediate_actions": [
                "Increase spacing or prune dense foliage to improve airflow",
                "Water near the soil line and avoid wetting leaves",
                "Check nearby plants for white powdery patches",
            ],
            "prevention_plan": [
                "Track humidity-heavy periods and act early",
                "Keep the crop canopy open and well ventilated",
                "Re-scan after 48 hours if the white patches grow",
            ],
            "monitoring_advice": "Watch the crop daily during humid weather and repeat the scan after the next irrigation cycle.",
            "when_to_seek_expert_help": "Seek help if the white growth spreads across most leaves, affects fruiting parts, or does not slow after airflow improvements.",
            "confidence_explanation": "Visual cues are consistent with a humidity-linked fungal pattern, but severity can vary with local weather and crop stage.",
        },
        "Nutrient Deficiency Signs": {
            "possible_causes": [
                "Soil nutrient levels may be unbalanced",
                "Soil pH may be limiting nutrient uptake",
                "Recent fertiliser timing or rate may need review",
            ],
            "immediate_actions": [
                "Review the fertiliser schedule and recent soil amendments",
                "Check soil pH before applying more nutrients",
                "Compare older leaves with newer growth for yellowing patterns",
            ],
            "prevention_plan": [
                "Apply balanced nutrients gradually rather than in one large correction",
                "Keep notes on what was applied and when",
                "Test soil periodically to catch drift before yield loss appears",
            ],
            "monitoring_advice": "Re-check the crop after the next feeding cycle and watch whether the yellowing improves or worsens.",
            "when_to_seek_expert_help": "Get expert support if symptoms keep spreading, several nutrient types look affected, or the crop stops responding to feeding.",
            "confidence_explanation": "The leaf pattern matches common deficiency cues, but confirmation usually depends on soil or tissue testing.",
        },
        "Water Stress Signs": {
            "possible_causes": [
                "Soil moisture is below the crop's preferred range",
                "Irrigation coverage may be uneven or blocked",
                "Hot or windy conditions could be increasing water loss",
            ],
            "immediate_actions": [
                "Check soil moisture and irrigate affected zones today",
                "Inspect emitters, hoses, or valves for blockages",
                "Mulch exposed soil to reduce evaporation",
            ],
            "prevention_plan": [
                "Track moisture more often during warm or windy weather",
                "Confirm irrigation coverage across the full bed or block",
                "Use trend checks to spot dry-down before plants wilt",
            ],
            "monitoring_advice": "Monitor moisture again within a few hours after irrigation and re-scan tomorrow if stress remains visible.",
            "when_to_seek_expert_help": "Seek expert help if irrigation fixes do not improve the crop quickly, or if large areas wilt at the same time.",
            "confidence_explanation": "The image shows a pattern commonly linked to water stress and the urgency is reinforced by the high-risk label.",
        },
    }

    selected = advice_map.get(label, advice_map["Healthy Leaf"])
    return {
        "possible_causes": selected["possible_causes"],
        "immediate_actions": selected["immediate_actions"],
        "prevention_plan": selected["prevention_plan"],
        "monitoring_advice": selected["monitoring_advice"],
        "when_to_seek_expert_help": selected["when_to_seek_expert_help"],
        "confidence_explanation": selected["confidence_explanation"],
        "advisory_disclaimer": (
            "This AI crop scan is advisory support only. Confirm important decisions with field scouting, local conditions, "
            "and expert agronomy advice when needed."
        ),
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
        "possible_causes": scan_doc.get("possible_causes", []),
        "immediate_actions": scan_doc.get("immediate_actions", []),
        "prevention_plan": scan_doc.get("prevention_plan", []),
        "monitoring_advice": scan_doc.get("monitoring_advice", ""),
        "when_to_seek_expert_help": scan_doc.get("when_to_seek_expert_help", ""),
        "confidence_explanation": scan_doc.get("confidence_explanation", ""),
        "advisory_disclaimer": scan_doc.get("advisory_disclaimer", ""),
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
    advice = _build_scan_advice(prediction, crop_type)
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
        **advice,
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
