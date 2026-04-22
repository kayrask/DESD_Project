"""
Inference module – loaded by quality_service.py at runtime.

Responsible for:
  1. Loading the trained MobileNetV2 model (once, cached in memory).
  2. Pre-processing uploaded images to the correct tensor format.
  3. Running inference and returning confidence scores.
  4. Computing interpretable Color / Size / Ripeness scores from image pixels.
  5. Generating Grad-CAM heatmaps for Explainable AI (XAI).

Fallback chain (used when no trained model file exists):
  1. KMeans colour clustering (unsupervised ML — Task 1 baseline)
  2. Simple greenness heuristic (zero dependencies beyond PIL/numpy)

Author (ai-integration): Kayra
Evidence prefix: ai-integration
"""

from __future__ import annotations

import base64
import io
import pathlib

MODEL_PATH = pathlib.Path(__file__).parent / "saved_models" / "quality_classifier.pt"
IMG_SIZE = 224

# Module-level cache — model is loaded only once per process.
_model = None
_device = "cpu"


# ── Model loading ─────────────────────────────────────────────────────────────

def _load_model_once():
    global _model, _device
    if _model is not None:
        return _model
    import torch
    from ml.model import load_model
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = load_model(str(MODEL_PATH), device=_device)
    return _model


def reload_model():
    """Force the in-memory model cache to reload from disk on next inference call.
    Called after an AI engineer uploads a new .pt file via the admin panel."""
    global _model
    _model = None


def _preprocess(image_bytes: bytes):
    """Convert raw image bytes to a normalised [1, 3, 224, 224] tensor."""
    import torch
    from PIL import Image
    from torchvision import transforms

    tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return tf(img).unsqueeze(0)


# ── Interpretable image-level feature extraction ─────────────────────────────

def _compute_image_scores(image_bytes: bytes) -> dict:
    """
    Compute interpretable quality scores directly from image pixels.

    These scores are derived independently of the CNN and provide the
    'explainable' breakdown shown in the XAI panel.

    color_score   – HSV-based freshness indicator:
                    high green/yellow → fresh; high brown → rotten.
    ripeness_score – Surface texture smoothness:
                    low edge density → smoother surface → fresher produce.
    size_score    – Subject presence in frame:
                    ratio of centre-crop variance to background variance.
    """
    from PIL import Image
    import numpy as np

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
    arr = np.array(img, dtype=np.float32)
    r = arr[:, :, 0] / 255.0
    g = arr[:, :, 1] / 255.0
    b = arr[:, :, 2] / 255.0

    # ── Color score ──────────────────────────────────────────────────────────
    cmax = np.maximum(np.maximum(r, g), b)
    delta = cmax - np.minimum(np.minimum(r, g), b) + 1e-6
    saturation = np.where(cmax > 0, delta / cmax, 0.0)

    # Brown pixels: R dominant over G and B; moderate saturation
    brown_mask = (r > g * 1.15) & (r > b * 1.15) & (saturation > 0.15)
    # Fresh pixels: green at least equal to red; decent saturation; not too dark
    fresh_mask = (g >= r * 0.85) & (saturation > 0.10) & (cmax > 0.15)

    total = float(r.size)
    brown_ratio = float(brown_mask.sum()) / total
    fresh_ratio = float(fresh_mask.sum()) / total

    color_score = float(np.clip(50.0 + (fresh_ratio - brown_ratio) * 100.0, 10.0, 100.0))

    # ── Ripeness score ───────────────────────────────────────────────────────
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gx = float(np.abs(gray[:, 1:] - gray[:, :-1]).mean())
    gy = float(np.abs(gray[1:, :] - gray[:-1, :]).mean())
    edge_density = (gx + gy) / 2.0
    # Lower edge density (smoother surface) correlates with freshness.
    # Typical edge density range: 5–25; map to 20–100.
    ripeness_score = float(np.clip(100.0 - (edge_density / 15.0) * 50.0, 20.0, 100.0))

    # ── Size score ───────────────────────────────────────────────────────────
    gray_n = gray / 255.0
    centre = gray_n[32:96, 32:96]
    corners = np.concatenate([
        gray_n[:20, :20].ravel(),
        gray_n[:20, -20:].ravel(),
        gray_n[-20:, :20].ravel(),
        gray_n[-20:, -20:].ravel(),
    ])
    centre_var = float(centre.var())
    corner_var = float(corners.var()) + 1e-6
    size_score = float(np.clip(
        50.0 + (centre_var / (corner_var + centre_var)) * 50.0, 40.0, 100.0
    ))

    return {
        "color_score": round(color_score, 1),
        "size_score": round(size_score, 1),
        "ripeness_score": round(ripeness_score, 1),
    }


