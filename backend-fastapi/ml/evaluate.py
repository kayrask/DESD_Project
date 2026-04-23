"""
Evaluation script — run after training to get full metrics, fairness analysis,
and optional multi-architecture comparison.

Usage (from backend-fastapi/):

    # Evaluate the single production model
    python -m ml.evaluate --data_dir "ml/Fruit And Vegetable Diseases Dataset"

    # Compare MobileNetV2 vs ResNet18 side-by-side
    python -m ml.evaluate --data_dir "ml/Fruit And Vegetable Diseases Dataset" --compare

Outputs
-------
- Classification report (precision / recall / F1 per class)
- Confusion matrix PNG → ml/saved_models/confusion_matrix.png
- Fairness metrics (per-class FPR, FNR, equalized-odds gap)
- Updated ml/saved_models/model_metrics.json with all metrics
- When --compare: comparative table of all evaluated models
"""

import argparse
import json
import os
import pathlib
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from torch.utils.data import DataLoader

from ml.data.preprocess import build_splits, SEED, VAL_SPLIT
from ml.model import load_model

# ── Paths ──────────────────────────────────────────────────────────────────────
MODELS_DIR = pathlib.Path(__file__).parent / "saved_models"
MODEL_PATH = MODELS_DIR / "quality_classifier.pt"
CM_SAVE_PATH = MODELS_DIR / "confusion_matrix.png"
METRICS_PATH = MODELS_DIR / "model_metrics.json"

BATCH_SIZE = 32
_IN_DOCKER = pathlib.Path("/.dockerenv").exists()
NUM_WORKERS = 0 if (os.name == "nt" or _IN_DOCKER) else 2


# ── Confusion matrix visualisation ────────────────────────────────────────────

def _save_confusion_matrix(cm: np.ndarray, save_path: pathlib.Path, title: str = "") -> None:
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.colorbar(im, ax=ax)
    classes = ["Healthy", "Rotten"]
    tick_marks = range(len(classes))
    ax.set_xticks(tick_marks)
    ax.set_yticks(tick_marks)
    ax.set_xticklabels(classes)
    ax.set_yticklabels(classes)
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
    ax.set_ylabel("Actual label")
    ax.set_xlabel("Predicted label")
    ax.set_title(title or "Confusion Matrix – Quality Classifier")
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  Confusion matrix saved → {save_path}")


# ── Fairness metrics ───────────────────────────────────────────────────────────

def compute_fairness_metrics(labels: np.ndarray, preds: np.ndarray) -> dict:
    """
    Compute per-class fairness metrics and equalized-odds gap.

    Fairness framing
    ----------------
    The two 'groups' here are the product classes: Healthy (0) and Rotten (1).
    A fair classifier should not systematically disadvantage one class —
    concretely, producers of genuinely healthy produce should not face a
    disproportionately high false-rotten rate (FPR), which would unfairly
    damage their reputation.

    Metrics
    -------
    FPR (False Positive Rate) for Healthy class:
        P(predict Rotten | actual Healthy) — healthy wrongly flagged as rotten.
        High FPR harms honest producers.

    FNR (False Negative Rate) for Rotten class:
        P(predict Healthy | actual Rotten) — rotten produce missed.
        High FNR is a food-safety risk (the class-weighted loss addresses this).

    Equalized Odds Gap:
        |FPR_Healthy - FNR_Rotten|  — 0 = perfectly balanced error rates.
        Measures whether the model distributes its errors evenly or biases
        toward one type of mistake.

    Producer Parity Check:
        The model uses only image features; it has no access to producer
        identity.  Systematic per-producer bias would require per-producer
        validation data.  The equalized-odds gap on Healthy vs Rotten serves
        as a proxy fairness check in the absence of producer-labelled test data.
    """
    cm = confusion_matrix(labels, preds)
    tn, fp, fn, tp = cm.ravel()

    fpr_healthy = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr_rotten = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    tpr_healthy = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    tpr_rotten = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    equalized_odds_gap = abs(fpr_healthy - fnr_rotten)

    return {
        "fpr_healthy": round(fpr_healthy, 4),
        "fnr_rotten": round(fnr_rotten, 4),
        "tpr_healthy_specificity": round(tpr_healthy, 4),
        "tpr_rotten_recall": round(tpr_rotten, 4),
        "equalized_odds_gap": round(equalized_odds_gap, 4),
        "fairness_verdict": (
            "PASS — equalized-odds gap ≤ 0.10"
            if equalized_odds_gap <= 0.10
            else "REVIEW — equalized-odds gap > 0.10, investigate class-level errors"
        ),
    }


