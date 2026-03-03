from fastapi import APIRouter

from app.models.schemas import LoginRequest, LoginResponse
from app.services.auth_service import login_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    return login_user(payload.email, payload.password)
