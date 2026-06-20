from datetime import datetime, timedelta, timezone
import os
import secrets
from urllib.parse import urlencode

import bcrypt
import jwt
from flask import Blueprint, jsonify, make_response, request
from flask_cors import cross_origin  
from werkzeug.utils import secure_filename
from pymongo.errors import PyMongoError

from blueprints.auth.models import (
    validate_password_reset_payload,
    validate_profile_update_payload,
    validate_signup_payload,
)
import config
from decorators import jwt_required
from extensions import limiter
from utils.emailer import (
    email_delivery_config_error,
    send_password_reset_email,
    send_verification_email,
)
from utils.validators import serialize_document

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

auth_bp = Blueprint("auth_bp", __name__)

VERIFICATION_TOKEN_HOURS = 24
PASSWORD_RESET_TOKEN_MINUTES = 60
MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
PROFILE_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
GENERIC_PASSWORD_RESET_MESSAGE = (
    "If an Agri Guide account exists, a password reset email has been sent."
)


def _safe_user_profile(user):
    return {
        "user_id": str(user.get("_id", "")),
        "username": user.get("username"),
        "email": user.get("email"),
        "role": user.get("role"),
        "contact_preference": user.get("contact_preference"),
        "created_at": serialize_document(user.get("created_at")),
        "display_name": user.get("display_name", ""),
        "phone": user.get("phone", ""),
        "has_profile_image": bool(user.get("profile_image_blob_name")),
    }


def _profile_image_storage_config():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "crop-scans").strip()
    if not connection_string or not container_name or BlobServiceClient is None:
        return None

    return {
        "connection_string": connection_string,
        "container_name": container_name,
    }


def _get_profile_image_container_client(ensure_exists=False):
    storage_config = _profile_image_storage_config()
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


def _profile_image_extension(filename):
    filename = secure_filename(filename or "")
    if "." not in filename:
        return None

    extension = filename.rsplit(".", 1)[1].lower()
    if extension == "jpeg":
        return "jpg"
    if extension in PROFILE_IMAGE_EXTENSIONS:
        return extension
    return None


def _profile_image_blob_name(user_id, extension):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"profile-images/{secure_filename(str(user_id))}/{timestamp}-profile.{extension}"


def _now_utc():
    return datetime.now(timezone.utc)


def _verification_deadline():
    return _now_utc() + timedelta(hours=VERIFICATION_TOKEN_HOURS)


def _password_reset_deadline():
    return _now_utc() + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES)


def _generate_verification_token():
    return secrets.token_urlsafe(32)


def _generate_password_reset_token():
    return secrets.token_urlsafe(32)


def _verification_link(token):
    return f"{config.Config.FRONTEND_VERIFY_EMAIL_URL}?{urlencode({'token': token})}"


def _password_reset_link(token):
    return f"{config.Config.FRONTEND_RESET_PASSWORD_URL}?{urlencode({'token': token})}"


def _email_is_verified(user):
    if user.get("is_verified") is True:
        return True
    if user.get("email_verified") is True:
        return True
    if "email_verified" in user:
        return False
    if "is_verified" in user:
        return False
    return True


def _coerce_utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _public_verification_message(sent):
    if sent:
        return "Account created. Please check your email to verify your account before logging in."
    return (
        "Account created. Email verification is disabled in this demo environment, "
        "so you can log in now."
    )


def _generic_resend_message(sent):
    if sent:
        return "If an unverified account exists, a verification email has been sent."
    return (
        "If an account exists, Email verification is disabled in this demo environment "
        "and no email was sent."
    )


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

    email_config_error = email_delivery_config_error()
    email_required = email_config_error is None
    verification_token = _generate_verification_token() if email_required else None

    user_document = {
        "username": payload["username"],
        "email": payload["email"],
        "password": hashed_password,
        "role": payload["role"],
        "contact_preference": payload["contact_preference"],
        "email_verified": not email_required,
        "is_verified": not email_required,
        "created_at": _now_utc(),
    }
    if email_required:
        user_document["verification_token"] = verification_token
        user_document["verification_token_expires_at"] = _verification_deadline()

    try:
        users.insert_one(user_document)
    except PyMongoError as exc:
        return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    email_sent = False
    if email_required:
        email_sent, _ = send_verification_email(
            to_email=payload["email"],
            verification_link=_verification_link(verification_token),
        )

    return make_response(
        jsonify(
            {
                "message": _public_verification_message(email_sent),
                "email_verification_required": email_required,
                "email_sent": email_sent,
            }
        ),
        201,
    )