# ── Grading ───────────────────────────────────────────────────────────────────

def _grade_from_scores(color: float, size: float, ripeness: float) -> tuple[str, bool]:
    """
    Apply the case-study grading thresholds.

    Grade A: Color ≥ 85, Size ≥ 90, Ripeness ≥ 80
    Grade B: Color ≥ 75, Size ≥ 80, Ripeness ≥ 70
    Grade C: otherwise
    """
    if color >= 85 and size >= 90 and ripeness >= 80:
        return "A", True
    elif color >= 75 and size >= 80 and ripeness >= 70:
        return "B", True
    else:
        return "C", False


# ── XAI: natural-language explanation ────────────────────────────────────────

def _build_explanation(grade: str, color: float, size: float, ripeness: float) -> str:
    """
    Construct a plain-language explanation of the grade decision.

    This is the textual XAI output — it explains which dimension(s) drove
    the grade and what they mean for the produce.
    """
    parts = []

    if color >= 85:
        parts.append("excellent colour uniformity indicating optimal freshness")
    elif color >= 75:
        parts.append("acceptable colour with minor discolouration detected")
    else:
        parts.append("notable discolouration or browning detected")

    if size >= 90:
        parts.append("uniform shape and size consistent with premium quality")
    elif size >= 80:
        parts.append("adequate size characteristics with minor irregularities")
    else:
        parts.append("irregular shape or insufficient subject fill detected")

    if ripeness >= 80:
        parts.append("smooth surface texture indicating optimal ripeness")
    elif ripeness >= 70:
        parts.append("surface texture within acceptable ripeness range")
    else:
        parts.append("surface irregularities suggest over-ripeness or rot")

    grade_labels = {"A": "Premium (Grade A)", "B": "Standard (Grade B)", "C": "Below standard (Grade C)"}
    return f"{grade_labels[grade]} — {'; '.join(parts)}."


# ── XAI: Grad-CAM heatmap ─────────────────────────────────────────────────────

