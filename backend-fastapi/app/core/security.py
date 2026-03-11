from typing import Dict
from uuid import uuid4


class ApiAuthError(Exception):
    def __init__(self, message: str, status_code: int = 401, error: str = "unauthenticated"):
        self.message = message
        self.status_code = status_code
        self.error = error
        super().__init__(message)


SESSIONS: Dict[str, dict] = {}


def issue_token(user_payload: dict) -> str:
    token = str(uuid4())
    SESSIONS[token] = user_payload
    return token


def user_from_token(raw_auth: str | None) -> dict:
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    token = raw_auth.replace("Bearer ", "", 1).strip()
    session = SESSIONS.get(token)
    if not session:
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    return session


def revoke_token(raw_auth: str | None) -> None:
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    token = raw_auth.replace("Bearer ", "", 1).strip()
    if token not in SESSIONS:
        raise ApiAuthError("Authentication required", 401, "unauthenticated")

    del SESSIONS[token]


def require_role(user: dict, allowed_roles: list[str]) -> None:
    if user.get("role") not in allowed_roles:
        raise ApiAuthError("Access denied", 403, "forbidden")
