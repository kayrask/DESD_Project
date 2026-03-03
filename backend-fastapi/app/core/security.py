from typing import Dict
from uuid import uuid4

from fastapi import HTTPException, status

SESSIONS: Dict[str, dict] = {}


def issue_token(user_payload: dict) -> str:
    token = str(uuid4())
    SESSIONS[token] = user_payload
    return token


def user_from_token(raw_auth: str | None) -> dict:
    if not raw_auth or not raw_auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = raw_auth.replace("Bearer ", "", 1).strip()
    session = SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return session


def require_role(user: dict, allowed_roles: list[str]) -> None:
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