def _grad_cam_heatmap(model, tensor, image_bytes: bytes) -> str | None:
    """
    Generate a Grad-CAM saliency map overlaid on the original image.

    Grad-CAM weights the last convolutional feature maps by the gradient
    of the Healthy-class score, producing a coarse localisation map that
    shows which image regions drove the prediction.

    Returns a base64-encoded PNG (ready for use as a data: URI), or None
    if generation fails.

    Reference: Selvaraju et al., "Grad-CAM: Visual Explanations from Deep
    Networks via Gradient-based Localization", ICCV 2017.
    """
    import numpy as np
    from PIL import Image

    try:
        # Hook onto the last convolutional block of MobileNetV2
        target_layer = model.features[-1]
        activations: dict = {}
        gradients: dict = {}

        def fwd_hook(module, inp, out):
            activations["v"] = out.detach()

        def bwd_hook(module, grad_in, grad_out):
            gradients["v"] = grad_out[0].detach()

        h_fwd = target_layer.register_forward_hook(fwd_hook)
        h_bwd = target_layer.register_full_backward_hook(bwd_hook)

        try:
            # Fresh forward pass with gradient tracking
            t = tensor.clone().requires_grad_(True)
            logits = model(t)
            model.zero_grad()
            # Backpropagate through the Healthy-class score (class 0)
            logits[0, 0].backward()

            acts = activations["v"].cpu().numpy()[0]   # [C, H, W]
            grads = gradients["v"].cpu().numpy()[0]    # [C, H, W]

            # Global average pool gradients → channel weights
            weights = grads.mean(axis=(1, 2))          # [C]
            cam = np.zeros(acts.shape[1:], dtype=np.float32)
            for i, w in enumerate(weights):
                cam += w * acts[i]

            cam = np.maximum(cam, 0)   # ReLU
            if cam.max() > 0:
                cam = cam / cam.max()  # Normalise to [0, 1]

            # Upsample to 224×224
            cam_img = Image.fromarray((cam * 255).astype(np.uint8)).resize(
                (IMG_SIZE, IMG_SIZE), Image.BILINEAR
            )
            cam_arr = np.array(cam_img, dtype=np.float32) / 255.0

            # Apply hot colormap: black → red → yellow → white
            red   = np.clip(cam_arr * 3.0,       0.0, 1.0)
            green = np.clip(cam_arr * 3.0 - 1.0, 0.0, 1.0)
            blue  = np.clip(cam_arr * 3.0 - 2.0, 0.0, 1.0)
            heat  = np.stack([red, green, blue], axis=-1)
            heat_img = Image.fromarray((heat * 255).astype(np.uint8)).convert("RGB")

            # Blend with resized original image
            orig = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(
                (IMG_SIZE, IMG_SIZE), Image.BILINEAR
            )
            blended = Image.blend(orig, heat_img, alpha=0.45)

            buf = io.BytesIO()
            blended.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")

        finally:
            h_fwd.remove()
            h_bwd.remove()

    except Exception:
        return None


# ── Fallback: KMeans clustering (Task 1 — unsupervised baseline) ──────────────

def _kmeans_fallback(image_bytes: bytes) -> dict:
    """
    Unsupervised ML fallback used when no trained model is available.

    Clusters pixel colours with KMeans; the proportion of 'green' vs 'brown'
    cluster members estimates freshness confidence.  Returns the same dict
    shape as the CNN path so the rest of the system is unaffected.
    """
    from PIL import Image
    import numpy as np
    from sklearn.cluster import KMeans

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
    arr = np.array(img, dtype=np.float32)
    pixels = arr.reshape(-1, 3)

    rng = np.random.default_rng(42)
    sample = pixels[rng.choice(pixels.shape[0], size=min(5000, pixels.shape[0]), replace=False)]

    kmeans = KMeans(n_clusters=3, n_init="auto", random_state=42)
    labels = kmeans.fit_predict(sample)
    centers = kmeans.cluster_centers_

    green_idx = int(np.argmax(centers[:, 1]))
    brown_scores = (centers[:, 0] - centers[:, 2]) - (centers[:, 1] * 0.25)
    brown_idx = int(np.argmax(brown_scores))

    green_prop = float(np.mean(labels == green_idx))
    brown_prop = float(np.mean(labels == brown_idx))
    cnn_conf = float(np.clip(green_prop - brown_prop * 0.8 + 0.5, 0.0, 1.0))

    # Blend KMeans confidence with pixel-level feature analysis
    img_scores = _compute_image_scores(image_bytes)
    w_cnn, w_img = 0.4, 0.6
    color_s    = round(img_scores["color_score"]    * w_img + cnn_conf * 100 * w_cnn, 1)
    size_s     = round(img_scores["size_score"]     * w_img + cnn_conf * 100 * w_cnn, 1)
    ripeness_s = round(img_scores["ripeness_score"] * w_img + cnn_conf * 100 * w_cnn, 1)
    grade, is_healthy = _grade_from_scores(color_s, size_s, ripeness_s)

    return {
        "grade": grade,
        "color_score": color_s,
        "size_score": size_s,
        "ripeness_score": ripeness_s,
        "model_confidence": round(cnn_conf, 4),
        "is_healthy": is_healthy,
        "model_version": "kmeans-fallback-v1",
        "xai_heatmap": None,
        "xai_explanation": _build_explanation(grade, color_s, size_s, ripeness_s),
    }


