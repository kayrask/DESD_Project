"""
Two-stage training pipeline for maximum accuracy.

Stage 1 — Head only (backbone frozen):
    Fast convergence. A high learning rate trains the classification head
    without disturbing the pretrained feature extractor.

Stage 2 — Full fine-tuning (all layers unfrozen):
    Very low LR lets the backbone adapt its features to produce imagery
    without destroying the ImageNet representations it already learned.
    Cosine annealing ensures a smooth LR decay to the end of training.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from config import (
    WEIGHT_DECAY, EARLY_STOPPING_PATIENCE, LABEL_SMOOTHING,
    STAGE1_EPOCHS, STAGE2_EPOCHS, STAGE1_LR, STAGE2_LR,
    CHECKPOINT_DIR,
)
from models.classifier import freeze_backbone, unfreeze_backbone


class EarlyStopping:
    """Stop training when validation loss stops improving for `patience` epochs."""

    def __init__(self, patience: int = EARLY_STOPPING_PATIENCE, min_delta: float = 1e-4):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss: Optional[float] = None
        self.should_stop = False

    def reset(self) -> None:
        """Reset state between training stages."""
        self.counter = 0
        self.best_loss = None
        self.should_stop = False

    def step(self, val_loss: float) -> bool:
        if self.best_loss is None or val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        return self.should_stop


class Trainer:
    """
    Two-stage trainer for transfer learning.

    Stage 1 trains only the classification head with a high LR.
    Stage 2 unfreezes the full network and fine-tunes with a very low LR.
    Both stages use CosineAnnealingLR and label smoothing.
    """

    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        device: torch.device,
        backbone: str,
        checkpoint_dir: Path = CHECKPOINT_DIR,
        stage1_epochs: int = STAGE1_EPOCHS,
        stage2_epochs: int = STAGE2_EPOCHS,
        stage1_lr: float = STAGE1_LR,
        stage2_lr: float = STAGE2_LR,
        weight_decay: float = WEIGHT_DECAY,
        label_smoothing: float = LABEL_SMOOTHING,
        pretrained: bool = True,
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.backbone = backbone
        self.checkpoint_dir = checkpoint_dir
        self.stage1_epochs = stage1_epochs
        self.stage2_epochs = stage2_epochs
        self.stage1_lr = stage1_lr
        self.stage2_lr = stage2_lr
        self.weight_decay = weight_decay
        self.pretrained = pretrained

        # Label smoothing prevents the model from becoming overconfident,
        # which consistently improves generalisation on fine-grained tasks.
        self.criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)

        self.early_stopping = EarlyStopping()
        self.history: Dict[str, List[float]] = {
            "train_loss": [], "val_loss": [],
            "train_acc": [], "val_acc": [],
        }
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # ── Core epoch loop ────────────────────────────────────────────────────────

    def _run_epoch(self, loader: DataLoader, training: bool) -> tuple[float, float]:
        self.model.train(training)
        total_loss, correct, total = 0.0, 0, 0

        with torch.set_grad_enabled(training):
            for images, labels in loader:
                images, labels = images.to(self.device), labels.to(self.device)

                if training:
                    self.optimizer.zero_grad()

                outputs = self.model(images)
                loss = self.criterion(outputs, labels)

                if training:
                    loss.backward()
                    # Gradient clipping prevents exploding gradients during fine-tuning.
                    nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                    self.optimizer.step()

                total_loss += loss.item() * images.size(0)
                correct += (outputs.argmax(dim=1) == labels).sum().item()
                total += images.size(0)

        return total_loss / total, correct / total

    def _run_stage(self, num_epochs: int, stage_name: str) -> float:
        """Run one training stage. Returns best val loss achieved."""
        best_val_loss = float("inf")
        self.early_stopping.reset()

        for epoch in range(1, num_epochs + 1):
            t0 = time.time()
            train_loss, train_acc = self._run_epoch(self.train_loader, training=True)
            val_loss, val_acc = self._run_epoch(self.val_loader, training=False)
            self.scheduler.step()

            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_acc"].append(val_acc)

            elapsed = time.time() - t0
            print(
                f"[{stage_name}] Epoch {epoch:03d}/{num_epochs} "
                f"| train_loss={train_loss:.4f}  train_acc={train_acc:.4f} "
                f"| val_loss={val_loss:.4f}  val_acc={val_acc:.4f} "
                f"| {elapsed:.1f}s"
            )

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                self._save_checkpoint("best_model.pth")
                print(f"  ✓ checkpoint saved (val_acc={val_acc:.4f})")

            if self.early_stopping.step(val_loss):
                print(f"  [Early stopping] Triggered at epoch {epoch}.")
                break

        return best_val_loss

    # ── Public API ─────────────────────────────────────────────────────────────

    def train(self) -> Dict[str, List[float]]:
        """
        Run the two-stage training loop.

        If pretrained=False, skips Stage 1 (nothing to freeze) and runs
        a single stage with stage2_lr as the learning rate.
        """
        if self.pretrained:
            # ── Stage 1: head only ─────────────────────────────────────────────
            print(f"\n{'═'*60}")
            print(f"  STAGE 1 — Head training (backbone frozen)")
            print(f"  LR={self.stage1_lr}  Epochs={self.stage1_epochs}")
            print(f"{'═'*60}")
            freeze_backbone(self.model, self.backbone)
            self._setup_optimizer(self.stage1_lr, self.stage1_epochs)
            self._run_stage(self.stage1_epochs, "Stage1")

            # Load best head weights before unfreezing.
            self._load_checkpoint("best_model.pth")

            # ── Stage 2: full fine-tune ────────────────────────────────────────
            print(f"\n{'═'*60}")
            print(f"  STAGE 2 — Full fine-tuning (all layers)")
            print(f"  LR={self.stage2_lr}  Epochs={self.stage2_epochs}")
            print(f"{'═'*60}")
            unfreeze_backbone(self.model)
            self._setup_optimizer(self.stage2_lr, self.stage2_epochs)
            self._run_stage(self.stage2_epochs, "Stage2")
        else:
            # From-scratch: single stage, train everything with stage2_lr.
            print(f"\n{'═'*60}")
            print(f"  TRAINING FROM SCRATCH — all layers")
            print(f"{'═'*60}")
            self._setup_optimizer(self.stage2_lr, self.stage1_epochs + self.stage2_epochs)
            self._run_stage(self.stage1_epochs + self.stage2_epochs, "Train")

        return self.history

    def _setup_optimizer(self, lr: float, num_epochs: int) -> None:
        self.optimizer = Adam(
            filter(lambda p: p.requires_grad, self.model.parameters()),
            lr=lr,
            weight_decay=self.weight_decay,
        )
        # Cosine annealing smoothly reduces LR to near-zero by the final epoch,
        # avoiding the abrupt drops of StepLR which can destabilise late training.
        self.scheduler = CosineAnnealingLR(self.optimizer, T_max=num_epochs, eta_min=1e-7)

    def _save_checkpoint(self, filename: str) -> None:
        torch.save(self.model.state_dict(), self.checkpoint_dir / filename)

    def _load_checkpoint(self, filename: str) -> None:
        path = self.checkpoint_dir / filename
        self.model.load_state_dict(torch.load(path, map_location=self.device))
        print(f"  [Trainer] Loaded checkpoint: {path.name}")
