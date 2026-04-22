"""
Inference module – loaded by quality_service.py at runtime.

Model priority chain:
  1. fruit_quality_ai — EfficientNet-B0, 28-class, TTA, trained checkpoint
  2. MobileNetV2 (legacy) — binary Healthy/Rotten, quality_classifier.pt
  3. KMeans colour clustering — unsupervised fallback (no trained weights needed)
  4. Greenness heuristic — zero-dependency last resort

The public interface (classify_image) is unchanged — all callers continue
to receive the same dict regardless of which backend is active.

Author (ai-integration): Kayra
New model integration: Nazli (fruit_quality_ai EfficientNet-B0)
"""

from __future__ import annotations

import base64
import io
import pathlib
import sys

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE = pathlib.Path(__file__).parent
_FRUIT_AI_DIR   = _BASE.parent / "fruit_quality_ai"
_CHECKPOINT     = _FRUIT_AI_DIR / "checkpoints" / "best_model.pth"
_LEGACY_MODEL   = _BASE / "saved_models" / "quality_classifier.pt"
IMG_SIZE = 224

# Module-level caches
_fruit_predictor = None   # QualityPredictor instance (new model)
_legacy_model    = None   # MobileNetV2 (old model)
_device = "cpu"


# ── New model: fruit_quality_ai EfficientNet-B0 ───────────────────────────────

def _load_fruit_predictor():
    """Load the EfficientNet-B0 QualityPredictor (once, cached)."""
    global _fruit_predictor
    if _fruit_predictor is not None:
        return _fruit_predictor
    if not _CHECKPOINT.exists():
        return None
    try:
        import torch

        # Use a temporary sys.path extension rather than permanently inserting
        # at index 0, to avoid shadowing top-level Django modules named 'config'.
        _fai = str(_FRUIT_AI_DIR)
        _added = _fai not in sys.path
        if _added:
            sys.path.append(_fai)   # append, not insert(0)
        try:
            from models.classifier import build_model
            from inference.predictor import QualityPredictor
        finally:
            if _added:
                sys.path.remove(_fai)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Build with pretrained=False — checkpoint already has fine-tuned weights,
        # no need to download ImageNet weights on every cold start.
        model = build_model(pretrained=False)
        model.load_state_dict(torch.load(_CHECKPOINT, map_location=device, weights_only=True))
        model.eval()
        _fruit_predictor = QualityPredictor(
            model=model,
            device=device,
            generate_xai=True,
            xai_output_dir=_FRUIT_AI_DIR / "results" / "xai",
        )
        print(f"[Predictor] EfficientNet-B0 loaded from {_CHECKPOINT}")
        return _fruit_predictor
    except Exception as exc:
        print(f"[Predictor] Failed to load fruit_quality_ai model: {exc}")
        return None


