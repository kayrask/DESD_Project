"""Training script – run this ONCE to produce quality_classifier.pt.

Usage (from backend-fastapi/):
    python -m ml.train --data_dir "ml/Fruit And Vegetable Diseases Dataset" --warmup_epochs 3 --finetune_epochs 7

Dataset structure:

- This script trains a **binary** classifier: class 0 = healthy/fresh, class 1 = rotten.
- It supports common folder naming patterns used by public datasets:
    - ``<Item>__Healthy`` / ``<Item>__Rotten`` (Kaggle produce disease/freshness datasets)
    - ``Healthy`` / ``Rotten``
    - ``Fresh`` / ``Rotten``

Training strategy (two-phase progressive fine-tuning):

  Phase 1 – Warmup (warmup_epochs):
      Only the classifier head is trained. The MobileNetV2 feature extractor
      is fully frozen. High LR is safe here since only 2 layers update.

  Phase 2 – Fine-tune (finetune_epochs):
      The last 3 feature blocks are unfrozen and trained at 10x lower LR
      so their ImageNet weights adapt gradually to produce-domain features
      without catastrophic forgetting.

Responsible AI:
  - Class-weighted loss (Rotten weight=2.0) penalises missed rotten produce
    more than missed healthy produce — a food-safety design decision.
  - CosineAnnealingLR provides smooth convergence across both phases.
  - Best model saved by val_acc; backup of previous best kept.

The trained model is saved to ml/saved_models/quality_classifier.pt.

Author (ai-model): Member 3
Evidence prefix: ai-model
"""

import argparse
import os
import pathlib
import shutil
import time

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

from ml.model import build_model, unfreeze_top_layers

# ── Constants ─────────────────────────────────────────────────────────────────
SAVE_PATH   = pathlib.Path(__file__).parent / "saved_models" / "quality_classifier.pt"
BACKUP_PATH = pathlib.Path(__file__).parent / "saved_models" / "quality_classifier_prev.pt"
IMG_SIZE    = 224
BATCH_SIZE  = 32
SEED        = 42
_IN_DOCKER  = pathlib.Path("/.dockerenv").exists()
NUM_WORKERS = 0 if (os.name == "nt" or _IN_DOCKER) else 2

# Class weights: penalise Rotten→Healthy errors twice as much.
# Rationale: classifying rotten produce as healthy is a food-safety risk;
# the asymmetric cost is an intentional responsible-AI design decision.
CLASS_WEIGHTS = [1.0, 2.0]   # [Healthy, Rotten]


def get_transforms():
    """
    Return (train_tf, val_tf) transform pipelines.

    Training augmentations are chosen to mimic real-world produce photography
    conditions: varied lighting (ColorJitter), orientation (flips, rotation),
    and partial occlusion (RandomErasing).  Val/inference uses only resize +
    normalise so metrics are not inflated by augmentation luck.
    """
    train_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(20),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.05),
        transforms.RandomGrayscale(p=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.1, scale=(0.02, 0.1)),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    return train_tf, val_tf


class HealthyRottenDataset(torch.utils.data.Dataset):
    """
    Wraps a torchvision ImageFolder, remapping class indices so that
    any folder containing 'Healthy'/'Fresh' maps to label 0 (Healthy)
    and any folder containing 'Rotten' maps to label 1 (Rotten).

    Supports dataset layouts:
      - <Fruit>__Healthy / <Fruit>__Rotten
      - Healthy / Rotten
      - Fresh / Rotten
    """

    def __init__(self, root: str, transform=None):
        self._inner = datasets.ImageFolder(root=root, transform=transform)
        self._remap = {}
        for class_name, idx in self._inner.class_to_idx.items():
            normalized = class_name.strip().lower()
            if "healthy" in normalized or "fresh" in normalized:
                self._remap[idx] = 0
            elif "rotten" in normalized:
                self._remap[idx] = 1
            else:
                raise ValueError(
                    f"Unrecognized class folder name for binary mapping: {class_name!r}. "
                    "Expected folder names containing 'Healthy'/'Fresh' or 'Rotten'."
                )

    def __len__(self):
        return len(self._inner)

    def __getitem__(self, index):
        image, label = self._inner[index]
        return image, self._remap[label]


def _validate_epoch(model, loader, device):
    """Run one validation pass; return accuracy."""
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            preds = model(images).argmax(dim=1)
            correct += (preds == labels).sum().item()
            total   += labels.size(0)
    return correct / total if total else 0.0


