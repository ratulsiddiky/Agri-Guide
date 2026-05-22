import os
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    _TESTING_CONTEXT = _as_bool(os.getenv("FLASK_TESTING"), default=False) or bool(
        os.getenv("PYTEST_CURRENT_TEST")
    )

    SECRET_KEY = os.getenv("SECRET_KEY") or ("test_secret" if _TESTING_CONTEXT else None)
    MONGO_URI = os.getenv("MONGO_URI") or ("mongodb://127.0.0.1:27017" if _TESTING_CONTEXT else None)
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME") or ("smart_agri_db" if _TESTING_CONTEXT else None)
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_PORT", "5001"))
    DEBUG = _as_bool(os.getenv("FLASK_DEBUG"), default=True)
    TESTING = _as_bool(os.getenv("FLASK_TESTING"), default=False)

    EMAIL_ENABLED = _as_bool(os.getenv("EMAIL_ENABLED"), default=False)
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS = _as_bool(os.getenv("SMTP_USE_TLS"), default=True)
    EMAIL_FROM = os.getenv("EMAIL_FROM")

    RATE_LIMIT_DEFAULTS = [
        os.getenv("RATE_LIMIT_DEFAULT_1", "200 per day"),
        os.getenv("RATE_LIMIT_DEFAULT_2", "50 per hour"),
    ]


def _require_config():
    missing = []
    if not Config.SECRET_KEY:
        missing.append("SECRET_KEY")
    if not Config.MONGO_URI:
        missing.append("MONGO_URI")
    if not Config.MONGO_DB_NAME:
        missing.append("MONGO_DB_NAME")
    if missing and not Config._TESTING_CONTEXT:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_mongo_client():
    _require_config()
    return MongoClient(
        Config.MONGO_URI,
        maxPoolSize=50, 
        minPoolSize=10,  
        socketTimeoutMS=5000  
    )


@lru_cache(maxsize=1)
def get_db():
    _require_config()
    return get_mongo_client()[Config.MONGO_DB_NAME]


def reset_db_cache():
    get_db.cache_clear()
    get_mongo_client.cache_clear()
