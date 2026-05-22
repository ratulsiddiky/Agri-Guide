from datetime import datetime, timedelta, timezone
import secrets
import smtplib

import bcrypt
import jwt
from bson import ObjectId
from flask import Blueprint, jsonify, make_response, request
from flask_cors import cross_origin  
from pymongo.errors import PyMongoError

from blueprints.auth.models import validate_signup_payload
import config
from decorators import jwt_required
from extensions import limiter
from utils.emailer import send_verification_email
from utils.validators import serialize_document

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/api/users/signup", methods=["POST"])
@auth_bp.route("/api/users/register", methods=["POST"])
@limiter.limit("10 per minute")
def signup():
    payload, error = validate_signup_payload(request.get_json(silent=True))
    if error:
        return make_response(jsonify({"message": error}), 400)

    users = config.get_db().users
    if users.find_one(
        {"$or": [{"username": payload["username"]}, {"email": payload["email"]}]}
    ):
        return make_response(
            jsonify({"message": "Username or email is already registered."}),
            409,
        )

    hashed_password = bcrypt.hashpw(
        payload["password"].encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    try:
        result = users.insert_one(
            {
                "username": payload["username"],
                "email": payload["email"],
                "password": hashed_password,
                "role": payload["role"],
                "contact_preference": payload["contact_preference"],
                "is_verified": True, 
                "created_at": datetime.now(timezone.utc),
            }
        )
    except PyMongoError as exc:
        return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    return make_response(
        jsonify(
            {
                "message": f"✅ Account created for {payload['username']} successfully! You can now log in.",
            }
        ),
        201,
    )


@auth_bp.route("/api/users/verify", methods=["GET"])
@cross_origin()
@limiter.limit("30 per hour")
def verify_email():
    token = request.args.get("token", "").strip()
    if not token:
        return make_response(jsonify({"message": "Missing verification token"}), 400)

    users = config.get_db().users
    now = datetime.now(timezone.utc)  

    try:
        user = users.find_one({"verification_token": token})
        if not user:
            return make_response(jsonify({"message": "Invalid verification link"}), 400)

        expires_at = user.get("verification_token_expires_at")
        if not isinstance(expires_at, datetime) or expires_at < now:  
            return make_response(jsonify({"message": "Verification link expired"}), 400)

        result = users.update_one(
            {"_id": user["_id"]},
            {"$set": {"is_verified": True}, "$unset": {"verification_token": "", "verification_token_expires_at": ""}},
        )
    except PyMongoError as exc:
        return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    if result.matched_count == 0:
        return make_response(jsonify({"message": "User not found"}), 404)

    return make_response(
        jsonify({"message": "✅ Email successfully verified! You can now log in."}),
        200,
    )


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response(jsonify({"message": "Missing username or password"}), 401)

    user = config.get_db().users.find_one({"username": auth.username})
    if not user:
        return make_response(jsonify({"message": "User not found"}), 404)

    if not user.get("is_verified", False):
        return make_response(
            jsonify({"message": "Please verify your email before logging in."}),
            403,
        )

    if not bcrypt.checkpw(
        auth.password.encode("utf-8"),
        user["password"].encode("utf-8"),
    ):
        return make_response(jsonify({"message": "Incorrect password"}), 401)

    token = jwt.encode(
        {
            "username": user["username"],
            "role": user["role"],
            "user_id": str(user["_id"]),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        config.Config.SECRET_KEY,
        algorithm="HS256",
    )

    return make_response(
        jsonify(
            {
                "message": "Login successful!",
                "token": token,
                "username": user["username"],
                "role": user["role"],
                "user_id": str(user["_id"]),
            }
        ),
        200,
    )


@auth_bp.route("/api/logout", methods=["GET"])
@jwt_required
def logout(current_user):
    authorization = request.headers.get("Authorization", "").split()
    token = (
        authorization[1]
        if len(authorization) == 2 and authorization[0].lower() == "bearer"
        else request.headers.get("x-access-token")
    )
    config.get_db().blacklist.insert_one({"token": token, "username": current_user["username"]})
    return make_response(jsonify({"message": "Logout successful"}), 200)


@auth_bp.route("/api/users/me", methods=["GET"])
@jwt_required
def get_current_user(current_user):
    user_doc = serialize_document(current_user)
    user_doc.pop("password", None)
    user_doc.pop("verification_token", None)
    user_doc.pop("verification_token_expires_at", None)
    return make_response(jsonify(user_doc), 200)


@auth_bp.route("/api/users", methods=["GET"])
@jwt_required
def get_all_users(current_user):
    if current_user.get("role") != "admin":
        return make_response(jsonify({"message": "Admin access required"}), 403)

    page_raw = request.args.get("page", "1")
    limit_raw = request.args.get("limit", "20")
    try:
        page = max(1, int(page_raw))
        limit = max(1, min(100, int(limit_raw)))
    except (TypeError, ValueError):
        return make_response(
            jsonify({"message": "Invalid pagination parameters"}),
            400,
        )

    skip = (page - 1) * limit
    
    try:
        total = config.get_db().users.count_documents({})
        users_list = [
            serialize_document(user)
            for user in config.get_db().users.find({}, {"password": 0}).skip(skip).limit(limit)
        ]
    except PyMongoError as exc:
        return make_response(
            jsonify({"message": "Database error", "error": str(exc)}),
            500,
        )
    
    return make_response(
        jsonify({
            "count": len(users_list),
            "total": total,
            "users": users_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "has_next": skip + len(users_list) < total,
            }
        }), 
        200
    )
