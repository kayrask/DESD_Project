"""
Evaluation script – run after training to get precision, recall, F1, confusion matrix.

Usage (from backend-fastapi/):
    python -m ml.evaluate --data_dir "../Fruit And Vegetable Diseases Dataset"

Evaluates on a held-out 20% test split (same seed as training so there is
zero overlap with the training data).  Prints per-class metrics and saves a
confusion matrix PNG to ml/saved_models/confusion_matrix.png.

Author (ai-eval): Member 2
Evidence prefix: ai-eval
"""

import argparse
import os
import pathlib

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — safe inside Docker/CI
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader, random_split
from torchvision import transforms

from ml.model import load_model
from ml.train import HealthyRottenDataset, SEED

MODEL_PATH = pathlib.Path(__file__).parent / "saved_models" / "quality_classifier.pt"
CM_SAVE_PATH = pathlib.Path(__file__).parent / "saved_models" / "confusion_matrix.png"
IMG_SIZE = 224
BATCH_SIZE = 32
VAL_SPLIT = 0.2   # must match the fraction used in train.py

_IN_DOCKER = pathlib.Path("/.dockerenv").exists()
NUM_WORKERS = 0 if (os.name == "nt" or _IN_DOCKER) else 2


def _save_confusion_matrix(cm: np.ndarray, save_path: pathlib.Path) -> None:
    """Save a labelled confusion matrix as a PNG file."""
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.colorbar(im, ax=ax)

    classes = ["Healthy", "Rotten"]
    tick_marks = range(len(classes))
    ax.set_xticks(tick_marks)
    ax.set_yticks(tick_marks)
    ax.set_xticklabels(classes)
    ax.set_yticklabels(classes)

    # Annotate each cell with its count
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j, i, str(cm[i, j]),
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "black",
            )

    ax.set_ylabel("Actual label")
    ax.set_xlabel("Predicted label")
    ax.set_title("Confusion Matrix – Quality Classifier")
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  Confusion matrix saved → {save_path}")


def evaluate(data_dir: str) -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No trained model at {MODEL_PATH}. Run ml/train.py first.")

    tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # ── Reproduce the exact same train/val split used during training ──────────
    # Using the same seed and split fraction ensures the test set has ZERO
    # overlap with the training data, giving honest, unbiased metrics.
    full_dataset = HealthyRottenDataset(root=data_dir, transform=tf)
    n_val = max(1, int(VAL_SPLIT * len(full_dataset)))
    n_train = len(full_dataset) - n_val
    _, val_set = random_split(
        full_dataset,
        [n_train, n_val],
        generator=torch.Generator().manual_seed(SEED),
    )

    print(f"Evaluating on {len(val_set)} held-out samples ({VAL_SPLIT:.0%} split, seed={SEED})")

    loader = DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(str(MODEL_PATH), device=device)

    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            preds = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)

    print("\n── Classification Report ─────────────────────────────────")
    print(classification_report(all_labels, all_preds, target_names=["Healthy", "Rotten"]))

    cm = confusion_matrix(all_labels, all_preds)
    print("Confusion matrix (rows=actual, cols=predicted):")
    print(f"             Healthy  Rotten")
    print(f"  Healthy    {cm[0,0]:>7}  {cm[0,1]:>6}")
    print(f"  Rotten     {cm[1,0]:>7}  {cm[1,1]:>6}")

    # Save confusion matrix PNG (used as evidence in the technical report)
    _save_confusion_matrix(cm, CM_SAVE_PATH)

    # Hit-rate: fraction of healthy samples correctly identified as healthy
    healthy_mask = all_labels == 0
    hit_rate = (all_preds[healthy_mask] == 0).mean() if healthy_mask.any() else 0.0
    print(f"\nHit-rate (healthy correctly identified): {hit_rate:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate quality classifier on held-out val split")
    parser.add_argument("--data_dir", required=True, help="Path to dataset root folder")
    args = parser.parse_args()
    evaluate(args.data_dir)