@auth_bp.route("/api/users/verify-email", methods=["GET", "POST"])
@auth_bp.route("/api/users/verify", methods=["GET"])
@cross_origin()
@limiter.limit("30 per hour")
def verify_email():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        token = str(payload.get("token", "")).strip()
    else:
        token = request.args.get("token", "").strip()

    if not token:
        return make_response(jsonify({"message": "Missing verification token"}), 400)

    users = config.get_db().users
    now = _now_utc()

    try:
        user = users.find_one({"verification_token": token})
        if not user:
            return make_response(jsonify({"message": "Invalid verification link"}), 400)

        expires_at = _coerce_utc(user.get("verification_token_expires_at"))
        if expires_at is None or expires_at < now:
            return make_response(jsonify({"message": "Verification link expired"}), 400)

        result = users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"email_verified": True, "is_verified": True},
                "$unset": {
                    "verification_token": "",
                    "verification_token_expires_at": "",
                },
            },
        )
    except PyMongoError as exc:
        return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    if result.matched_count == 0:
        return make_response(jsonify({"message": "User not found"}), 404)

    return make_response(
        jsonify({"message": "✅ Email successfully verified! You can now log in."}),
        200,
    )


@auth_bp.route("/api/users/resend-verification", methods=["POST"])
@cross_origin()
@limiter.limit("5 per minute")
def resend_verification():
    payload = request.get_json(silent=True) or {}
    identifier = str(
        payload.get("identifier")
        or payload.get("email")
        or payload.get("username")
        or ""
    ).strip()

    email_config_error = email_delivery_config_error()
    email_required = email_config_error is None
    email_sent = False

    if identifier and email_required:
        users = config.get_db().users
        query = {
            "$or": [
                {"username": identifier},
                {"email": identifier.lower()},
            ]
        }
        try:
            user = users.find_one(query)
            if user and not _email_is_verified(user):
                token = _generate_verification_token()
                users.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "verification_token": token,
                            "verification_token_expires_at": _verification_deadline(),
                            "email_verified": False,
                            "is_verified": False,
                        }
                    },
                )
                email_sent, _ = send_verification_email(
                    to_email=user["email"],
                    verification_link=_verification_link(token),
                )
        except PyMongoError as exc:
            return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    return make_response(
        jsonify(
            {
                "message": _generic_resend_message(email_sent),
                "email_verification_required": email_required,
                "email_sent": email_sent,
            }
        ),
        200,
    )


@auth_bp.route("/api/users/forgot-password", methods=["POST"])
@cross_origin()
@limiter.limit("5 per minute")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    identifier = str(
        payload.get("identifier")
        or payload.get("email")
        or payload.get("username")
        or ""
    ).strip()

    if not identifier:
        return make_response(jsonify({"message": GENERIC_PASSWORD_RESET_MESSAGE}), 200)

    users = config.get_db().users
    query = {
        "$or": [
            {"username": identifier},
            {"email": identifier.lower()},
        ]
    }

    try:
        user = users.find_one(query)
        if user:
            token = _generate_password_reset_token()
            users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "password_reset_token": token,
                        "password_reset_token_expires_at": _password_reset_deadline(),
                    }
                },
            )
            send_password_reset_email(
                to_email=user["email"],
                reset_link=_password_reset_link(token),
            )
    except PyMongoError as exc:
        return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    return make_response(jsonify({"message": GENERIC_PASSWORD_RESET_MESSAGE}), 200)


@auth_bp.route("/api/users/reset-password", methods=["POST"])
@cross_origin()
@limiter.limit("10 per hour")
def reset_password():
    payload, error = validate_password_reset_payload(request.get_json(silent=True))
    if error:
        return make_response(jsonify({"message": error}), 400)

    users = config.get_db().users
    now = _now_utc()

    try:
        user = users.find_one({"password_reset_token": payload["token"]})
        if not user:
            return make_response(jsonify({"message": "Invalid password reset link"}), 400)

        expires_at = _coerce_utc(user.get("password_reset_token_expires_at"))
        if expires_at is None or expires_at < now:
            return make_response(jsonify({"message": "Password reset link expired"}), 400)

        hashed_password = bcrypt.hashpw(
            payload["new_password"].encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        result = users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"password": hashed_password},
                "$unset": {
                    "password_reset_token": "",
                    "password_reset_token_expires_at": "",
                },
            },
        )
    except PyMongoError as exc:
        return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

    if result.matched_count == 0:
        return make_response(jsonify({"message": "User not found"}), 404)

    return make_response(
        jsonify({"message": "Password reset successfully. You can now log in."}),
        200,
    )


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    auth = request.authorization
    if auth:
        username = auth.username.strip() if auth.username else ""
        password = auth.password
    else:
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip()
        password = payload.get("password")

    if not username or not password:
        return make_response(jsonify({"message": "Missing username or password"}), 401)

    user = config.get_db().users.find_one({"username": username})
    if not user:
        return make_response(jsonify({"message": "User not found"}), 404)

    if not _email_is_verified(user):
        return make_response(
            jsonify({"message": "Please verify your email before logging in."}),
            403,
        )

    stored_password = user.get("password")
    try:
        password_valid = bcrypt.checkpw(
            str(password).encode("utf-8"),
            stored_password.encode("utf-8"),
        )
    except (AttributeError, TypeError, ValueError):
        password_valid = False

    if not password_valid:
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
    return make_response(jsonify(_safe_user_profile(current_user)), 200)


