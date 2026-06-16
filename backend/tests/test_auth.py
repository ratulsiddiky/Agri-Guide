from base64 import b64encode
from datetime import datetime, timedelta, timezone

import bcrypt
import mongomock
import pytest

import config
import blueprints.auth.auth as auth_module
from app import create_app


@pytest.fixture()
def client(monkeypatch):
    mock_client = mongomock.MongoClient()
    mock_db = mock_client["smart_agri_test"]
    config.reset_db_cache()
    monkeypatch.setattr(config, "get_mongo_client", lambda: mock_client)
    monkeypatch.setattr(config, "get_db", lambda: mock_db)

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as test_client:
        yield test_client


def _basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def _insert_verified_user(username="farmer_one", password_text="Password123!", role="user"):
    password = bcrypt.hashpw(password_text.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
            "role": role,
            "contact_preference": "email",
            "email_verified": True,
            "is_verified": True,
            "verification_token": "secret-token",
            "verification_token_expires_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }
    )


def _login_token(client, username="farmer_one", password="Password123!", role="user"):
    _insert_verified_user(username=username, password_text=password, role=role)
    response = client.post("/api/login", headers=_basic_auth(username, password))
    return response.get_json()["token"]


def test_signup_creates_user(client):
    response = client.post(
        "/api/users/signup",
        json={
            "username": "new_farmer",
            "email": "new_farmer@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    stored_user = config.get_db().users.find_one({"username": "new_farmer"})
    assert body["email_verification_required"] is False
    assert "Email verification is disabled in this demo environment" in body["message"]
    assert stored_user["email_verified"] is True
    assert stored_user["is_verified"] is True
    assert "verification_token" not in stored_user


def test_signup_requires_verification_when_email_is_configured(client, monkeypatch):
    monkeypatch.setattr(config.Config, "EMAIL_ENABLED", True)
    monkeypatch.setattr(config.Config, "SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setattr(config.Config, "SMTP_USERNAME", "smtp-user@example.com")
    monkeypatch.setattr(config.Config, "SMTP_PASSWORD", "smtp-password")
    monkeypatch.setattr(config.Config, "EMAIL_FROM", "no-reply@example.com")
    monkeypatch.setattr(
        auth_module,
        "send_verification_email",
        lambda **kwargs: (True, None),
    )

    response = client.post(
        "/api/users/signup",
        json={
            "username": "new_farmer",
            "email": "new_farmer@example.com",
            "password": "Password123!",
        },
    )

    body = response.get_json()
    stored_user = config.get_db().users.find_one({"username": "new_farmer"})
    assert response.status_code == 201
    assert body["email_verification_required"] is True
    assert body["email_sent"] is True
    assert body["message"] == "Account created. Please check your email to verify your account before logging in."
    assert stored_user["email_verified"] is False
    assert stored_user["is_verified"] is False
    assert stored_user["verification_token"]
    assert stored_user["verification_token_expires_at"]
    assert "verification_token" not in body


def test_basic_auth_login_works(client):
    _insert_verified_user()

    response = client.post(
        "/api/login",
        headers=_basic_auth("farmer_one", "Password123!"),
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["message"] == "Login successful!"
    assert body["token"]
    assert body["username"] == "farmer_one"
    assert body["role"] == "user"
    assert body["user_id"]


def test_json_login_works(client):
    _insert_verified_user()

    response = client.post(
        "/api/login",
        json={"username": " farmer_one ", "password": "Password123!"},
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["message"] == "Login successful!"
    assert body["token"]
    assert body["username"] == "farmer_one"
    assert body["role"] == "user"
    assert body["user_id"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "farmer_one"},
        {"password": "Password123!"},
        {"username": "   ", "password": "Password123!"},
        {"username": "farmer_one", "password": ""},
    ],
)
def test_login_missing_username_or_password_returns_401(client, payload):
    response = client.post("/api/login", json=payload)

    assert response.status_code == 401
    assert response.get_json()["message"] == "Missing username or password"


def test_login_handles_malformed_password_hash(client):
    config.get_db().users.insert_one(
        {
            "username": "farmer_one",
            "email": "farmer_one@example.com",
            "password": "not-a-bcrypt-hash",
            "role": "user",
            "is_verified": True,
        }
    )

    response = client.post(
        "/api/login",
        json={"username": "farmer_one", "password": "Password123!"},
    )

    assert response.status_code == 401
    assert response.get_json()["message"] == "Incorrect password"


def test_login_requires_verified_user(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "farmer_one",
            "email": "farmer_one@example.com",
            "password": password,
            "role": "user",
            "email_verified": False,
            "is_verified": False,
        }
    )

    response = client.post("/api/login", headers=_basic_auth("farmer_one", "Password123!"))
    assert response.status_code == 403
    assert response.get_json()["message"] == "Please verify your email before logging in."


def test_login_allows_legacy_user_without_verification_fields(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "legacy_farmer",
            "email": "legacy@example.com",
            "password": password,
            "role": "user",
        }
    )

    response = client.post("/api/login", headers=_basic_auth("legacy_farmer", "Password123!"))
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_login_allows_legacy_user_with_is_verified_true(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "legacy_verified",
            "email": "legacy_verified@example.com",
            "password": password,
            "role": "user",
            "is_verified": True,
        }
    )

    response = client.post("/api/login", headers=_basic_auth("legacy_verified", "Password123!"))
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_verify_email_token_marks_user_verified(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "new_farmer",
            "email": "new_farmer@example.com",
            "password": password,
            "role": "user",
            "email_verified": False,
            "is_verified": False,
            "verification_token": "valid-token",
            "verification_token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )

    verify_response = client.post("/api/users/verify-email", json={"token": "valid-token"})
    login_response = client.post("/api/login", headers=_basic_auth("new_farmer", "Password123!"))
    stored_user = config.get_db().users.find_one({"username": "new_farmer"})

    assert verify_response.status_code == 200
    assert stored_user["email_verified"] is True
    assert stored_user["is_verified"] is True
    assert "verification_token" not in stored_user
    assert "verification_token_expires_at" not in stored_user
    assert login_response.status_code == 200


def test_verify_email_rejects_invalid_token(client):
    response = client.post("/api/users/verify-email", json={"token": "not-real"})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid verification link"


def test_verify_email_rejects_expired_token(client):
    config.get_db().users.insert_one(
        {
            "username": "new_farmer",
            "email": "new_farmer@example.com",
            "password": "not-used",
            "role": "user",
            "email_verified": False,
            "is_verified": False,
            "verification_token": "expired-token",
            "verification_token_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
    )

    response = client.post("/api/users/verify-email", json={"token": "expired-token"})

    assert response.status_code == 400
    assert response.get_json()["message"] == "Verification link expired"


def test_resend_verification_returns_generic_message_and_rotates_token(client, monkeypatch):
    monkeypatch.setattr(config.Config, "EMAIL_ENABLED", True)
    monkeypatch.setattr(config.Config, "SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setattr(config.Config, "SMTP_USERNAME", "smtp-user@example.com")
    monkeypatch.setattr(config.Config, "SMTP_PASSWORD", "smtp-password")
    monkeypatch.setattr(config.Config, "EMAIL_FROM", "no-reply@example.com")
    monkeypatch.setattr(
        auth_module,
        "send_verification_email",
        lambda **kwargs: (True, None),
    )
    config.get_db().users.insert_one(
        {
            "username": "new_farmer",
            "email": "new_farmer@example.com",
            "password": "not-used",
            "role": "user",
            "email_verified": False,
            "is_verified": False,
            "verification_token": "old-token",
            "verification_token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )

    response = client.post("/api/users/resend-verification", json={"identifier": "new_farmer"})
    stored_user = config.get_db().users.find_one({"username": "new_farmer"})

    assert response.status_code == 200
    assert response.get_json()["message"] == "If an unverified account exists, a verification email has been sent."
    assert stored_user["verification_token"] != "old-token"
    assert "verification_token" not in response.get_json()


def test_resend_verification_is_demo_safe_when_email_disabled(client):
    response = client.post("/api/users/resend-verification", json={"identifier": "missing_user"})

    assert response.status_code == 200
    assert response.get_json()["email_verification_required"] is False
    assert "Email verification is disabled in this demo environment" in response.get_json()["message"]


def test_forgot_password_returns_generic_message_for_existing_user(client, monkeypatch):
    sent_messages = []
    _insert_verified_user()
    monkeypatch.setattr(
        auth_module,
        "send_password_reset_email",
        lambda **kwargs: sent_messages.append(kwargs) or (True, None),
    )

    response = client.post("/api/users/forgot-password", json={"identifier": "farmer_one"})
    stored_user = config.get_db().users.find_one({"username": "farmer_one"})

    assert response.status_code == 200
    assert response.get_json()["message"] == auth_module.GENERIC_PASSWORD_RESET_MESSAGE
    assert stored_user["password_reset_token"]
    assert stored_user["password_reset_token_expires_at"]
    assert sent_messages[0]["to_email"] == "farmer_one@example.com"
    assert stored_user["password_reset_token"] in sent_messages[0]["reset_link"]
    assert "password_reset_token" not in response.get_json()


def test_forgot_password_returns_generic_message_for_missing_user(client, monkeypatch):
    sent_messages = []
    monkeypatch.setattr(
        auth_module,
        "send_password_reset_email",
        lambda **kwargs: sent_messages.append(kwargs) or (True, None),
    )

    response = client.post("/api/users/forgot-password", json={"identifier": "missing_user"})

    assert response.status_code == 200
    assert response.get_json()["message"] == auth_module.GENERIC_PASSWORD_RESET_MESSAGE
    assert sent_messages == []


def test_reset_password_with_valid_token_updates_password_and_clears_token(client):
    _insert_verified_user()
    config.get_db().users.update_one(
        {"username": "farmer_one"},
        {
            "$set": {
                "password_reset_token": "valid-reset-token",
                "password_reset_token_expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            }
        },
    )

    reset_response = client.post(
        "/api/users/reset-password",
        json={"token": "valid-reset-token", "new_password": "NewPassword123!"},
    )
    new_login_response = client.post(
        "/api/login",
        headers=_basic_auth("farmer_one", "NewPassword123!"),
    )
    old_login_response = client.post(
        "/api/login",
        headers=_basic_auth("farmer_one", "Password123!"),
    )
    stored_user = config.get_db().users.find_one({"username": "farmer_one"})

    assert reset_response.status_code == 200
    assert reset_response.get_json()["message"] == "Password reset successfully. You can now log in."
    assert new_login_response.status_code == 200
    assert old_login_response.status_code == 401
    assert "password_reset_token" not in stored_user
    assert "password_reset_token_expires_at" not in stored_user


def test_reset_password_rejects_invalid_token(client):
    response = client.post(
        "/api/users/reset-password",
        json={"token": "not-real", "new_password": "NewPassword123!"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid password reset link"


def test_reset_password_rejects_expired_token(client):
    _insert_verified_user()
    config.get_db().users.update_one(
        {"username": "farmer_one"},
        {
            "$set": {
                "password_reset_token": "expired-reset-token",
                "password_reset_token_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            }
        },
    )

    response = client.post(
        "/api/users/reset-password",
        json={"token": "expired-reset-token", "new_password": "NewPassword123!"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Password reset link expired"


def test_reset_password_rejects_weak_password(client):
    _insert_verified_user()
    config.get_db().users.update_one(
        {"username": "farmer_one"},
        {
            "$set": {
                "password_reset_token": "valid-reset-token",
                "password_reset_token_expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            }
        },
    )

    response = client.post(
        "/api/users/reset-password",
        json={"token": "valid-reset-token", "new_password": "short"},
    )

    assert response.status_code == 400
    assert "Password" in response.get_json()["message"]


def test_logout_blacklists_token(client):
    password = bcrypt.hashpw(b"Password123!", bcrypt.gensalt()).decode("utf-8")
    config.get_db().users.insert_one(
        {
            "username": "admin_user",
            "email": "admin@example.com",
            "password": password,
            "role": "admin",
            "is_verified": True,
        }
    )

    login_response = client.post(
        "/api/login",
        headers=_basic_auth("admin_user", "Password123!"),
    )
    token = login_response.get_json()["token"]

    logout_response = client.get(
        "/api/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout_response.status_code == 200
    assert config.get_db().blacklist.find_one({"token": token}) is not None


def test_get_current_user_profile_returns_safe_fields(client):
    token = _login_token(client)

    response = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})

    body = response.get_json()
    assert response.status_code == 200
    assert body["user_id"]
    assert body["username"] == "farmer_one"
    assert body["email"] == "farmer_one@example.com"
    assert body["role"] == "user"
    assert body["contact_preference"] == "email"
    assert "created_at" in body
    assert "password" not in body
    assert "verification_token" not in body
    assert "verification_token_expires_at" not in body


def test_update_current_user_profile_allows_safe_fields(client):
    token = _login_token(client)

    response = client.put(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": " Updated.Farmer@Example.com ",
            "contact_preference": "sms",
            "display_name": " Farmer One ",
            "phone": " 07123 456789 ",
        },
    )

    body = response.get_json()
    stored_user = config.get_db().users.find_one({"username": "farmer_one"})
    assert response.status_code == 200
    assert body["email"] == "updated.farmer@example.com"
    assert body["contact_preference"] == "sms"
    assert body["display_name"] == "Farmer One"
    assert body["phone"] == "07123 456789"
    assert stored_user["email"] == "updated.farmer@example.com"
    assert stored_user["display_name"] == "Farmer One"


def test_update_current_user_profile_does_not_change_role_or_username(client):
    token = _login_token(client)

    response = client.put(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "renamed_user",
            "role": "admin",
            "email": "farmer_one_updated@example.com",
        },
    )

    body = response.get_json()
    stored_user = config.get_db().users.find_one({"username": "farmer_one"})
    assert response.status_code == 200
    assert body["username"] == "farmer_one"
    assert body["role"] == "user"
    assert stored_user["username"] == "farmer_one"
    assert stored_user["role"] == "user"
    assert config.get_db().users.find_one({"username": "renamed_user"}) is None


@pytest.mark.parametrize("method", ["get", "put"])
def test_current_user_profile_requires_authentication(client, method):
    request_method = getattr(client, method)

    response = request_method("/api/users/me", json={})

    assert response.status_code == 401


def test_update_current_user_profile_rejects_invalid_email(client):
    token = _login_token(client)

    response = client.put(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "not-an-email"},
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "A valid email address is required."
