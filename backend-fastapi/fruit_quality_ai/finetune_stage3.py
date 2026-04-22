"""
Stage 3 fine-tuning — squeeze out the last accuracy gains.

Loads the best checkpoint from Stage 2 and continues training with an
extremely low LR (1e-6). At this point the model is already well-converged;
this stage makes only tiny adjustments without risking catastrophic forgetting.

Usage:
    python finetune_stage3.py
    python finetune_stage3.py --epochs 30 --lr 5e-7
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import CosineAnnealingLR

import config
from data.dataset import get_dataloaders
from models.classifier import build_model
from utils.helpers import get_device, set_seed, plot_training_history

STAGE3_LR = 1e-6
STAGE3_EPOCHS = 20
PATIENCE = 8


def run_stage3(lr: float = STAGE3_LR, num_epochs: int = STAGE3_EPOCHS) -> None:
    set_seed(42)
    device = get_device()

    checkpoint_path = config.CHECKPOINT_DIR / "best_model.pth"
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"No checkpoint found at {checkpoint_path}. Run training first.")

    print(f"\n{'═'*60}")
    print(f"  STAGE 3 — Ultra-fine tuning")
    print(f"  LR={lr}  Epochs={num_epochs}")
    print(f"  Loading: {checkpoint_path}")
    print(f"{'═'*60}\n")

    train_loader, val_loader, _ = get_dataloaders()

    model = build_model(pretrained=False)
    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    model.to(device)

    criterion = nn.CrossEntropyLoss(label_smoothing=config.LABEL_SMOOTHING)
    optimizer = Adam(model.parameters(), lr=lr, weight_decay=config.WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=num_epochs, eta_min=1e-8)

    best_val_loss = float("inf")
    patience_counter = 0
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}

    for epoch in range(1, num_epochs + 1):
        # ── Train ──────────────────────────────────────────────────────────────
        model.train()
        t_loss, t_correct, t_total = 0.0, 0, 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            out = model(images)
            loss = criterion(out, labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            t_loss += loss.item() * images.size(0)
            t_correct += (out.argmax(1) == labels).sum().item()
            t_total += images.size(0)

        # ── Validate ───────────────────────────────────────────────────────────
        model.eval()
        v_loss, v_correct, v_total = 0.0, 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                out = model(images)
                loss = criterion(out, labels)
                v_loss += loss.item() * images.size(0)
                v_correct += (out.argmax(1) == labels).sum().item()
                v_total += images.size(0)

        scheduler.step()

        train_loss = t_loss / t_total
        train_acc  = t_correct / t_total
        val_loss   = v_loss / v_total
        val_acc    = v_correct / v_total

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)

        print(
            f"[Stage3] Epoch {epoch:03d}/{num_epochs} "
            f"| train_loss={train_loss:.4f}  train_acc={train_acc:.4f} "
            f"| val_loss={val_loss:.4f}  val_acc={val_acc:.4f}"
        )

        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), checkpoint_path)
            print(f"  ✓ checkpoint saved (val_acc={val_acc:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"  [Early stopping] No improvement for {PATIENCE} epochs.")
                break

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_training_history(history, config.RESULTS_DIR / "stage3_history.png")
    print(f"\n[Stage3] Done. Best checkpoint updated → {checkpoint_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lr", type=float, default=STAGE3_LR)
    parser.add_argument("--epochs", type=int, default=STAGE3_EPOCHS)
    args = parser.parse_args()
    run_stage3(lr=args.lr, num_epochs=args.epochs)
