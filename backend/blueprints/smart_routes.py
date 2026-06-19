from datetime import datetime, timezone
from io import BytesIO
import os
import random
from time import perf_counter

from bson import ObjectId
from flask import Blueprint, jsonify, make_response, request
from werkzeug.utils import secure_filename

import config
from decorators import jwt_required
from services import crop_disease_model

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    Image = None

try:
    from azure.core.exceptions import AzureError, ResourceExistsError, ResourceNotFoundError
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ImportError:  # pragma: no cover - optional dependency
    class AzureError(Exception):
        pass

    class ResourceExistsError(AzureError):
        pass

    class ResourceNotFoundError(AzureError):
        pass

    BlobServiceClient = None
    ContentSettings = None


smart_bp = Blueprint("smart_bp", __name__)
ALLOWED_SCAN_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_SCAN_BYTES = 5 * 1024 * 1024
ADVISORY_DISCLAIMER = (
    "This AI crop scan is advisory support only. Confirm important decisions with field scouting, local conditions, "
    "and expert agronomy advice when needed."
)

CROP_DIAGNOSIS_KNOWLEDGE_BASE = {
    "healthy": {
        "label": "Healthy Leaf",
        "keywords": ("healthy", "fresh", "normal", "clean", "good"),
        "confidence_range": (0.82, 0.94),
        "severity": "low",
        "recommendation": "Crop appears healthy. Continue routine monitoring and keep sensor checks active.",
        "explanation": "The leaf image does not show strong disease, pest, water stress, or nutrient imbalance cues.",
        "severity_explanation": "Low severity means no urgent intervention is suggested from this image alone.",
        "likely_causes": [
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
        "prevention_steps": [
            "Inspect leaves weekly for new spots or discoloration.",
            "Keep irrigation within the recommended soil moisture range.",
            "Record follow-up images if weather becomes humid or unusually hot.",
        ],
        "monitoring_advice": "Re-scan in 5 to 7 days, or sooner if weather turns hot, wet, or windy.",
        "when_to_seek_expert_help": "Seek expert help if symptoms spread quickly, several plants decline, or sensor data starts drifting from normal.",
        "confidence_explanation": "The image matches a low-risk healthy-leaf pattern and does not show strong stress indicators.",
    },
    "leaf_blight": {
        "label": "Leaf Blight Risk",
        "keywords": ("blight", "spot", "spots", "lesion", "tomato"),
        "confidence_range": (0.74, 0.88),
        "severity": "medium",
        "recommendation": "Remove affected leaves if visible and improve airflow around plants.",
        "explanation": "Dark spots, lesions, or blight-like naming cues suggest a possible fungal leaf disease risk.",
        "severity_explanation": "Medium severity means the crop should be inspected soon before symptoms spread across the canopy.",
        "likely_causes": [
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
        "prevention_steps": [
            "Avoid overhead watering where possible.",
            "Rotate susceptible crops between seasons.",
            "Check nearby plants for dark circular leaf spots.",
        ],
        "monitoring_advice": "Inspect the crop again within 24 to 48 hours and watch for new dark circular spots.",
        "when_to_seek_expert_help": "Ask an agronomist or plant pathologist if the spots spread rapidly, reach fruit or stems, or appear on multiple beds.",
        "confidence_explanation": "The symptom pattern commonly aligns with leaf blight risk, so the recommendation is moderately confident.",
    },
    "powdery_mildew": {
        "label": "Powdery Mildew Risk",
        "keywords": ("mildew", "powder", "powdery", "white"),
        "confidence_range": (0.73, 0.87),
        "severity": "medium",
        "recommendation": "Increase spacing or airflow and monitor humidity-heavy periods closely.",
        "explanation": "White or powdery leaf cues are consistent with a humidity-linked fungal pressure pattern.",
        "severity_explanation": "Medium severity means quick airflow and moisture management can help reduce spread.",
        "likely_causes": [
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
        "prevention_steps": [
            "Prune dense foliage to reduce trapped humidity.",
            "Water near the soil line early in the day.",
            "Re-scan leaves after 48 hours if white patches spread.",
        ],
        "monitoring_advice": "Watch the crop daily during humid weather and repeat the scan after the next irrigation cycle.",
        "when_to_seek_expert_help": "Seek help if the white growth spreads across most leaves, affects fruiting parts, or does not slow after airflow improvements.",
        "confidence_explanation": "Visual cues are consistent with a humidity-linked fungal pattern, but severity can vary with local weather and crop stage.",
    },
    "rust": {
        "label": "Rust Disease Risk",
        "keywords": ("rust", "orange", "brown", "pustule", "rusty"),
        "confidence_range": (0.72, 0.86),
        "severity": "medium",
        "recommendation": "Inspect both sides of leaves and remove heavily affected foliage where practical.",
        "explanation": "Rust-like orange or brown speckling can indicate fungal spores developing on leaf surfaces.",
        "severity_explanation": "Medium severity means the issue can spread under suitable weather and should be checked promptly.",
        "likely_causes": [
            "Rust fungus favored by leaf wetness and mild temperatures",
            "Spores moving from nearby infected plants",
            "Dense planting that keeps foliage damp",
        ],
        "immediate_actions": [
            "Inspect the underside of leaves for orange or brown pustules",
            "Remove severely affected leaves and avoid shaking spores onto healthy plants",
            "Reduce leaf wetness by watering at soil level",
        ],
        "prevention_plan": [
            "Improve air movement through spacing and pruning",
            "Avoid working through wet crops when spores can spread",
            "Rotate or separate susceptible crops where possible",
        ],
        "prevention_steps": [
            "Check leaf undersides weekly for orange or brown marks.",
            "Keep foliage dry during irrigation.",
            "Remove crop debris that may carry spores into the next season.",
        ],
        "monitoring_advice": "Re-check in 24 to 48 hours and note whether orange or brown marks are increasing.",
        "when_to_seek_expert_help": "Seek expert advice if rust marks spread across multiple plants or appear after repeated removal.",
        "confidence_explanation": "The classification is based on rust-colored symptom cues, but field confirmation should check leaf undersides.",
    },
    "nutrient_deficiency": {
        "label": "Nutrient Deficiency Signs",
        "keywords": ("yellow", "nutrient", "pale", "deficiency", "chlorosis"),
        "confidence_range": (0.7, 0.85),
        "severity": "medium",
        "recommendation": "Review recent fertiliser schedule and consider a soil nutrient test.",
        "explanation": "Yellowing or pale leaf cues can indicate nutrient imbalance, pH issues, or reduced uptake.",
        "severity_explanation": "Medium severity means yield may be affected if the underlying nutrient issue continues.",
        "likely_causes": [
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
        "prevention_steps": [
            "Check soil pH before adding fertiliser.",
            "Compare older and newer leaves for yellowing patterns.",
            "Apply balanced nutrients gradually to avoid over-correction.",
        ],
        "monitoring_advice": "Re-check the crop after the next feeding cycle and watch whether the yellowing improves or worsens.",
        "when_to_seek_expert_help": "Get expert support if symptoms keep spreading, several nutrient types look affected, or the crop stops responding to feeding.",
        "confidence_explanation": "The leaf pattern matches common deficiency cues, but confirmation usually depends on soil or tissue testing.",
    },
    "pest_damage": {
        "label": "Pest Damage Signs",
        "keywords": ("pest", "insect", "bite", "holes", "chewed", "aphid", "caterpillar"),
        "confidence_range": (0.71, 0.86),
        "severity": "medium",
        "recommendation": "Inspect leaves closely for insects, eggs, webbing, or fresh feeding damage.",
        "explanation": "Chewing, holes, or insect-related cues suggest pest activity may be affecting the crop.",
        "severity_explanation": "Medium severity means damage should be checked soon because pest pressure can increase quickly.",
        "likely_causes": [
            "Chewing or sap-feeding insects present on the crop",
            "Eggs or larvae developing on leaf undersides",
            "Nearby weeds or crop residue sheltering pests",
        ],
        "immediate_actions": [
            "Inspect leaf undersides and growing tips for pests",
            "Remove heavily damaged leaves if practical",
            "Use sticky traps or manual counts to estimate pressure",
        ],
        "prevention_plan": [
            "Remove nearby weeds that host pests",
            "Encourage beneficial insects where suitable",
            "Scout regularly during warm periods when pests reproduce faster",
        ],
        "prevention_steps": [
            "Check leaf undersides for insects or eggs.",
            "Record pest counts before choosing controls.",
            "Keep field edges and weeds managed.",
        ],
        "monitoring_advice": "Scout again within 24 hours and compare damage levels across several plants.",
        "when_to_seek_expert_help": "Seek expert help if pest numbers rise quickly, damage reaches new growth, or organic controls are not working.",
        "confidence_explanation": "The image or filename cues match common pest damage patterns, but scouting is needed to identify the pest species.",
    },
    "water_stress": {
        "label": "Water Stress Signs",
        "keywords": ("dry", "wilt", "water", "stress", "drought", "droop"),
        "confidence_range": (0.76, 0.9),
        "severity": "high",
        "recommendation": "Check soil moisture and irrigation coverage for this crop zone today.",
        "explanation": "Wilting, dry, or stress cues suggest the plant may not be receiving or retaining enough water.",
        "severity_explanation": "High severity means the crop should be checked today because water stress can cause rapid decline.",
        "likely_causes": [
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
        "prevention_steps": [
            "Inspect emitters or irrigation lines for blockages.",
            "Mulch exposed soil to reduce evaporation.",
            "Increase monitoring during warm or windy weather.",
        ],
        "monitoring_advice": "Monitor moisture again within a few hours after irrigation and re-scan tomorrow if stress remains visible.",
        "when_to_seek_expert_help": "Seek expert help if irrigation fixes do not improve the crop quickly, or if large areas wilt at the same time.",
        "confidence_explanation": "The image shows a pattern commonly linked to water stress and the urgency is reinforced by the high-risk label.",
    },
}


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


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _azure_scan_storage_config():
    if not _env_bool("AI_SCAN_IMAGE_STORAGE_ENABLED", default=False):
        return None

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "crop-scans").strip()
    if not connection_string or not container_name or BlobServiceClient is None:
        return None

    return {
        "connection_string": connection_string,
        "container_name": container_name,
    }


def _blob_name_segment(value, fallback):
    cleaned = secure_filename(str(value or "").strip())
    return cleaned or fallback


def _build_scan_blob_name(scan_doc):
    user_id = _blob_name_segment(scan_doc.get("user_id"), "unknown-user")
    farm_id = _blob_name_segment(scan_doc.get("farm_id"), "none")
    scan_id = _blob_name_segment(scan_doc.get("_id"), "unknown-scan")
    filename = _blob_name_segment(
        scan_doc.get("image_metadata", {}).get("filename"),
        "crop-image",
    )
    return f"{user_id}/{farm_id}/{scan_id}/{filename}"


def _get_scan_container_client(ensure_exists=False):
    storage_config = _azure_scan_storage_config()
    if storage_config is None:
        return None

    service_client = BlobServiceClient.from_connection_string(
        storage_config["connection_string"]
    )
    container_client = service_client.get_container_client(storage_config["container_name"])
    if ensure_exists:
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass
    return container_client


def _upload_scan_image_to_blob(scan_doc, image_bytes):
    try:
        container_client = _get_scan_container_client(ensure_exists=True)
        if container_client is None:
            return None

        blob_name = _build_scan_blob_name(scan_doc)
        content_type = scan_doc.get("image_metadata", {}).get("content_type")
        upload_kwargs = {"overwrite": True}
        if ContentSettings is not None and content_type:
            upload_kwargs["content_settings"] = ContentSettings(content_type=content_type)

        container_client.upload_blob(name=blob_name, data=image_bytes, **upload_kwargs)
        return {
            "image_storage_provider": "azure_blob",
            "image_blob_name": blob_name,
            "image_content_type": content_type,
            "image_size_bytes": len(image_bytes),
            "image_original_filename": scan_doc.get("image_metadata", {}).get("filename"),
        }
    except Exception:
        return None


def _download_scan_image_from_blob(scan_doc):
    container_client = _get_scan_container_client()
    if container_client is None:
        return None

    downloader = container_client.download_blob(scan_doc["image_blob_name"])
    return downloader.readall()


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
    diagnosis_key = next(
        (
            key
            for key, entry in CROP_DIAGNOSIS_KNOWLEDGE_BASE.items()
            if any(token in haystack for token in entry["keywords"])
        ),
        None,
    )
    if diagnosis_key is None:
        diagnosis_key = random.choice(list(CROP_DIAGNOSIS_KNOWLEDGE_BASE.keys()))

    selected = CROP_DIAGNOSIS_KNOWLEDGE_BASE[diagnosis_key]
    low, high = selected["confidence_range"]

    return {
        "diagnosis_key": diagnosis_key,
        "label": selected["label"],
        "confidence": round(random.uniform(low, high), 2),
        "severity": selected["severity"],
        "recommendation": selected["recommendation"],
        "prevention_steps": selected["prevention_steps"],
    }


def _build_scan_advice(prediction, crop_type=None):
    diagnosis_key = prediction.get("diagnosis_key", "healthy")
    selected = CROP_DIAGNOSIS_KNOWLEDGE_BASE.get(
        diagnosis_key,
        CROP_DIAGNOSIS_KNOWLEDGE_BASE["healthy"],
    )
    return {
        "explanation": selected["explanation"],
        "severity_explanation": selected["severity_explanation"],
        "likely_causes": selected["likely_causes"],
        "possible_causes": selected["likely_causes"],
        "immediate_actions": selected["immediate_actions"],
        "prevention_plan": selected["prevention_plan"],
        "monitoring_advice": selected["monitoring_advice"],
        "when_to_seek_expert_help": selected["when_to_seek_expert_help"],
        "confidence_explanation": selected["confidence_explanation"],
        "advisory_disclaimer": ADVISORY_DISCLAIMER,
    }


def _crop_scan_ai_result(image_bytes, filename, crop_type):
    if os.getenv("AI_PROVIDER", "simulated_ai").strip().lower() == "custom_model":
        custom_result = crop_disease_model.predict_crop_disease(image_bytes)
        if custom_result:
            return custom_result

    prediction = _simulated_crop_prediction(filename, crop_type)
    return {
        "prediction": prediction,
        "advice": _build_scan_advice(prediction, crop_type),
        "metadata": {
            "model": "Simulated crop diagnosis knowledge base",
            "provider": "simulated_ai",
            "ai_mode": "simulated_ai",
            "model_mode": "simulated_ai",
        },
    }


def _scan_response(scan_doc):
    prediction = scan_doc.get("prediction", {})
    created_at = scan_doc.get("created_at") or datetime.now(timezone.utc)
    timestamp = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
    farm_name = None
    farm_id = scan_doc.get("farm_id")
    likely_causes = scan_doc.get("likely_causes") or scan_doc.get("possible_causes", [])
    scan_id = str(scan_doc["_id"])
    has_image = bool(
        scan_doc.get("image_storage_provider") == "azure_blob"
        and scan_doc.get("image_blob_name")
    )

    if farm_id and ObjectId.is_valid(farm_id):
        farm = config.get_db().farms.find_one({"_id": ObjectId(farm_id)}, {"farm_name": 1})
        if farm:
            farm_name = farm.get("farm_name")

    recommendation = scan_doc.get("recommendation")
    prevention_steps = prediction.get("prevention_steps", [])
    immediate_actions = scan_doc.get("immediate_actions", [])
    prevention_plan = scan_doc.get("prevention_plan", [])
    advisory_disclaimer = scan_doc.get("advisory_disclaimer", "")
    model_mode = scan_doc.get("model_mode", "simulated_ai")
    model = scan_doc.get("model") or (
        "Custom crop disease classifier"
        if model_mode == "custom_trained_model"
        else "Simulated crop diagnosis knowledge base"
    )
    provider = scan_doc.get("provider") or model_mode
    ai_mode = scan_doc.get("ai_mode") or model_mode

    response = {
        "scan_id": scan_id,
        "farm_id": farm_id,
        "farm_name": scan_doc.get("farm_name") or farm_name,
        "crop_type": scan_doc.get("crop_type"),
        "model_mode": model_mode,
        "model_type": "crop_leaf_health_classifier",
        "future_upgrade_model": "MobileNetV2 transfer learning CNN",
        "label": prediction.get("label"),
        "confidence": prediction.get("confidence"),
        "severity": prediction.get("severity"),
        "recommendation": recommendation,
        "prevention_steps": prevention_steps,
        "explanation": scan_doc.get("explanation", ""),
        "severity_explanation": scan_doc.get("severity_explanation", ""),
        "likely_causes": likely_causes,
        "possible_causes": scan_doc.get("possible_causes") or likely_causes,
        "immediate_actions": immediate_actions,
        "prevention_plan": prevention_plan,
        "monitoring_advice": scan_doc.get("monitoring_advice", ""),
        "when_to_seek_expert_help": scan_doc.get("when_to_seek_expert_help", ""),
        "confidence_explanation": scan_doc.get("confidence_explanation", ""),
        "advisory_disclaimer": advisory_disclaimer,
        "diagnosis": prediction.get("label"),
        "disease_risk": scan_doc.get("disease_risk") or prediction.get("severity"),
        "summary": scan_doc.get("explanation", ""),
        "recommendations": [recommendation] if recommendation else [],
        "urgent_actions": immediate_actions,
        "prevention_tips": prevention_plan or prevention_steps,
        "disclaimer": advisory_disclaimer,
        "model": model,
        "provider": provider,
        "ai_mode": ai_mode,
        "latency_ms": scan_doc.get("latency_ms"),
        "image_metadata": scan_doc.get("image_metadata", {}),
        "has_image": has_image,
        "created_at": timestamp,
        "timestamp": timestamp,
    }
    if has_image:
        response["image_endpoint"] = f"/api/ai/scans/{scan_id}/image"
    return response


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
    ai_result = _crop_scan_ai_result(image_bytes, metadata["filename"], crop_type)
    prediction = ai_result["prediction"]
    advice = ai_result["advice"]
    ai_metadata = ai_result["metadata"]
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
        **ai_metadata,
        "latency_ms": latency_ms,
        "created_at": created_at,
    }

    insert_result = config.get_db().ai_scans.insert_one(scan_doc)
    scan_doc["_id"] = insert_result.inserted_id
    image_storage_fields = _upload_scan_image_to_blob(scan_doc, image_bytes)
    if image_storage_fields:
        config.get_db().ai_scans.update_one(
            {"_id": scan_doc["_id"]},
            {"$set": image_storage_fields},
        )
        scan_doc.update(image_storage_fields)

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


@smart_bp.route("/api/ai/scans/<scan_id>", methods=["GET"])
@jwt_required
def get_crop_scan(current_user, scan_id):
    if not ObjectId.is_valid(scan_id):
        return _json_response({"message": "Scan not found."}, 404)

    scan = config.get_db().ai_scans.find_one({"_id": ObjectId(scan_id)})
    if scan is None:
        return _json_response({"message": "Scan not found."}, 404)

    is_owner = scan.get("user_id") == _current_user_id(current_user)
    if not (is_owner or _is_admin(current_user)):
        return _json_response({"message": "You do not have permission to view this scan."}, 403)

    return _json_response(_scan_response(scan))


@smart_bp.route("/api/ai/scans/<scan_id>/image", methods=["GET"])
@jwt_required
def get_crop_scan_image(current_user, scan_id):
    if not ObjectId.is_valid(scan_id):
        return _json_response({"message": "Scan image not found."}, 404)

    scan = config.get_db().ai_scans.find_one({"_id": ObjectId(scan_id)})
    if scan is None:
        return _json_response({"message": "Scan image not found."}, 404)

    is_owner = scan.get("user_id") == _current_user_id(current_user)
    if not (is_owner or _is_admin(current_user)):
        return _json_response({"message": "You do not have permission to view this scan image."}, 403)

    if scan.get("image_storage_provider") != "azure_blob" or not scan.get("image_blob_name"):
        return _json_response({"message": "Image preview is not stored for this scan."}, 404)

    try:
        image_bytes = _download_scan_image_from_blob(scan)
    except ResourceNotFoundError:
        return _json_response({"message": "Image preview is not stored for this scan."}, 404)
    except AzureError:
        return _json_response({"message": "Unable to load scan image preview."}, 502)
    except Exception:
        return _json_response({"message": "Unable to load scan image preview."}, 502)

    if image_bytes is None:
        return _json_response({"message": "Unable to load scan image preview."}, 502)

    content_type = scan.get("image_content_type") or "application/octet-stream"
    filename = secure_filename(scan.get("image_original_filename") or "crop-scan-image")
    response = make_response(image_bytes)
    response.headers["Content-Type"] = content_type
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


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
