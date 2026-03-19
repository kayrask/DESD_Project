"""
Training script – run this ONCE to produce quality_classifier.pt.

Usage (from backend-fastapi/):
    python -m ml.train --data_dir "../Fruit And Vegetable Diseases Dataset" --epochs 10

The dataset folder must contain sub-folders named <Item>__Healthy and
<Item>__Rotten (exactly as downloaded from Kaggle).  All Healthy images
are treated as class 0 (healthy) and all Rotten images as class 1 (rotten).

The trained model is saved to ml/saved_models/quality_classifier.pt.

Author (ai-model): Member 3
Evidence prefix: ai-model
"""

import argparse
import os
import pathlib

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms

from ml.model import build_model

# ── Constants ────────────────────────────────────────────────────────────────
SAVE_PATH = pathlib.Path(__file__).parent / "saved_models" / "quality_classifier.pt"
IMG_SIZE = 224
BATCH_SIZE = 32
SEED = 42


def get_transforms():
    train_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
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
    any folder containing '__Healthy' maps to label 0 and '__Rotten' to 1.
    """

    def __init__(self, root: str, transform=None):
        self._inner = datasets.ImageFolder(root=root, transform=transform)
        # Build remap: original_idx -> binary label
        self._remap = {}
        for class_name, idx in self._inner.class_to_idx.items():
            self._remap[idx] = 0 if "Healthy" in class_name else 1

    def __len__(self):
        return len(self._inner)

    def __getitem__(self, index):
        image, label = self._inner[index]
        return image, self._remap[label]


def train(data_dir: str, epochs: int, lr: float):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Training on {device}")

    train_tf, val_tf = get_transforms()

    full_dataset = HealthyRottenDataset(root=data_dir, transform=train_tf)
    n_val = max(1, int(0.2 * len(full_dataset)))
    n_train = len(full_dataset) - n_val
    train_set, val_set = random_split(
        full_dataset, [n_train, n_val],
        generator=torch.Generator().manual_seed(SEED),
    )
    # Apply val transforms to val split
    val_set.dataset = HealthyRottenDataset(root=data_dir, transform=val_tf)

    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    model = build_model(num_classes=2, pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.5)

    best_val_acc = 0.0
    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        running_loss, correct, total = 0.0, 0, 0
        for images, labels in train_loader:
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

        train_acc = correct / total
        train_loss = running_loss / total

        # Validate
        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                preds = outputs.argmax(dim=1)
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)
        val_acc = val_correct / val_total

        scheduler.step()
        print(f"Epoch {epoch}/{epochs}  loss={train_loss:.4f}  train_acc={train_acc:.3f}  val_acc={val_acc:.3f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), SAVE_PATH)
            print(f"  ✓ Saved best model → {SAVE_PATH}")

    print(f"\nTraining complete. Best val accuracy: {best_val_acc:.3f}")
    print(f"Model saved to: {SAVE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train quality classifier")
    parser.add_argument("--data_dir", required=True, help="Path to dataset root folder")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()
    train(args.data_dir, args.epochs, args.lr)
