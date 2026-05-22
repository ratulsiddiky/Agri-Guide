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