@auth_bp.route("/api/users/me", methods=["PUT"])
@jwt_required
def update_current_user(current_user):
    updates, error = validate_profile_update_payload(request.get_json(silent=True))
    if error:
        return make_response(jsonify({"message": error}), 400)

    users = config.get_db().users

    if "email" in updates:
        existing_user = users.find_one(
            {"email": updates["email"], "_id": {"$ne": current_user["_id"]}}
        )
        if existing_user:
            return make_response(
                jsonify({"message": "Email is already registered."}),
                409,
            )

    if updates:
        try:
            result = users.update_one({"_id": current_user["_id"]}, {"$set": updates})
        except PyMongoError as exc:
            return make_response(jsonify({"message": "Database error", "error": str(exc)}), 500)

        if result.matched_count == 0:
            return make_response(jsonify({"message": "User not found"}), 404)

    updated_user = users.find_one({"_id": current_user["_id"]})
    return make_response(jsonify(_safe_user_profile(updated_user)), 200)


@auth_bp.route("/api/users/me/profile-image", methods=["POST"])
@jwt_required
def upload_current_user_profile_image(current_user):
    uploaded_image = request.files.get("image")
    if uploaded_image is None or not uploaded_image.filename:
        return make_response(jsonify({"message": "Profile image file is required."}), 400)

    extension = _profile_image_extension(uploaded_image.filename)
    if extension is None:
        return make_response(
            jsonify({"message": "Invalid image type. Please upload a jpg, jpeg, png, or webp file."}),
            400,
        )

    content_type = uploaded_image.content_type or "application/octet-stream"
    if content_type not in PROFILE_IMAGE_CONTENT_TYPES:
        return make_response(
            jsonify({"message": "Invalid image content type. Please upload a jpg, png, or webp image."}),
            400,
        )

    image_bytes = uploaded_image.read()
    if len(image_bytes) > MAX_PROFILE_IMAGE_BYTES:
        return make_response(jsonify({"message": "Image file is too large. Maximum size is 5 MB."}), 400)

    container_client = _get_profile_image_container_client(ensure_exists=True)
    if container_client is None:
        return make_response(
            jsonify({"message": "Profile image storage is not configured. Initials avatar is still available."}),
            503,
        )

    blob_name = _profile_image_blob_name(current_user["_id"], extension)
    upload_kwargs = {"overwrite": True}
    if ContentSettings is not None:
        upload_kwargs["content_settings"] = ContentSettings(content_type=content_type)

    try:
        container_client.upload_blob(name=blob_name, data=image_bytes, **upload_kwargs)
    except AzureError:
        return make_response(
            jsonify({"message": "Unable to save profile image right now. Initials avatar is still available."}),
            502,
        )
    except Exception:
        return make_response(
            jsonify({"message": "Unable to save profile image right now. Initials avatar is still available."}),
            502,
        )

    previous_blob_name = current_user.get("profile_image_blob_name")
    if previous_blob_name and previous_blob_name != blob_name:
        try:
            container_client.delete_blob(previous_blob_name)
        except ResourceNotFoundError:
            pass
        except Exception:
            pass

    users = config.get_db().users
    users.update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "profile_image_blob_name": blob_name,
                "profile_image_content_type": content_type,
                "profile_image_uploaded_at": _now_utc(),
            }
        },
    )
    updated_user = users.find_one({"_id": current_user["_id"]})
    return make_response(jsonify(_safe_user_profile(updated_user)), 200)


@auth_bp.route("/api/users/me/profile-image", methods=["GET"])
@jwt_required
def get_current_user_profile_image(current_user):
    blob_name = current_user.get("profile_image_blob_name")
    if not blob_name:
        return make_response(jsonify({"message": "Profile image is not set."}), 404)

    container_client = _get_profile_image_container_client()
    if container_client is None:
        return make_response(
            jsonify({"message": "Profile image storage is not configured."}),
            503,
        )

    try:
        image_bytes = container_client.download_blob(blob_name).readall()
    except ResourceNotFoundError:
        return make_response(jsonify({"message": "Profile image is not set."}), 404)
    except AzureError:
        return make_response(jsonify({"message": "Unable to load profile image."}), 502)
    except Exception:
        return make_response(jsonify({"message": "Unable to load profile image."}), 502)

    response = make_response(image_bytes)
    response.headers["Content-Type"] = current_user.get("profile_image_content_type") or "application/octet-stream"
    response.headers["Content-Disposition"] = 'inline; filename="profile-image"'
    return response


@auth_bp.route("/api/users/me/profile-image", methods=["DELETE"])
@jwt_required
def delete_current_user_profile_image(current_user):
    blob_name = current_user.get("profile_image_blob_name")
    container_client = _get_profile_image_container_client()

    if blob_name and container_client is not None:
        try:
            container_client.delete_blob(blob_name)
        except ResourceNotFoundError:
            pass
        except Exception:
            pass

    users = config.get_db().users
    users.update_one(
        {"_id": current_user["_id"]},
        {
            "$unset": {
                "profile_image_blob_name": "",
                "profile_image_content_type": "",
                "profile_image_uploaded_at": "",
            }
        },
    )
    updated_user = users.find_one({"_id": current_user["_id"]})
    return make_response(jsonify(_safe_user_profile(updated_user)), 200)


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
