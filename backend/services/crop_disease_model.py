from io import BytesIO
import json
import logging
import os
from pathlib import Path


LOGGER = logging.getLogger(__name__)

CUSTOM_MODEL_NAME = "Custom crop disease classifier"
CUSTOM_PROVIDER = "Agri Guide trained model"
CUSTOM_MODE = "custom_trained_model"
DISCLAIMER = "AI-assisted diagnosis. Please verify serious crop disease decisions with an agricultural expert."

EXPECTED_LABELS = [
    "Pepper__bell___Bacterial_spot",
    "Pepper__bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Tomato_Bacterial_spot",
    "Tomato_Early_blight",
    "Tomato_Late_blight",
    "Tomato_healthy",
]

LABEL_ADVICE = {
    "Pepper__bell___Bacterial_spot": {
        "label": "Pepper bell bacterial spot",
        "severity": "medium",
        "risk": "medium",
        "recommendation": "Remove badly affected leaves, avoid overhead watering, and improve spacing around pepper plants.",
        "summary": "The image is most consistent with bacterial spot on bell pepper foliage.",
        "likely_causes": [
            "Bacterial infection favored by wet leaves and warm conditions",
            "Splashing water moving bacteria between leaves",
            "Infected seed, seedlings, or crop residue",
        ],
        "urgent_actions": [
            "Remove heavily spotted leaves where practical",
            "Avoid handling plants while foliage is wet",
            "Check nearby pepper plants for matching spots",
        ],
        "prevention_tips": [
            "Water at soil level instead of overhead",
            "Sanitize tools between affected and healthy plants",
            "Rotate away from peppers and tomatoes in the next season where possible",
        ],
        "monitoring": "Re-check affected plants within 48 hours and watch whether spots spread after rain or irrigation.",
    },
    "Pepper__bell___healthy": {
        "label": "Healthy pepper bell leaf",
        "severity": "low",
        "risk": "low",
        "recommendation": "Pepper foliage appears healthy. Continue routine scouting and irrigation checks.",
        "summary": "The model did not detect a strong disease pattern on this pepper leaf.",
        "likely_causes": [
            "Current pepper foliage appears stable",
            "No major disease symptoms detected in the image",
        ],
        "urgent_actions": [
            "Keep this image as a healthy comparison baseline",
            "Continue normal crop monitoring",
        ],
        "prevention_tips": [
            "Inspect leaves weekly for new spots or yellowing",
            "Keep foliage dry during irrigation",
            "Maintain airflow around the canopy",
        ],
        "monitoring": "Re-scan in 5 to 7 days or sooner if new spots, wilting, or yellowing appears.",
    },
    "Potato___Early_blight": {
        "label": "Potato early blight",
        "severity": "medium",
        "risk": "medium",
        "recommendation": "Remove infected lower leaves where practical and reduce leaf wetness around potato plants.",
        "summary": "The image is most consistent with potato early blight.",
        "likely_causes": [
            "Fungal pressure favored by warm, humid conditions",
            "Spores from infected potato residue or nearby plants",
            "Older lower leaves staying wet for long periods",
        ],
        "urgent_actions": [
            "Inspect lower leaves for concentric brown lesions",
            "Remove badly affected leaves if disease is limited",
            "Avoid overhead irrigation",
        ],
        "prevention_tips": [
            "Rotate potatoes away from the same bed in future seasons",
            "Remove crop debris after harvest",
            "Keep plants well nourished to reduce stress",
        ],
        "monitoring": "Scout again in 24 to 48 hours and compare whether lesions are increasing.",
    },
    "Potato___Late_blight": {
        "label": "Potato late blight",
        "severity": "high",
        "risk": "high",
        "recommendation": "Inspect the crop immediately and isolate or remove heavily affected foliage if late blight symptoms are confirmed.",
        "summary": "The image is most consistent with potato late blight, which can spread quickly in wet conditions.",
        "likely_causes": [
            "Late blight pathogen favored by cool, wet weather",
            "Spores moving from infected potatoes or volunteer plants",
            "Extended leaf wetness after rain or irrigation",
        ],
        "urgent_actions": [
            "Inspect nearby potato plants today",
            "Avoid moving through wet foliage",
            "Contact a local agricultural expert if symptoms are spreading",
        ],
        "prevention_tips": [
            "Destroy infected crop debris safely",
            "Avoid overhead watering and improve airflow",
            "Use certified disease-free seed potatoes",
        ],
        "monitoring": "Check daily during wet weather because late blight can move through a crop very quickly.",
    },
    "Potato___healthy": {
        "label": "Healthy potato leaf",
        "severity": "low",
        "risk": "low",
        "recommendation": "Potato foliage appears healthy. Continue routine scouting and moisture monitoring.",
        "summary": "The model did not detect a strong potato disease pattern.",
        "likely_causes": [
            "Current potato foliage appears stable",
            "No major blight symptoms detected in the image",
        ],
        "urgent_actions": [
            "Keep the current crop management plan",
            "Record this image as a healthy baseline",
        ],
        "prevention_tips": [
            "Scout lower leaves weekly",
            "Avoid prolonged leaf wetness",
            "Remove volunteer potato plants that can carry disease",
        ],
        "monitoring": "Re-scan in 5 to 7 days, or sooner after wet weather.",
    },
    "Tomato_Bacterial_spot": {
        "label": "Tomato bacterial spot",
        "severity": "medium",
        "risk": "medium",
        "recommendation": "Remove badly affected tomato leaves, avoid wet foliage, and sanitize tools after handling plants.",
        "summary": "The image is most consistent with bacterial spot on tomato foliage.",
        "likely_causes": [
            "Bacterial infection favored by warm, wet conditions",
            "Splashing water spreading bacteria between leaves",
            "Infected seedlings, seed, or nearby plant debris",
        ],
        "urgent_actions": [
            "Remove heavily spotted leaves where practical",
            "Avoid pruning or harvesting while leaves are wet",
            "Check nearby tomato plants for similar spots",
        ],
        "prevention_tips": [
            "Water at the soil line",
            "Increase spacing and airflow",
            "Rotate away from tomatoes and peppers where possible",
        ],
        "monitoring": "Re-check within 48 hours and watch for spread after rain or irrigation.",
    },
    "Tomato_Early_blight": {
        "label": "Tomato early blight",
        "severity": "medium",
        "risk": "medium",
        "recommendation": "Remove affected lower leaves, improve airflow, and keep tomato foliage as dry as possible.",
        "summary": "The image is most consistent with tomato early blight.",
        "likely_causes": [
            "Fungal spores favored by warm, humid conditions",
            "Splashing soil or infected residue contacting lower leaves",
            "Plant stress making older leaves more vulnerable",
        ],
        "urgent_actions": [
            "Inspect lower leaves for dark target-like spots",
            "Remove the most affected leaves if disease is limited",
            "Avoid overhead watering",
        ],
        "prevention_tips": [
            "Mulch soil to reduce splash-back",
            "Stake or prune plants for airflow",
            "Rotate tomatoes away from the same location next season",
        ],
        "monitoring": "Inspect again within 24 to 48 hours and watch whether spots move upward.",
    },
    "Tomato_Late_blight": {
        "label": "Tomato late blight",
        "severity": "high",
        "risk": "high",
        "recommendation": "Inspect tomatoes immediately and seek local expert guidance if symptoms are spreading.",
        "summary": "The image is most consistent with tomato late blight, a high-risk disease under wet conditions.",
        "likely_causes": [
            "Late blight pathogen favored by cool, wet weather",
            "Spores moving from infected tomato or potato plants",
            "Extended leaf wetness and dense canopy conditions",
        ],
        "urgent_actions": [
            "Inspect nearby tomato and potato plants today",
            "Avoid handling wet plants",
            "Remove and contain severely affected plant material if confirmed",
        ],
        "prevention_tips": [
            "Improve airflow and avoid overhead irrigation",
            "Remove infected debris safely",
            "Use resistant varieties where available",
        ],
        "monitoring": "Monitor daily in wet weather because late blight can spread rapidly.",
    },
    "Tomato_healthy": {
        "label": "Healthy tomato leaf",
        "severity": "low",
        "risk": "low",
        "recommendation": "Tomato foliage appears healthy. Continue normal scouting and moisture management.",
        "summary": "The model did not detect a strong tomato disease pattern.",
        "likely_causes": [
            "Current tomato foliage appears stable",
            "No major tomato leaf disease symptoms detected in the image",
        ],
        "urgent_actions": [
            "Continue routine scouting",
            "Keep this image as a healthy baseline",
        ],
        "prevention_tips": [
            "Keep tomato foliage dry during irrigation",
            "Prune crowded growth for airflow",
            "Inspect lower leaves weekly for spots",
        ],
        "monitoring": "Re-scan in 5 to 7 days or sooner if new leaf spots appear.",
    },
}

