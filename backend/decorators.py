from functools import wraps

import jwt
from flask import jsonify, make_response, request

import config


def _extract_token():
    authorization = request.headers.get("Authorization", "").strip()
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    return request.headers.get("x-access-token")


def jwt_required(view_func):
    @wraps(view_func)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return make_response(
                jsonify({"message": "Token is missing! Please log in."}),
                401,
            )

        db = config.get_db()
        blacklist = db.blacklist

        if blacklist.find_one({"token": token}):
            return make_response(
                jsonify({"message": "Token has been cancelled/logged out"}),
                401,
            )

        try:
            payload = jwt.decode(token, config.Config.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return make_response(
                jsonify({"message": "Token has expired! Please log in again."}),
                401,
            )
        except jwt.InvalidTokenError:
            return make_response(
                jsonify({"message": "Token is invalid."}),
                401,
            )

        users = db.users
        username = payload.get("username")
        current_user = users.find_one({"username": username})
        if current_user is None:
            return make_response(
                jsonify({"message": "User associated with token was not found."}),
                404,
            )

        return view_func(current_user, *args, **kwargs)

    return decorated
