from typing import Dict
from uuid import uuid4

from fastapi import HTTPException, status

SESSIONS: Dict[str, dict] = {}


def issue_token(user_payload: dict) -> str:
    token = str(uuid4())
    SESSIONS[token] = user_payload
    return token


def _auth_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthenticated", "message": message},
    )


def user_from_token(raw_auth: str | None) -> dict:
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise _auth_error("Authentication required")

    token = raw_auth.replace("Bearer ", "", 1).strip()
    session = SESSIONS.get(token)
    if not session:
        raise _auth_error("Authentication required")

    return session


def revoke_token(raw_auth: str | None) -> None:
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise _auth_error("Authentication required")

    token = raw_auth.replace("Bearer ", "", 1).strip()
    if token not in SESSIONS:
        raise _auth_error("Authentication required")

    del SESSIONS[token]


def require_role(user: dict, allowed_roles: list[str]) -> None:
    if user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Access denied"},
        )
