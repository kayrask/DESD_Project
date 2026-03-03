from fastapi import HTTPException, status

from app.core.security import issue_token
from app.models.schemas import LoginResponse
from app.repositories.auth_repo import find_user_by_email


def login_user(email: str, password: str) -> LoginResponse:
    user = find_user_by_email(email)
    if not user or user.password != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    payload = {
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
    }
    token = issue_token(payload)
    return LoginResponse(access_token=token, user=payload)