def _fruit_classify(image_bytes: bytes, explain: bool) -> dict | None:
    """
    Run inference through the new EfficientNet-B0 model.

    Returns the standard classify_image dict, or None if the model
    couldn't be loaded so the caller can fall through to the legacy path.
    """
    import tempfile, os
    predictor = _load_fruit_predictor()
    if predictor is None:
        return None
    try:
        # QualityPredictor needs a file path — write bytes to a temp file
        suffix = ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            result = predictor.predict(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        # Read Grad-CAM PNG → base64 for the template <img> tag, then delete
        xai_heatmap = None
        if result.explanation_path:
            try:
                with open(result.explanation_path, "rb") as f:
                    raw = f.read()
                if explain:
                    xai_heatmap = base64.b64encode(raw).decode("utf-8")
                os.unlink(result.explanation_path)   # don't accumulate PNGs on disk
            except Exception:
                pass

        # Strip verbose dataset suffixes from class names for display
        _STRIP = "_fruit_and_vegetable_diseases_dataset"
        reasoning = result.reasoning.replace(_STRIP, "")
        predicted_class = result.predicted_class.replace(_STRIP, "").replace("_", " ").title()

        # Derive colour/size/ripeness from image pixels (independent of CNN)
        img_scores = _compute_image_scores(image_bytes)

        # Blend pixel scores with CNN quality_score for smoother output
        q = float(result.quality_score)          # 0.5–1.0 fresh, 0.0–0.5 rotten
        w_cnn, w_img = 0.65, 0.35
        color_s    = round(img_scores["color_score"]    * w_img + q * 100 * w_cnn, 1)
        size_s     = round(img_scores["size_score"]     * w_img + q * 100 * w_cnn, 1)
        ripeness_s = round(img_scores["ripeness_score"] * w_img + q * 100 * w_cnn, 1)

        is_healthy = result.condition == "fresh"

        return {
            "grade":            result.grade,
            "color_score":      color_s,
            "size_score":       size_s,
            "ripeness_score":   ripeness_s,
            "model_confidence": round(result.confidence, 4),
            "is_healthy":       is_healthy,
            "model_version":    "efficientnet-b0-v1",
            "predicted_class":  predicted_class,
            "xai_heatmap":      xai_heatmap,
            "xai_explanation":  reasoning,
        }
    except Exception:
        return None


# ── Legacy model: MobileNetV2 ─────────────────────────────────────────────────

def _load_legacy_once():
    global _legacy_model, _device
    if _legacy_model is not None:
        return _legacy_model
    import torch
    from ml.model import load_model
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _legacy_model = load_model(str(_LEGACY_MODEL), device=_device)
    return _legacy_model


def reload_model():
    """Force both model caches to reload (called after admin model upload)."""
    global _fruit_predictor, _legacy_model
    _fruit_predictor = None
    _legacy_model = None


def _preprocess(image_bytes: bytes):
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


# ── Pixel-level quality scores (architecture-independent) ─────────────────────

def _compute_image_scores(image_bytes: bytes) -> dict:
    from PIL import Image
    import numpy as np

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
    arr = np.array(img, dtype=np.float32)
    r = arr[:, :, 0] / 255.0
    g = arr[:, :, 1] / 255.0
    b = arr[:, :, 2] / 255.0

    cmax = np.maximum(np.maximum(r, g), b)
    delta = cmax - np.minimum(np.minimum(r, g), b) + 1e-6
    saturation = np.where(cmax > 0, delta / cmax, 0.0)
    brown_mask = (r > g * 1.15) & (r > b * 1.15) & (saturation > 0.15)
    fresh_mask = (g >= r * 0.85) & (saturation > 0.10) & (cmax > 0.15)
    total = float(r.size)
    color_score = float(
        np.clip(50.0 + (fresh_mask.sum() / total - brown_mask.sum() / total) * 100.0, 10.0, 100.0)
    )

    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gx = float(np.abs(gray[:, 1:] - gray[:, :-1]).mean())
    gy = float(np.abs(gray[1:, :] - gray[:-1, :]).mean())
    ripeness_score = float(np.clip(100.0 - ((gx + gy) / 2.0 / 15.0) * 50.0, 20.0, 100.0))

    gray_n = gray / 255.0
    centre = gray_n[32:96, 32:96]
    corners = np.concatenate([
        gray_n[:20, :20].ravel(), gray_n[:20, -20:].ravel(),
        gray_n[-20:, :20].ravel(), gray_n[-20:, -20:].ravel(),
    ])
    cv = float(centre.var())
    corner_v = float(corners.var()) + 1e-6
    size_score = float(np.clip(50.0 + (cv / (corner_v + cv)) * 50.0, 40.0, 100.0))

    return {
        "color_score":    round(color_score, 1),
        "size_score":     round(size_score, 1),
        "ripeness_score": round(ripeness_score, 1),
    }


def _grade_from_scores(color, size, ripeness):
    if color >= 85 and size >= 90 and ripeness >= 80:
        return "A", True
    if color >= 75 and size >= 80 and ripeness >= 70:
        return "B", True
    return "C", False


def _build_explanation(grade, color, size, ripeness):
    parts = []
    parts.append(
        "excellent colour uniformity" if color >= 85
        else "acceptable colour with minor discolouration" if color >= 75
        else "notable discolouration or browning detected"
    )
    parts.append(
        "uniform shape consistent with premium quality" if size >= 90
        else "adequate size with minor irregularities" if size >= 80
        else "irregular shape or insufficient subject fill"
    )
    parts.append(
        "smooth surface indicating optimal ripeness" if ripeness >= 80
        else "surface texture within acceptable range" if ripeness >= 70
        else "surface irregularities suggest over-ripeness or rot"
    )
    labels = {"A": "Premium (Grade A)", "B": "Standard (Grade B)", "C": "Below standard (Grade C)"}
    return f"{labels[grade]} — {'; '.join(parts)}."


def _grad_cam_heatmap(model, tensor, image_bytes):
    import numpy as np
    from PIL import Image
    try:
        target_layer = model.features[-1]
        activations, gradients = {}, {}
        h_fwd = target_layer.register_forward_hook(lambda m, i, o: activations.__setitem__("v", o.detach()))
        h_bwd = target_layer.register_full_backward_hook(lambda m, gi, go: gradients.__setitem__("v", go[0].detach()))
        try:
            t = tensor.clone().requires_grad_(True)
            logits = model(t)
            model.zero_grad()
            logits[0, 0].backward()
            acts = activations["v"].cpu().numpy()[0]
            grads = gradients["v"].cpu().numpy()[0]
            weights = grads.mean(axis=(1, 2))
            cam = np.maximum(np.sum(weights[:, None, None] * acts, axis=0), 0)
            if cam.max() > 0:
                cam /= cam.max()
            cam_img = Image.fromarray((cam * 255).astype(np.uint8)).resize((IMG_SIZE, IMG_SIZE), Image.BILINEAR)
            cam_arr = np.array(cam_img, dtype=np.float32) / 255.0
            red   = np.clip(cam_arr * 3.0, 0, 1)
            green = np.clip(cam_arr * 3.0 - 1.0, 0, 1)
            blue  = np.clip(cam_arr * 3.0 - 2.0, 0, 1)
            heat  = Image.fromarray((np.stack([red, green, blue], axis=-1) * 255).astype("uint8"))
            orig  = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((IMG_SIZE, IMG_SIZE))
            blended = Image.blend(orig, heat, alpha=0.45)
            buf = io.BytesIO()
            blended.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        finally:
            h_fwd.remove()
            h_bwd.remove()
    except Exception:
        return None


# ── KMeans fallback ───────────────────────────────────────────────────────────

def _kmeans_fallback(image_bytes):
    from PIL import Image
    import numpy as np
    from sklearn.cluster import KMeans

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
    pixels = np.array(img, dtype=np.float32).reshape(-1, 3)
    rng = np.random.default_rng(42)
    sample = pixels[rng.choice(pixels.shape[0], size=min(5000, pixels.shape[0]), replace=False)]
    km = KMeans(n_clusters=3, n_init="auto", random_state=42)
    labels = km.fit_predict(sample)
    centers = km.cluster_centers_
    green_idx = int(np.argmax(centers[:, 1]))
    brown_scores = (centers[:, 0] - centers[:, 2]) - centers[:, 1] * 0.25
    brown_idx = int(np.argmax(brown_scores))
    cnn_conf = float(np.clip(
        np.mean(labels == green_idx) - np.mean(labels == brown_idx) * 0.8 + 0.5, 0.0, 1.0
    ))
    img_scores = _compute_image_scores(image_bytes)
    w_cnn, w_img = 0.4, 0.6
    cs = round(img_scores["color_score"]    * w_img + cnn_conf * 100 * w_cnn, 1)
    ss = round(img_scores["size_score"]     * w_img + cnn_conf * 100 * w_cnn, 1)
    rs = round(img_scores["ripeness_score"] * w_img + cnn_conf * 100 * w_cnn, 1)
    grade, is_healthy = _grade_from_scores(cs, ss, rs)
    return {
        "grade": grade, "color_score": cs, "size_score": ss, "ripeness_score": rs,
        "model_confidence": round(cnn_conf, 4), "is_healthy": is_healthy,
        "model_version": "kmeans-fallback-v1", "xai_heatmap": None,
        "xai_explanation": _build_explanation(grade, cs, ss, rs),
    }


# ── Public entry point ────────────────────────────────────────────────────────

def classify_image(image_bytes: bytes, explain: bool = False) -> dict:
    """
    Classify a produce image and return quality scores.

    Model priority:
      1. EfficientNet-B0 (fruit_quality_ai) — if checkpoint exists
      2. MobileNetV2 (legacy quality_classifier.pt) — if checkpoint exists
      3. KMeans unsupervised fallback
      4. Greenness heuristic

    Returns dict with: grade, color_score, size_score, ripeness_score,
    model_confidence, is_healthy, model_version, xai_heatmap, xai_explanation.
    """
    # ── 1. Try new EfficientNet-B0 model ─────────────────────────────────────
    if _CHECKPOINT.exists():
        result = _fruit_classify(image_bytes, explain)
        if result is not None:
            return result

    # ── 2. Try legacy MobileNetV2 ─────────────────────────────────────────────
    if _LEGACY_MODEL.exists():
        try:
            import torch
            model = _load_legacy_once()
            tensor = _preprocess(image_bytes).to(_device)
            with torch.no_grad():
                logits = model(tensor)
                probs = torch.softmax(logits, dim=1)[0]
            healthy_conf = float(probs[0])
            img_scores = _compute_image_scores(image_bytes)
            w_cnn, w_img = 0.6, 0.4
            cs = round(img_scores["color_score"]    * w_img + healthy_conf * 100 * w_cnn, 1)
            ss = round(img_scores["size_score"]     * w_img + healthy_conf * 100 * w_cnn, 1)
            rs = round(img_scores["ripeness_score"] * w_img + healthy_conf * 100 * w_cnn, 1)
            grade, is_healthy = _grade_from_scores(cs, ss, rs)
            xai_heatmap = _grad_cam_heatmap(model, tensor, image_bytes) if explain else None
            return {
                "grade": grade, "color_score": cs, "size_score": ss, "ripeness_score": rs,
                "model_confidence": round(healthy_conf, 4), "is_healthy": is_healthy,
                "model_version": "mobilenetv2-v1", "xai_heatmap": xai_heatmap,
                "xai_explanation": _build_explanation(grade, cs, ss, rs),
            }
        except Exception:
            pass

    # ── 3. KMeans fallback ────────────────────────────────────────────────────
    try:
        return _kmeans_fallback(image_bytes)
    except Exception:
        pass

    # ── 4. Greenness heuristic (zero dependencies) ────────────────────────────
    from PIL import Image
    import numpy as np
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
    arr = np.array(img, dtype=np.float32)
    g = arr[:, :, 1] / 255.0
    r = arr[:, :, 0] / 255.0
    b = arr[:, :, 2] / 255.0
    cnn_conf = float(np.clip(g.mean() - np.clip(r - b, 0, None).mean() * 0.5, 0.0, 1.0))
    img_scores = _compute_image_scores(image_bytes)
    cs = round(img_scores["color_score"]    * 0.5 + cnn_conf * 100 * 0.5, 1)
    ss = round(img_scores["size_score"]     * 0.5 + cnn_conf * 100 * 0.5, 1)
    rs = round(img_scores["ripeness_score"] * 0.5 + cnn_conf * 100 * 0.5, 1)
    grade, is_healthy = _grade_from_scores(cs, ss, rs)
    return {
        "grade": grade, "color_score": cs, "size_score": ss, "ripeness_score": rs,
        "model_confidence": round(cnn_conf, 4), "is_healthy": is_healthy,
        "model_version": "heuristic-fallback-v1", "xai_heatmap": None,
        "xai_explanation": _build_explanation(grade, cs, ss, rs),
    }
