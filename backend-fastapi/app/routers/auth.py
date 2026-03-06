from fastapi import APIRouter

from app.models.schemas import LoginRequest, LoginResponse, RegisterRequest
from app.services.auth_service import login_user, register_new_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    return login_user(payload.email, payload.password)


@router.post("/register")
def register(payload: RegisterRequest) -> dict:
    return register_new_user(payload.email, payload.password, payload.role, payload.full_name)
