class ApiAuthError(Exception):
    def __init__(self, message: str, status_code: int = 401, error: str = "unauthenticated"):
        self.message = message
        self.status_code = status_code
        self.error = error
        super().__init__(message)


def issue_token(user) -> str:
    """Create (or replace) a database-backed auth token for the given User."""
    from rest_framework.authtoken.models import Token
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return token.key


def user_from_token(raw_auth: str | None) -> dict:
    """Validate Bearer token and return a user payload dict."""
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    token_key = raw_auth.removeprefix("Bearer ").strip()

    from rest_framework.authtoken.models import Token
    try:
        token_obj = Token.objects.select_related("user").get(key=token_key)
    except Token.DoesNotExist:
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    user = token_obj.user
    return {"email": user.email, "role": user.role, "full_name": user.full_name}


def revoke_token(raw_auth: str | None) -> None:
    """Delete the token from the database (logout)."""
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    token_key = raw_auth.removeprefix("Bearer ").strip()

    from rest_framework.authtoken.models import Token
    deleted, _ = Token.objects.filter(key=token_key).delete()
    if not deleted:
        raise ApiAuthError("Authentication required", 401, "unauthenticated")


def require_role(user: dict, allowed_roles: list[str]) -> None:
    if user.get("role") not in allowed_roles:
        raise ApiAuthError("Access denied", 403, "forbidden")
