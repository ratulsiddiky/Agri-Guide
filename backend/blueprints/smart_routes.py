from datetime import datetime, timezone
from time import perf_counter

from flask import Blueprint, jsonify, make_response


smart_bp = Blueprint("smart_bp", __name__)


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _json_response(payload, status_code=200):
    return make_response(jsonify(payload), status_code)


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