def train(
    data_dir: str,
    warmup_epochs: int,
    finetune_epochs: int,
    lr: float,
    log_every: int,
    unfreeze_n: int,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    total_epochs = warmup_epochs + finetune_epochs
    print(f"Training on {device}  |  {warmup_epochs} warmup + {finetune_epochs} fine-tune = {total_epochs} total epochs")
    print(f"Class weights: Healthy={CLASS_WEIGHTS[0]}, Rotten={CLASS_WEIGHTS[1]} (food-safety weighting)")

    train_tf, val_tf = get_transforms()

    # Two dataset instances with separate transforms — same deterministic index split.
    train_dataset = HealthyRottenDataset(root=data_dir, transform=train_tf)
    val_dataset   = HealthyRottenDataset(root=data_dir, transform=val_tf)

    n_val   = max(1, int(0.2 * len(train_dataset)))
    n_train = len(train_dataset) - n_val
    indices = torch.randperm(
        len(train_dataset), generator=torch.Generator().manual_seed(SEED)
    ).tolist()
    train_indices, val_indices = indices[:n_train], indices[n_train:]

    train_set = Subset(train_dataset, train_indices)
    val_set   = Subset(val_dataset,   val_indices)

    print(f"Dataset: {n_train} train / {n_val} val samples")

    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True,  num_workers=NUM_WORKERS)
    val_loader   = DataLoader(val_set,   batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)

    # Load starting weights.
    # If a previous checkpoint exists, start from it (avoids re-downloading
    # ImageNet weights and gives a better starting point than random init).
    # Otherwise fall back to pretrained=True (requires internet).
    if SAVE_PATH.exists():
        print(f"Resuming from existing checkpoint: {SAVE_PATH}")
        model = build_model(num_classes=2, pretrained=False).to(device)
        model.load_state_dict(torch.load(str(SAVE_PATH), map_location=device, weights_only=True))
    else:
        print("No existing checkpoint found — using ImageNet pretrained weights.")
        model = build_model(num_classes=2, pretrained=True).to(device)

    # Class-weighted loss — Rotten class penalised 2x for food-safety reasons.
    weights   = torch.tensor(CLASS_WEIGHTS, dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)

    # ── Phase 1: warmup — only train the classifier head ─────────────────────
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=warmup_epochs, eta_min=lr / 20
    )

    best_val_acc = 0.0

    for epoch in range(1, total_epochs + 1):

        # ── Switch to fine-tune phase after warmup ────────────────────────────
        if epoch == warmup_epochs + 1:
            print(f"\n── Phase 2: fine-tuning top {unfreeze_n} feature blocks at LR={lr/10:.2e} ──")
            unfreeze_top_layers(model, n=unfreeze_n)
            optimizer = torch.optim.Adam([
                {"params": model.classifier.parameters(),       "lr": lr / 10},
                {"params": list(model.features[-unfreeze_n:].parameters()), "lr": lr / 100},
            ])
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=finetune_epochs, eta_min=lr / 1000
            )

        # ── Train one epoch ───────────────────────────────────────────────────
        model.train()
        running_loss, correct, total = 0.0, 0, 0
        epoch_start  = time.time()
        batches_seen = 0

        for images, labels in train_loader:
            batches_seen += 1
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss    = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            preds         = outputs.argmax(dim=1)
            correct      += (preds == labels).sum().item()
            total        += labels.size(0)

            if log_every and (batches_seen % log_every == 0):
                elapsed   = time.time() - epoch_start
                avg_batch = elapsed / batches_seen
                eta_sec   = int(max(0, len(train_loader) - batches_seen) * avg_batch)
                print(
                    f"  [epoch {epoch}/{total_epochs}] batch {batches_seen}/{len(train_loader)} "
                    f"loss={loss.item():.4f} acc={correct/total:.3f} "
                    f"ETA~{eta_sec//60}m{eta_sec%60:02d}s"
                )

        train_acc  = correct / total
        train_loss = running_loss / total

        val_acc = _validate_epoch(model, val_loader, device)
        scheduler.step()

        phase_label = "warmup  " if epoch <= warmup_epochs else "finetune"
        print(
            f"Epoch {epoch:>2}/{total_epochs} [{phase_label}]  "
            f"loss={train_loss:.4f}  train_acc={train_acc:.3f}  val_acc={val_acc:.3f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Keep a backup of the previous best in case of regression.
            if SAVE_PATH.exists():
                shutil.copy2(SAVE_PATH, BACKUP_PATH)
            torch.save(model.state_dict(), SAVE_PATH)
            print(f"  ✓ New best val_acc={val_acc:.3f} — model saved → {SAVE_PATH}")

    print(f"\nTraining complete. Best val accuracy: {best_val_acc:.3f}")
    print(f"Model saved to: {SAVE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train quality classifier (two-phase progressive fine-tuning)")
    parser.add_argument("--data_dir",        required=True,          help="Path to dataset root folder")
    parser.add_argument("--warmup_epochs",   type=int, default=3,    help="Epochs to train head only (default 3)")
    parser.add_argument("--finetune_epochs", type=int, default=7,    help="Epochs to fine-tune top feature blocks (default 7)")
    parser.add_argument("--lr",              type=float, default=1e-3, help="Initial learning rate (default 1e-3)")
    parser.add_argument("--unfreeze_n",      type=int, default=3,    help="Number of top feature blocks to unfreeze in phase 2 (default 3)")
    parser.add_argument("--log_every",       type=int, default=50,   help="Print progress every N batches (0 disables)")
    args = parser.parse_args()
    train(
        data_dir=args.data_dir,
        warmup_epochs=args.warmup_epochs,
        finetune_epochs=args.finetune_epochs,
        lr=args.lr,
        log_every=args.log_every,
        unfreeze_n=args.unfreeze_n,
    )
