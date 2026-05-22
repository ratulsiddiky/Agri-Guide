from datetime import datetime, timezone
import requests
from bson import ObjectId
from flask import Blueprint, jsonify, make_response, request
from pymongo.errors import PyMongoError

from blueprints.farms.models import (
    validate_alert_payload,
    validate_farm_payload,
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

    farm_data["owner_id"] = current_user["_id"]
    farm_data["created_at"] = datetime.now(timezone.utc)
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
        if sensor.get("type") == "Soil Moisture":
            readings = sensor.get("readings", [])
            if readings and isinstance(readings, list):
                last = readings[-1]
                if isinstance(last, dict):
                    moisture_level = last.get("value")
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
