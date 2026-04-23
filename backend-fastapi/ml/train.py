"""Training script – run this to produce quality_classifier.pt.

Usage (from backend-fastapi/):
    # MobileNetV2 (production model)
    python -m ml.train --data_dir "ml/Fruit And Vegetable Diseases Dataset" --arch mobilenetv2

    # ResNet18 (baseline comparison)
    python -m ml.train --data_dir "ml/Fruit And Vegetable Diseases Dataset" --arch resnet18

    # Custom hyperparameters (for experimentation)
    python -m ml.train --data_dir "..." --arch mobilenetv2 --lr 5e-4 --warmup_epochs 5 --finetune_epochs 10

Dataset structure:
- Binary classifier: class 0 = healthy/fresh, class 1 = rotten.
- Supports folder naming: <Item>__Healthy / <Item>__Rotten, Healthy/Rotten, Fresh/Rotten.

Training strategy (two-phase progressive fine-tuning):

  Phase 1 – Warmup (warmup_epochs):
      Only the classifier head trains; the backbone is frozen.

  Phase 2 – Fine-tune (finetune_epochs):
      Top backbone blocks are unfrozen at 10x lower LR to adapt
      ImageNet weights to produce-domain features without catastrophic
      forgetting of learned low-level features.

Responsible AI:
  - Class-weighted loss (Rotten weight=2.0) penalises missed rotten produce
    more than missed healthy produce — a food-safety design decision.
  - CosineAnnealingLR provides smooth convergence across both phases.
  - Best model saved by val_acc; backup of previous best kept.

Experiment logging:
  Each run appends a record to ml/saved_models/experiments/runs.json,
  capturing architecture, hyperparameters, per-epoch metrics, and the
  final val_acc.  This log is the evidence base for comparative analysis
  and hyperparameter tuning claims.
"""

import argparse
import json
import os
import pathlib
import shutil
import time
from datetime import datetime

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.data.preprocess import (
    HealthyRottenDataset,
    build_splits,
    report_class_imbalance,
    scan_for_corrupt,
)
from ml.model import build_model_by_arch, unfreeze_top_layers_by_arch

# ── Constants ─────────────────────────────────────────────────────────────────
MODELS_DIR = pathlib.Path(__file__).parent / "saved_models"
SAVE_PATH = MODELS_DIR / "quality_classifier.pt"
BACKUP_PATH = MODELS_DIR / "quality_classifier_prev.pt"
EXPERIMENTS_DIR = MODELS_DIR / "experiments"
BATCH_SIZE = 32
_IN_DOCKER = pathlib.Path("/.dockerenv").exists()
NUM_WORKERS = 0 if (os.name == "nt" or _IN_DOCKER) else 2

# Class weights: penalise Rotten→Healthy errors twice as much.
# Rationale: classifying rotten produce as healthy is a food-safety risk;
# the asymmetric cost is an intentional responsible-AI design decision.
CLASS_WEIGHTS = [1.0, 2.0]   # [Healthy, Rotten]