_MODEL = None
_LABELS = None
_RUNTIME = None


def _resolve_path(value):
    raw_path = Path(value)
    if raw_path.is_absolute():
        return raw_path

    backend_dir = Path(__file__).resolve().parents[1]
    repo_dir = backend_dir.parent
    candidates = [
        Path.cwd() / raw_path,
        repo_dir / raw_path,
        backend_dir / raw_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _confidence_threshold():
    try:
        return float(os.getenv("CROP_MODEL_CONFIDENCE_THRESHOLD", "0.60"))
    except ValueError:
        return 0.60


def _load_runtime():
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME

    try:
        import numpy as np
        from PIL import Image
        from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
        from tensorflow.keras.models import load_model
    except Exception as exc:
        LOGGER.warning("Custom crop model runtime unavailable; using simulated fallback: %s", exc)
        return None

    _RUNTIME = {
        "np": np,
        "Image": Image,
        "preprocess_input": preprocess_input,
        "load_model": load_model,
    }
    return _RUNTIME


def _load_labels(labels_path):
    with labels_path.open("r", encoding="utf-8") as labels_file:
        labels = json.load(labels_file)
    if not isinstance(labels, list) or not labels:
        raise ValueError("labels file must contain a non-empty list")
    if labels != EXPECTED_LABELS:
        LOGGER.warning("Custom crop model labels differ from expected class order.")
    return labels


def _load_model_and_labels():
    global _MODEL, _LABELS
    if _MODEL is not None and _LABELS is not None:
        return _MODEL, _LABELS

    runtime = _load_runtime()
    if runtime is None:
        return None, None

    model_path = _resolve_path(os.getenv("CROP_MODEL_PATH", "backend/ml_models/crop_disease_model.keras"))
    labels_path = _resolve_path(os.getenv("CROP_LABELS_PATH", "backend/ml_models/class_names.json"))

    if not model_path.exists() or not labels_path.exists():
        LOGGER.warning("Custom crop model artifacts unavailable; using simulated fallback.")
        return None, None

    try:
        _LABELS = _load_labels(labels_path)
        _MODEL = runtime["load_model"](str(model_path))
    except Exception as exc:
        LOGGER.warning("Custom crop model load failed; using simulated fallback: %s", exc)
        _MODEL = None
        _LABELS = None
        return None, None

    return _MODEL, _LABELS


def _uncertain_result(confidence):
    label = "Uncertain crop disease diagnosis"
    prediction = {
        "diagnosis_key": "custom_uncertain",
        "label": label,
        "confidence": confidence,
        "severity": "medium",
        "recommendation": "Retake the photo in brighter, even lighting with a single leaf in clear focus.",
        "prevention_steps": [
            "Use natural light or bright indirect light.",
            "Fill the frame with one leaf and avoid blurry images.",
            "Photograph both healthy and affected leaves for comparison.",
        ],
        "raw_label": None,
    }
    advice = {
        "explanation": "The trained model could not classify this image confidently enough for disease-specific advice.",
        "severity_explanation": "Medium severity means the crop should be checked again before making treatment decisions.",
        "likely_causes": [
            "Image may be blurry, too dark, too distant, or outside the supported crop classes",
            "Visible symptoms may not match the trained pepper, potato, or tomato classes confidently",
        ],
        "possible_causes": [
            "Image may be blurry, too dark, too distant, or outside the supported crop classes",
            "Visible symptoms may not match the trained pepper, potato, or tomato classes confidently",
        ],
        "immediate_actions": [
            "Retake the photo in better lighting",
            "Capture one leaf close up and in focus",
            "Ask an agricultural expert if symptoms are severe or spreading",
        ],
        "prevention_plan": prediction["prevention_steps"],
        "monitoring_advice": "Repeat the scan with a clearer photo before acting on a disease treatment plan.",
        "when_to_seek_expert_help": "Seek expert help if symptoms are spreading, affecting fruit or stems, or causing rapid plant decline.",
        "confidence_explanation": "Confidence was below the configured threshold, so the result is marked uncertain.",
        "advisory_disclaimer": DISCLAIMER,
    }
    return _pack_result(prediction, advice)


def _pack_result(prediction, advice):
    return {
        "prediction": prediction,
        "advice": advice,
        "metadata": {
            "model": CUSTOM_MODEL_NAME,
            "provider": CUSTOM_PROVIDER,
            "ai_mode": CUSTOM_MODE,
            "model_mode": CUSTOM_MODE,
        },
    }


def _result_for_label(raw_label, confidence):
    entry = LABEL_ADVICE.get(raw_label)
    if entry is None:
        return None

    prediction = {
        "diagnosis_key": raw_label,
        "label": entry["label"],
        "confidence": confidence,
        "severity": entry["severity"],
        "recommendation": entry["recommendation"],
        "prevention_steps": entry["prevention_tips"],
        "raw_label": raw_label,
    }
    advice = {
        "explanation": entry["summary"],
        "severity_explanation": f"{entry['severity'].title()} severity reflects the recommended urgency for field follow-up.",
        "likely_causes": entry["likely_causes"],
        "possible_causes": entry["likely_causes"],
        "immediate_actions": entry["urgent_actions"],
        "prevention_plan": entry["prevention_tips"],
        "monitoring_advice": entry["monitoring"],
        "when_to_seek_expert_help": "Verify serious crop disease decisions with an agricultural expert, especially if symptoms are spreading.",
        "confidence_explanation": "Confidence is the trained model probability for the selected crop disease class.",
        "advisory_disclaimer": DISCLAIMER,
        "disease_risk": entry["risk"],
    }
    return _pack_result(prediction, advice)


def predict_crop_disease(image_bytes):
    if os.getenv("AI_PROVIDER", "simulated_ai").strip().lower() != "custom_model":
        return None

    runtime = _load_runtime()
    if runtime is None:
        return None

    model, labels = _load_model_and_labels()
    if model is None or labels is None:
        return None

    try:
        with runtime["Image"].open(BytesIO(image_bytes)) as image:
            image = image.convert("RGB").resize((224, 224))
            array = runtime["np"].array(image)

        batch = runtime["np"].expand_dims(array, axis=0)
        batch = runtime["preprocess_input"](batch)
        predictions = model.predict(batch, verbose=0)
        scores = runtime["np"].array(predictions)[0]
        class_index = int(runtime["np"].argmax(scores))
        confidence = round(float(scores[class_index]), 4)
        if class_index >= len(labels):
            raise ValueError("prediction class index is outside labels list")

        if confidence < _confidence_threshold():
            return _uncertain_result(confidence)

        return _result_for_label(labels[class_index], confidence)
    except Exception as exc:
        LOGGER.warning("Custom crop model inference failed; using simulated fallback: %s", exc)
        return None
