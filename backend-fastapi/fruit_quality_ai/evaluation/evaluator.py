"""
Evaluation module — test-set metrics, confusion matrix, and JSON report.

Computes accuracy, per-class precision / recall / F1, and produces a confusion
matrix image. All outputs are saved to results/ for inclusion in the report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)
import matplotlib.pyplot as plt

from config import RESULTS_DIR, CLASS_NAMES


def evaluate(
    model: nn.Module,
    test_loader: DataLoader,
    device: torch.device,
    class_names: List[str] = CLASS_NAMES,
    results_dir: Path = RESULTS_DIR,
) -> Dict:
    """
    Run inference on the full test set and compute classification metrics.

    Args:
        model:        Trained model (will be set to eval mode internally).
        test_loader:  DataLoader for the test split.
        device:       Torch device to run inference on.
        class_names:  Ordered list of class label strings.
        results_dir:  Directory where the confusion matrix and JSON report are saved.

    Returns:
        Dictionary with 'accuracy' and 'per_class' metrics.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    model.eval()

    all_preds: List[int] = []
    all_labels: List[int] = []

    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(device)
            outputs = model(images)
            preds = outputs.argmax(dim=1).cpu().tolist()
            all_preds.extend(preds)
            all_labels.extend(labels.tolist())

    # ── Metrics ────────────────────────────────────────────────────────────────
    accuracy = accuracy_score(all_labels, all_preds)
    report_dict = classification_report(
        all_labels, all_preds,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    report_str = classification_report(
        all_labels, all_preds,
        target_names=class_names,
        zero_division=0,
    )

    print(f"\n[Evaluation] Test Accuracy: {accuracy:.4f}\n")
    print(report_str)

    # ── Confusion matrix ───────────────────────────────────────────────────────
    cm = confusion_matrix(all_labels, all_preds)
    _plot_confusion_matrix(cm, class_names, results_dir / "confusion_matrix.png")

    # ── Persist JSON report ────────────────────────────────────────────────────
    # Includes the metadata the admin monitoring template expects
    # (dataset, samples, updated_at, model_version) so the bridge in
    # app/services/quality_service.py can surface it without extra glue.
    from datetime import date
    summary = {
        "model_version": "efficientnet-b0-v1",
        "accuracy": accuracy,
        "per_class": report_dict,
        "dataset": "Fruit & Vegetable Disease (Healthy vs Rotten)",
        "test_samples": len(all_labels),
        "updated_at": date.today().isoformat(),
    }
    report_path = results_dir / "evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[Evaluation] Report saved → {report_path}")

    return summary


def _plot_confusion_matrix(
    cm: np.ndarray,
    class_names: List[str],
    save_path: Path,
) -> None:
    n = len(class_names)
    fig, ax = plt.subplots(figsize=(max(6, n), max(5, n)))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
    disp.plot(ax=ax, xticks_rotation=45, colorbar=False)
    ax.set_title("Confusion Matrix — Fruit & Vegetable Quality Classifier")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"[Evaluation] Confusion matrix saved → {save_path}")
