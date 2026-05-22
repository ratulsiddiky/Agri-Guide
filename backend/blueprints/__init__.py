from blueprints.auth import auth_bp
from blueprints.farms import farms_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(farms_bp)
