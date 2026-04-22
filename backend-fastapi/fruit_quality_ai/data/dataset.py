"""
Dataset loading utilities for fruit and vegetable quality classification.

Assumed folder layout on disk:

    data/raw/
        train/
            fresh_apple/  img1.jpg  img2.jpg ...
            rotten_apple/ ...
            ...
        val/              (optional — auto-created if absent)
        test/             (optional — auto-created if absent)

If only a `train/` folder exists the module automatically creates stratified
val and test splits using the ratios defined in config.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import torch
from torch.utils.data import DataLoader, Dataset, Subset, random_split
from torchvision.datasets import ImageFolder

from config import (
    RAW_DATA_DIR, IMAGE_SIZE, BATCH_SIZE, NUM_WORKERS,
    VALIDATION_SPLIT, TEST_SPLIT, CLASS_NAMES,
)
from data.transforms import get_train_transforms, get_val_transforms


def _verify_classes(dataset: ImageFolder) -> None:
    """Warn if the dataset on disk diverges from the class list in config."""
    found = set(dataset.classes)
    expected = set(CLASS_NAMES)
    if extra := found - expected:
        print(f"[Dataset] Warning: unexpected classes found in data: {extra}")
    if missing := expected - found:
        print(f"[Dataset] Warning: expected classes missing from data: {missing}")


class _TransformSubset(Dataset):
    """Wraps a Subset and applies a different transform, allowing train/val/test
    to share the same underlying ImageFolder but use different augmentations."""

    def __init__(self, subset: Subset, transform) -> None:
        self.subset = subset
        self.transform = transform

    def __len__(self) -> int:
        return len(self.subset)

    def __getitem__(self, idx):
        image, label = self.subset.dataset.imgs[self.subset.indices[idx]]
        from PIL import Image
        image = Image.open(image).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label


def load_datasets(
    data_dir: Path = RAW_DATA_DIR,
    image_size: int = IMAGE_SIZE,
) -> Tuple[Dataset, Dataset, Dataset]:
    """
    Return (train, val, test) datasets ready for DataLoader wrapping.

    If pre-split folders exist on disk they are loaded directly.
    Otherwise a single train/ folder is split automatically.
    """
    train_dir = data_dir / "train"
    val_dir = data_dir / "val"
    test_dir = data_dir / "test"

    train_tf = get_train_transforms(image_size)
    val_tf = get_val_transforms(image_size)

    if val_dir.exists() and test_dir.exists():
        train_ds = ImageFolder(train_dir, transform=train_tf)
        val_ds = ImageFolder(val_dir, transform=val_tf)
        test_ds = ImageFolder(test_dir, transform=val_tf)
        _verify_classes(train_ds)
    else:
        # Load everything from train/ then split, applying correct transforms
        # to each partition via the _TransformSubset wrapper.
        base_ds = ImageFolder(train_dir)
        _verify_classes(base_ds)

        n_total = len(base_ds)
        n_test = int(n_total * TEST_SPLIT)
        n_val = int(n_total * VALIDATION_SPLIT)
        n_train = n_total - n_val - n_test

        train_sub, val_sub, test_sub = random_split(
            base_ds,
            [n_train, n_val, n_test],
            generator=torch.Generator().manual_seed(42),
        )
        train_ds = _TransformSubset(train_sub, train_tf)
        val_ds = _TransformSubset(val_sub, val_tf)
        test_ds = _TransformSubset(test_sub, val_tf)

        print(f"[Dataset] Auto-split → train: {n_train}  val: {n_val}  test: {n_test}")

    return train_ds, val_ds, test_ds


def get_dataloaders(
    data_dir: Path = RAW_DATA_DIR,
    image_size: int = IMAGE_SIZE,
    batch_size: int = BATCH_SIZE,
    num_workers: int = NUM_WORKERS,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """Build DataLoaders for all three splits."""
    train_ds, val_ds, test_ds = load_datasets(data_dir, image_size)

    # pin_memory only works on CUDA; MPS and CPU silently ignore or warn.
    _kw = dict(num_workers=num_workers, pin_memory=torch.cuda.is_available())
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, **_kw)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, **_kw)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, **_kw)

    print(
        f"[DataLoader] Sizes → train: {len(train_ds)}  "
        f"val: {len(val_ds)}  test: {len(test_ds)}"
    )
    return train_loader, val_loader, test_loader


def get_class_names(data_dir: Path = RAW_DATA_DIR) -> Dict[int, str]:
    """Return index→class-name mapping derived from the train folder, or from config."""
    train_dir = data_dir / "train"
    if not train_dir.exists():
        return {i: name for i, name in enumerate(CLASS_NAMES)}
    ds = ImageFolder(train_dir)
    return {v: k for k, v in ds.class_to_idx.items()}
