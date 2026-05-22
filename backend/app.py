from flask import Flask, jsonify, make_response
from flask_cors import CORS
from config import Config, get_db
from extensions import limiter


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["RATELIMIT_DEFAULT"] = "; ".join(Config.RATE_LIMIT_DEFAULTS)
    CORS(
        app,
        resources={
            r"/*": {
                "origins": ["http://localhost:4200", "http://127.0.0.1:4200"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                "allow_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True,
                "expose_headers": ["Content-Type", "Authorization"],
                "max_age": 3600,
            }
        },
    )

    limiter.init_app(app)

    from blueprints.auth.auth import auth_bp
    from blueprints.farms.farms import farms_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(farms_bp)

    @app.route("/", methods=["GET"])
    def home():
        return make_response(
            jsonify({"message": "Welcome to the Smart Agriculture API!"}), 200
        )

    with app.app_context():
        db = get_db()
    try:
        db.farms.create_index([("location", "2dsphere")])
    except Exception as e:
        print(f"Database Index Note (2dsphere): {e}")
    try:
        db.farms.create_index([("farm_name", "text"), ("crop_type", "text")])
    except Exception as e:
        print(f"Database Index Note (text): {e}")    
    
    try:
        db.farms.create_index([("owner_id", 1)])
    except Exception as e:
        print(f"Database Index Note (owner_id): {e}")
    try:
        db.users.create_index([("username", 1)])
    except Exception as e:
        print(f"Database Index Note (username): {e}")
    try:
        db.blacklist.create_index([("token", 1)])
    except Exception as e:
        print(f"Database Index Note (blacklist token): {e}")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)