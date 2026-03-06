from fastapi import APIRouter, Header

from app.models.schemas import LoginRequest, LoginResponse, RegisterRequest
from app.core.security import revoke_token
from app.services.auth_service import login_user, register_new_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    return login_user(payload.email, payload.password)


@router.post("/register")
def register(payload: RegisterRequest) -> dict:
    return register_new_user(payload.email, payload.password, payload.role, payload.full_name)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    revoke_token(authorization)
    return {"message": "Logged out successfully"}