def _validate_epoch(model, loader, device):
    """Run one validation pass; return accuracy."""
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            preds = model(images).argmax(dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
    return correct / total if total else 0.0


def _save_experiment(record: dict) -> None:
    """Append *record* to the runs log for later comparative analysis."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    runs_path = EXPERIMENTS_DIR / "runs.json"
    runs = []
    if runs_path.exists():
        with open(runs_path) as f:
            runs = json.load(f)
    runs.append(record)
    with open(runs_path, "w") as f:
        json.dump(runs, f, indent=2)
    print(f"  Experiment record saved → {runs_path}")


def train(
    data_dir: str,
    arch: str,
    warmup_epochs: int,
    finetune_epochs: int,
    lr: float,
    log_every: int,
    unfreeze_n: int,
    save_path: pathlib.Path | None = None,
):
    """
    Train a quality classifier and log the run for comparative analysis.

    Args:
        data_dir:        Path to dataset root.
        arch:            Architecture name ('mobilenetv2' or 'resnet18').
        warmup_epochs:   Epochs to train head only.
        finetune_epochs: Epochs for fine-tuning top backbone blocks.
        lr:              Initial learning rate.
        log_every:       Print progress every N batches (0 = silent).
        unfreeze_n:      Number of top backbone blocks to unfreeze in phase 2.
        save_path:       Override save destination (used by experiment.py).

    Returns:
        best_val_acc (float)
    """
    if save_path is None:
        save_path = SAVE_PATH
    backup_path = save_path.parent / (save_path.stem + "_prev.pt")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    total_epochs = warmup_epochs + finetune_epochs
    print(f"\n[{arch}] Training on {device}  |  {warmup_epochs} warmup + {finetune_epochs} fine-tune = {total_epochs} epochs")
    print(f"  LR={lr}  unfreeze_n={unfreeze_n}  class_weights={CLASS_WEIGHTS}")

    # ── Data pipeline: validate then split ───────────────────────────────────
    print("Scanning for corrupt images...")
    scan_for_corrupt(data_dir)

    train_set, val_set, n_train, n_val = build_splits(data_dir)
    print(f"  Dataset: {n_train} train / {n_val} val samples")

    # Report class imbalance on the full (un-split) dataset
    full_ds = HealthyRottenDataset(root=data_dir, transform=None)
    report_class_imbalance(full_ds)

    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True, num_workers=NUM_WORKERS)
    val_loader = DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)

    if save_path.exists():
        print(f"  Resuming from checkpoint: {save_path}")
        model = build_model_by_arch(arch, pretrained=False).to(device)
        model.load_state_dict(torch.load(str(save_path), map_location=device, weights_only=True))
    else:
        print("  No checkpoint — using ImageNet pretrained weights.")
        model = build_model_by_arch(arch, pretrained=True).to(device)

    weights = torch.tensor(CLASS_WEIGHTS, dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)

    # Phase 1: head-only warmup
    head_params = model.classifier.parameters() if arch == "mobilenetv2" else model.fc.parameters()
    optimizer = torch.optim.Adam(head_params, lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=warmup_epochs, eta_min=lr / 20
    )

    best_val_acc = 0.0
    epoch_log = []

    for epoch in range(1, total_epochs + 1):

        if epoch == warmup_epochs + 1:
            print(f"\n  ── Phase 2: fine-tuning top {unfreeze_n} blocks at LR={lr/10:.2e} ──")
            unfreeze_top_layers_by_arch(model, arch, n=unfreeze_n)
            head_params = model.classifier.parameters() if arch == "mobilenetv2" else model.fc.parameters()
            all_unfrozen = [p for p in model.parameters() if p.requires_grad and
                            id(p) not in {id(q) for q in head_params}]
            optimizer = torch.optim.Adam([
                {"params": list(head_params), "lr": lr / 10},
                {"params": all_unfrozen, "lr": lr / 100},
            ])
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=finetune_epochs, eta_min=lr / 1000
            )

        model.train()
        running_loss, correct, total = 0.0, 0, 0
        epoch_start = time.time()
        batches_seen = 0

        for images, labels in train_loader:
            batches_seen += 1
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            preds = outputs.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

            if log_every and (batches_seen % log_every == 0):
                elapsed = time.time() - epoch_start
                avg_batch = elapsed / batches_seen
                eta_sec = int(max(0, len(train_loader) - batches_seen) * avg_batch)
                print(
                    f"  [epoch {epoch}/{total_epochs}] batch {batches_seen}/{len(train_loader)} "
                    f"loss={loss.item():.4f} acc={correct/total:.3f} "
                    f"ETA~{eta_sec//60}m{eta_sec%60:02d}s"
                )

        train_acc = correct / total
        train_loss = running_loss / total
        val_acc = _validate_epoch(model, val_loader, device)
        scheduler.step()

        phase_label = "warmup  " if epoch <= warmup_epochs else "finetune"
        print(
            f"  Epoch {epoch:>2}/{total_epochs} [{phase_label}]  "
            f"loss={train_loss:.4f}  train_acc={train_acc:.3f}  val_acc={val_acc:.3f}"
        )
        epoch_log.append({
            "epoch": epoch,
            "phase": "warmup" if epoch <= warmup_epochs else "finetune",
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 4),
            "val_acc": round(val_acc, 4),
        })

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_path.parent.mkdir(parents=True, exist_ok=True)
            if save_path.exists():
                shutil.copy2(save_path, backup_path)
            torch.save(model.state_dict(), save_path)
            print(f"  ✓ New best val_acc={val_acc:.3f} — model saved → {save_path}")

    print(f"\n  Training complete. Best val accuracy: {best_val_acc:.3f}")

    # Log this run for comparative analysis
    _save_experiment({
        "run_id": datetime.utcnow().strftime("%Y%m%dT%H%M%S"),
        "arch": arch,
        "warmup_epochs": warmup_epochs,
        "finetune_epochs": finetune_epochs,
        "lr": lr,
        "unfreeze_n": unfreeze_n,
        "batch_size": BATCH_SIZE,
        "class_weights": CLASS_WEIGHTS,
        "n_train": n_train,
        "n_val": n_val,
        "best_val_acc": round(best_val_acc, 4),
        "epoch_log": epoch_log,
        "save_path": str(save_path),
    })

    return best_val_acc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train quality classifier (two-phase progressive fine-tuning)")
    parser.add_argument("--data_dir", required=True, help="Path to dataset root folder")
    parser.add_argument("--arch", default="mobilenetv2", choices=("mobilenetv2", "resnet18"),
                        help="Model architecture (default: mobilenetv2)")
    parser.add_argument("--warmup_epochs", type=int, default=3, help="Epochs to train head only (default 3)")
    parser.add_argument("--finetune_epochs", type=int, default=7, help="Epochs to fine-tune top blocks (default 7)")
    parser.add_argument("--lr", type=float, default=1e-3, help="Initial learning rate (default 1e-3)")
    parser.add_argument("--unfreeze_n", type=int, default=3, help="Top blocks to unfreeze in phase 2 (default 3)")
    parser.add_argument("--log_every", type=int, default=50, help="Print progress every N batches (0 disables)")
    args = parser.parse_args()
    train(
        data_dir=args.data_dir,
        arch=args.arch,
        warmup_epochs=args.warmup_epochs,
        finetune_epochs=args.finetune_epochs,
        lr=args.lr,
        log_every=args.log_every,
        unfreeze_n=args.unfreeze_n,
    )