# ── Public entry point ────────────────────────────────────────────────────────

def classify_image(image_bytes: bytes, explain: bool = False) -> dict:
    """
    Classify a produce image as Healthy / Rotten and return quality scores.

    Args:
        image_bytes: Raw bytes of the uploaded image.
        explain:     If True, generate a Grad-CAM heatmap for XAI.
                     Adds a small overhead (~50–100 ms on CPU).

    Returns a dict with:
        grade              – "A", "B", or "C"
        color_score        – colour uniformity score 0–100
        size_score         – shape/subject-fill score 0–100
        ripeness_score     – surface texture score 0–100
        model_confidence   – CNN softmax probability for Healthy class (0–1)
        is_healthy         – bool (confidence ≥ 0.5)
        model_version      – string identifier stored with each assessment
        xai_heatmap        – base64 PNG string or None
        xai_explanation    – plain-language grade rationale
    """
    if not MODEL_PATH.exists():
        try:
            return _kmeans_fallback(image_bytes)
        except Exception:
            # Minimal heuristic when scikit-learn is unavailable
            from PIL import Image
            import numpy as np

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
            arr = np.array(img, dtype=np.float32)
            g = arr[:, :, 1] / 255.0
            r = arr[:, :, 0] / 255.0
            b = arr[:, :, 2] / 255.0
            greenness = float(g.mean())
            brownness = float(np.clip(r - b, 0, None).mean())
            cnn_conf = float(np.clip(greenness - brownness * 0.5, 0.0, 1.0))

            img_scores = _compute_image_scores(image_bytes)
            cs = round(img_scores["color_score"] * 0.5 + cnn_conf * 100 * 0.5, 1)
            ss = round(img_scores["size_score"]  * 0.5 + cnn_conf * 100 * 0.5, 1)
            rs = round(img_scores["ripeness_score"] * 0.5 + cnn_conf * 100 * 0.5, 1)
            grade, is_healthy = _grade_from_scores(cs, ss, rs)
            return {
                "grade": grade,
                "color_score": cs,
                "size_score": ss,
                "ripeness_score": rs,
                "model_confidence": round(cnn_conf, 4),
                "is_healthy": is_healthy,
                "model_version": "heuristic-fallback-v1",
                "xai_heatmap": None,
                "xai_explanation": _build_explanation(grade, cs, ss, rs),
            }

    import torch
    model = _load_model_once()
    tensor = _preprocess(image_bytes).to(_device)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)[0]

    healthy_confidence = float(probs[0])

    # Blend CNN confidence with independent pixel-level analysis.
    # CNN captures semantic patterns; image scores capture visual attributes.
    img_scores = _compute_image_scores(image_bytes)
    w_cnn, w_img = 0.6, 0.4

    color_s    = round(img_scores["color_score"]    * w_img + healthy_confidence * 100 * w_cnn, 1)
    size_s     = round(img_scores["size_score"]     * w_img + healthy_confidence * 100 * w_cnn, 1)
    ripeness_s = round(img_scores["ripeness_score"] * w_img + healthy_confidence * 100 * w_cnn, 1)

    grade, is_healthy = _grade_from_scores(color_s, size_s, ripeness_s)

    # GradCAM requires a fresh forward pass with gradient tracking
    xai_heatmap = _grad_cam_heatmap(model, tensor, image_bytes) if explain else None

    return {
        "grade": grade,
        "color_score": color_s,
        "size_score": size_s,
        "ripeness_score": ripeness_s,
        "model_confidence": round(healthy_confidence, 4),
        "is_healthy": is_healthy,
        "model_version": "mobilenetv2-v1",
        "xai_heatmap": xai_heatmap,
        "xai_explanation": _build_explanation(grade, color_s, size_s, ripeness_s),
    }