# ── Core evaluation function ───────────────────────────────────────────────────

def _build_val_loader(data_dir: str):
    _, val_set, _, _ = build_splits(data_dir)
    print(f"  Evaluating on {len(val_set)} held-out samples ({VAL_SPLIT:.0%} split, seed={SEED})")
    return DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)


def evaluate_model(
    model_path: pathlib.Path,
    data_dir: str,
    arch: str = "mobilenetv2",
    save_cm: bool = True,
    cm_path: pathlib.Path | None = None,
) -> dict:
    """
    Evaluate a single model checkpoint.  Returns a metrics dict.

    Args:
        model_path: Path to the .pt checkpoint.
        data_dir:   Dataset root (same structure as train.py).
        arch:       Architecture name matching the checkpoint.
        save_cm:    Whether to write the confusion-matrix PNG.
        cm_path:    Override confusion-matrix save path.

    Returns:
        dict with accuracy, precision, recall, F1, AUC-ROC, fairness metrics.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(str(model_path), device=device, arch=arch)
    loader = _build_val_loader(data_dir)

    all_preds, all_labels, all_probs = [], [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            probs = torch.softmax(outputs, dim=1)[:, 1].cpu().numpy()
            preds = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
            all_probs.extend(probs)

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    all_probs = np.array(all_probs)

    print(f"\n── Classification Report [{arch}] {'─' * 40}")
    report = classification_report(
        all_labels, all_preds,
        target_names=["Healthy", "Rotten"],
        output_dict=True,
    )
    print(classification_report(all_labels, all_preds, target_names=["Healthy", "Rotten"]))

    cm = confusion_matrix(all_labels, all_preds)
    print("Confusion matrix (rows=actual, cols=predicted):")
    print("             Healthy  Rotten")
    print(f"  Healthy    {cm[0,0]:>7}  {cm[0,1]:>6}")
    print(f"  Rotten     {cm[1,0]:>7}  {cm[1,1]:>6}")

    try:
        auc = roc_auc_score(all_labels, all_probs)
    except Exception:
        auc = None

    if save_cm:
        target_cm_path = cm_path or CM_SAVE_PATH
        _save_confusion_matrix(cm, target_cm_path, title=f"Confusion Matrix – {arch}")

    healthy_mask = all_labels == 0
    hit_rate = (all_preds[healthy_mask] == 0).mean() if healthy_mask.any() else 0.0
    print(f"\n  Hit-rate (healthy correctly identified): {hit_rate:.3f}")

    fairness = compute_fairness_metrics(all_labels, all_preds)
    print("\n── Fairness Metrics ─────────────────────────────────────────")
    print(f"  FPR Healthy (healthy → wrongly rotten): {fairness['fpr_healthy']:.3f}")
    print(f"  FNR Rotten  (rotten  → missed):         {fairness['fnr_rotten']:.3f}")
    print(f"  Equalized-Odds Gap:                     {fairness['equalized_odds_gap']:.3f}")
    print(f"  Verdict: {fairness['fairness_verdict']}")

    tn, fp, fn, tp = cm.ravel()
    metrics = {
        "arch": arch,
        "accuracy": round(report["accuracy"], 4),
        "precision": round(report["weighted avg"]["precision"], 4),
        "recall": round(report["weighted avg"]["recall"], 4),
        "f1_score": round(report["weighted avg"]["f1-score"], 4),
        "auc_roc": round(auc, 4) if auc is not None else None,
        "hit_rate_healthy": round(hit_rate, 4),
        "confusion_matrix": {
            "true_positive": int(tp),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
        },
        "fairness": fairness,
    }
    return metrics


# ── Single-model entry point ───────────────────────────────────────────────────

def evaluate(data_dir: str) -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No trained model at {MODEL_PATH}. Run ml/train.py first.")

    metrics = evaluate_model(MODEL_PATH, data_dir, arch="mobilenetv2")

    output = {
        "model_version": "mobilenetv2-v1",
        "updated_at": date.today().isoformat(),
        **metrics,
        "notes": "Generated by ml/evaluate.py. Run ml/evaluate.py --compare for multi-arch comparison.",
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Metrics saved → {METRICS_PATH}")


# ── Multi-model comparison entry point ────────────────────────────────────────

def compare_models(data_dir: str) -> None:
    """
    Evaluate every architecture that has a saved checkpoint and print a
    side-by-side comparison table.  Results are written to
    ml/saved_models/experiments/comparison.json.

    This provides the comparative evidence required to justify the choice
    of MobileNetV2 as the production model.
    """
    candidates = [
        ("mobilenetv2", MODEL_PATH),
        ("resnet18", MODELS_DIR / "resnet18_classifier.pt"),
    ]
    experiments_dir = MODELS_DIR / "experiments"
    if experiments_dir.exists():
        for pt in sorted(experiments_dir.glob("*.pt")):
            arch = "mobilenetv2" if "mobilenetv2" in pt.stem else (
                   "resnet18" if "resnet18" in pt.stem else None)
            if arch:
                candidates.append((arch, pt))

    results = []
    for arch, path in candidates:
        if not path.exists():
            print(f"  [skip] No checkpoint for {arch} at {path}")
            continue
        print(f"\n{'═'*60}")
        print(f"  Evaluating: {arch}  ({path.name})")
        cm_path = MODELS_DIR / f"confusion_matrix_{arch}.png"
        metrics = evaluate_model(path, data_dir, arch=arch, cm_path=cm_path)
        metrics["checkpoint"] = str(path)
        results.append(metrics)

    if not results:
        print("No checkpoints found to compare.")
        return

    print(f"\n{'═'*60}")
    print(f"{'Architecture':<18} {'Accuracy':>8} {'Precision':>10} {'Recall':>8} {'F1':>8} {'AUC':>8} {'EOGap':>8}")
    print("─" * 70)
    for r in results:
        auc = f"{r['auc_roc']:.4f}" if r.get("auc_roc") else "  N/A "
        print(
            f"{r['arch']:<18} {r['accuracy']:>8.4f} {r['precision']:>10.4f} "
            f"{r['recall']:>8.4f} {r['f1_score']:>8.4f} {auc:>8} "
            f"{r['fairness']['equalized_odds_gap']:>8.4f}"
        )

    experiments_dir.mkdir(parents=True, exist_ok=True)
    comp_path = experiments_dir / "comparison.json"
    with open(comp_path, "w") as f:
        json.dump({"evaluated_at": date.today().isoformat(), "models": results}, f, indent=2)
    print(f"\n  Comparison saved → {comp_path}")

    best = max(results, key=lambda r: r["f1_score"])
    print(f"\n  Best model by F1: {best['arch']} (F1={best['f1_score']:.4f})")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate quality classifier")
    parser.add_argument("--data_dir", required=True, help="Path to dataset root folder")
    parser.add_argument("--compare", action="store_true",
                        help="Compare all available model checkpoints side-by-side")
    args = parser.parse_args()

    if args.compare:
        compare_models(args.data_dir)
    else:
        evaluate(args.data_dir)
