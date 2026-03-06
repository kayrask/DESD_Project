import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers.auth import router as auth_router
from app.routers.dashboards import router as dashboards_router
from app.routers.orders import router as orders_router

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
ROOT_ENV_EXAMPLE_PATH = Path(__file__).resolve().parents[2] / ".env.example"
load_dotenv(ROOT_ENV_PATH if ROOT_ENV_PATH.exists() else ROOT_ENV_EXAMPLE_PATH)

app = FastAPI(title="DESD Sprint 1 API", version="0.1.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_URLS",
        "http://localhost:5173,http://127.0.0.1:5173,http://frontend:5173",
    ).split(",")
    if origin.strip()
]
legacy_origin = os.getenv("FRONTEND_URL")
if legacy_origin and legacy_origin not in cors_origins:
    cors_origins.append(legacy_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(HTTPException)
def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail and "message" in exc.detail:
        payload = exc.detail
    else:
        error_map = {
            status.HTTP_400_BAD_REQUEST: ("validation_error", "Invalid request data"),
            status.HTTP_401_UNAUTHORIZED: ("unauthenticated", "Authentication required"),
            status.HTTP_403_FORBIDDEN: ("forbidden", "Access denied"),
        }
        error, message = error_map.get(exc.status_code, ("http_error", str(exc.detail)))
        payload = {"error": error, "message": message}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "validation_error", "message": "Invalid request data"},
    )


app.include_router(auth_router)
app.include_router(dashboards_router)
app.include_router(orders_router)
