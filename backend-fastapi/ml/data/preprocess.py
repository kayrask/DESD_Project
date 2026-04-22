"""
Data pipeline for the DESD quality classifier.

Extracted from ml/train.py so training and evaluation share one canonical
dataset loader, transform definitions, validation checks, and split logic.

Public API
----------
get_transforms()               -> (train_tf, val_tf)
build_splits(data_dir, ...)    -> (train_set, val_set, n_train, n_val)
scan_for_corrupt(data_dir)     -> list[pathlib.Path]   (empty = all OK)
report_class_imbalance(ds)     -> dict
HealthyRottenDataset           (re-exported for backwards compat)
SEED, VAL_SPLIT, IMG_SIZE      constants
"""

import pathlib
from typing import Tuple

import torch
from torch.utils.data import Dataset, Subset
from torchvision import datasets, transforms

IMG_SIZE  = 224
SEED      = 42
VAL_SPLIT = 0.2


class HealthyRottenDataset(torch.utils.data.Dataset):
    """Wraps torchvision ImageFolder with a binary label remap.

    Any folder whose name contains 'Healthy' or 'Fresh' maps to label 0.
    Any folder whose name contains 'Rotten' maps to label 1.

    Supported dataset layouts:
      - <Fruit>__Healthy / <Fruit>__Rotten   (Kaggle produce disease sets)
      - Healthy / Rotten
      - Fresh / Rotten
    """

    def __init__(self, root: str, transform=None):
        self._inner = datasets.ImageFolder(root=root, transform=transform)
        self._remap: dict[int, int] = {}
        for class_name, idx in self._inner.class_to_idx.items():
            norm = class_name.strip().lower()
            if "healthy" in norm or "fresh" in norm:
                self._remap[idx] = 0
            elif "rotten" in norm:
                self._remap[idx] = 1
            else:
                raise ValueError(
                    f"Unrecognised class folder: {class_name!r}. "
                    "Expected folder names containing 'Healthy'/'Fresh' or 'Rotten'."
                )

    def __len__(self) -> int:
        return len(self._inner)

    def __getitem__(self, index):
        image, label = self._inner[index]
        return image, self._remap[label]


def get_transforms() -> Tuple:
    """Return (train_tf, val_tf) torchvision transform pipelines.

    Training augmentations simulate real-world produce photography conditions:
    varied lighting (ColorJitter), orientation (flips, rotation), and partial
    occlusion (RandomErasing). Validation uses only resize + normalise so
    metrics are not inflated by augmentation randomness.
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


def scan_for_corrupt(data_dir: str) -> list:
    """Walk data_dir and return paths of unreadable image files.

    PIL verify() catches partial/truncated images, not just missing files.
    Call this before training to get a clean dataset report.
    """
    from PIL import Image, UnidentifiedImageError

    corrupt = []
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
    for path in pathlib.Path(data_dir).rglob("*"):
        if path.suffix.lower() not in exts:
            continue
        try:
            with Image.open(path) as img:
                img.verify()
        except (UnidentifiedImageError, Exception):
            corrupt.append(path)

    if corrupt:
        print(f"  ⚠ Found {len(corrupt)} corrupt image(s):")
        for p in corrupt[:10]:
            print(f"    {p}")
        if len(corrupt) > 10:
            print(f"    ... and {len(corrupt) - 10} more")
    else:
        print(f"  ✓ No corrupt images found in {data_dir}")
    return corrupt


def report_class_imbalance(dataset: Dataset) -> dict:
    """Count Healthy (0) vs Rotten (1) labels and flag imbalance.

    Reads the underlying ImageFolder .samples list directly — no image
    loading — so it runs in milliseconds even on large datasets.
    """
    inner = getattr(dataset, "_inner", None)
    if inner is None:
        raise TypeError("Expected a HealthyRottenDataset instance.")

    remap = dataset._remap
    counts: dict[int, int] = {0: 0, 1: 0}
    for _, orig_label in inner.samples:
        mapped = remap.get(orig_label, orig_label)
        counts[mapped] = counts.get(mapped, 0) + 1

    total = sum(counts.values()) or 1
    ratio = counts[1] / counts[0] if counts[0] else float("inf")
    report = {
        "healthy": counts[0],
        "rotten":  counts[1],
        "total":   total,
        "rotten_ratio": round(ratio, 3),
        "imbalanced": ratio > 2.0 or ratio < 0.5,
    }
    if report["imbalanced"]:
        print(
            f"  ⚠ Class imbalance: Healthy={counts[0]}, Rotten={counts[1]}, "
            f"ratio={ratio:.2f}. Consider adjusting CLASS_WEIGHTS in train.py."
        )
    else:
        print(
            f"  ✓ Class balance OK: Healthy={counts[0]}, Rotten={counts[1]}, ratio={ratio:.2f}"
        )
    return report


def build_splits(
    data_dir: str,
    val_split: float = VAL_SPLIT,
    seed: int = SEED,
):
    """Load dataset from data_dir and return deterministic train/val subsets.

    Two separate dataset instances share the same file list but apply
    different transforms — train augmentation vs val-only normalise.

    Returns
    -------
    train_set, val_set, n_train, n_val
    """
    train_tf, val_tf = get_transforms()

    train_base = HealthyRottenDataset(root=data_dir, transform=train_tf)
    val_base   = HealthyRottenDataset(root=data_dir, transform=val_tf)

    n_val   = max(1, int(val_split * len(train_base)))
    n_train = len(train_base) - n_val

    indices = torch.randperm(
        len(train_base), generator=torch.Generator().manual_seed(seed)
    ).tolist()

    train_set = Subset(train_base, indices[:n_train])
    val_set   = Subset(val_base,   indices[n_train:])
    return train_set, val_set, n_train, n_val
