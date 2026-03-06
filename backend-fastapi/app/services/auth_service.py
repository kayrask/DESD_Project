from fastapi import HTTPException, status

from app.core.security import issue_token
from app.models.schemas import LoginResponse, RegisterRequest
from app.repositories.auth_repo import find_user_by_email, register_user, verify_password


def login_user(email: str, password: str) -> LoginResponse:
    user = find_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    payload = {
        "email": user.get("email"),
        "role": user.get("role"),
        "full_name": user.get("full_name"),
    }
    token = issue_token(payload)
    return LoginResponse(access_token=token, user=payload)


def register_new_user(email: str, password: str, role: str, full_name: str) -> dict:
    try:
        user = register_user(email, password, role, full_name)
        return {
            "message": "User registered successfully",
            "user": {"email": user.get("email"), "role": user.get("role"), "full_name": user.get("full_name")},
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
