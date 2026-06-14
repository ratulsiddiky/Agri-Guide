from utils.validators import is_non_empty_string, normalize_email, validate_password_strength


def validate_signup_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not is_non_empty_string(username):
        return None, "Username is required."
    if not is_non_empty_string(email):
        return None, "Email is required."
    password_error = validate_password_strength(password)
    if password_error:
        return None, password_error

    username_clean = username.strip()
    if len(username_clean) < 3 or len(username_clean) > 32:
        return None, "Username must be between 3 and 32 characters."

    normalized_email = normalize_email(email)
    if normalized_email is None:
        return None, "A valid email address is required."

    return {
        "username": username_clean,
        "email": normalized_email,
        "password": password.strip(),
        "role": data.get("role", "user"),
        "contact_preference": data.get("contact_preference", "email"),
    }, None


def validate_profile_update_payload(data):
    if not isinstance(data, dict):
        return None, "Invalid JSON body."

    updates = {}

    if "email" in data:
        normalized_email = normalize_email(data.get("email"))
        if normalized_email is None:
            return None, "A valid email address is required."
        updates["email"] = normalized_email

    if "contact_preference" in data:
        contact_preference = data.get("contact_preference")
        if not is_non_empty_string(contact_preference):
            return None, "Contact preference is required."
        contact_preference_clean = contact_preference.strip().lower()
        if contact_preference_clean not in {"email", "phone", "sms"}:
            return None, "Contact preference must be email, phone, or sms."
        updates["contact_preference"] = contact_preference_clean

    for field, max_length in {"display_name": 80, "phone": 32}.items():
        if field not in data:
            continue
        value = data.get(field)
        if value is None:
            updates[field] = ""
            continue
        if not isinstance(value, str):
            return None, f"{field.replace('_', ' ').title()} must be text."
        value_clean = value.strip()
        if len(value_clean) > max_length:
            return None, f"{field.replace('_', ' ').title()} must be {max_length} characters or fewer."
        updates[field] = value_clean

    return updates, None
