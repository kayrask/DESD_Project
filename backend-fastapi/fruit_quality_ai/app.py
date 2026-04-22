"""
Lightweight FastAPI service — Fruit & Vegetable Quality Assessment API.

The AI component is the main priority; this service layer is intentionally
minimal. It exposes one prediction endpoint and one explanation retrieval
endpoint, making it easy to integrate into a wider DESD system later.

Usage:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
    # or
    python main.py --mode serve
"""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import config
from inference.predictor import QualityPredictor

# ── App lifecycle ──────────────────────────────────────────────────────────────

_predictor: QualityPredictor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the model at startup so the first request is not slow."""
    global _predictor
    _predictor = QualityPredictor.from_checkpoint()
    print("[API] Model loaded and ready.")
    yield
    # Teardown (nothing required here).


app = FastAPI(
    title="Fruit & Vegetable Quality Assessment API",
    description=(
        "AI-powered quality grading for the Bristol Regional Food Network. "
        "Upload a produce image to receive a grade, recommendation, and "
        "Grad-CAM explainability heatmap."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

UPLOAD_DIR = config.BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post(
    "/predict",
    summary="Assess fruit or vegetable quality from an uploaded image",
    response_description="JSON quality assessment with grade and recommendation",
)
async def predict(file: UploadFile = File(...)):
    """
    Upload a JPEG or PNG image of a fruit or vegetable.

    Returns a JSON object containing:
    - `predicted_class` — the recognised product and condition
    - `confidence` — model softmax probability
    - `quality_score` — continuous score in [0, 1]
    - `grade` — A, B, or C
    - `recommendation` — business action
    - `reasoning` — plain-English explanation of the grade decision
    - `explanation_path` — filename of the Grad-CAM heatmap (fetch via /explanation/{filename})
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"

    try:
        tmp_path.write_bytes(await file.read())
        result = _predictor.predict(str(tmp_path))
        return JSONResponse(content=result.to_dict())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get(
    "/explanation/{filename}",
    summary="Retrieve a Grad-CAM explanation image by filename",
)
async def get_explanation(filename: str):
    """Return a previously generated Grad-CAM visualisation as a PNG."""
    path = config.XAI_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Explanation image not found.")
    return FileResponse(path, media_type="image/png")


@app.get("/health", summary="Service health check")
async def health():
    return {
        "status": "ok",
        "backbone": config.BACKBONE,
        "num_classes": config.NUM_CLASSES,
        "class_names": config.CLASS_NAMES,
    }
