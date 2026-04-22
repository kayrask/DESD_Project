"""
Dataset setup script for the Kaggle dataset:
    "Fruit and Vegetable Disease (Healthy vs Rotten)"
    by muhammad0subhan
    https://www.kaggle.com/datasets/muhammad0subhan/fruit-and-vegetable-disease-healthy-vs-rotten

What this script does
─────────────────────
1. Downloads the dataset via kagglehub (cached after the first run).
2. Walks the downloaded folder tree to detect its structure automatically.
3. Copies images into the project's expected layout:
       data/raw/train/<class_name>/
       data/raw/val/<class_name>/
       data/raw/test/<class_name>/
4. Prints the CLASS_NAMES list so you can paste it into config.py,
   and optionally patches config.py automatically.

Usage
─────
    pip install kagglehub
    python setup_data.py              # copy + patch config.py
    python setup_data.py --dry-run    # just print what would happen
"""

from __future__ import annotations

import argparse
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
CONFIG_PATH = PROJECT_ROOT / "config.py"

VAL_SPLIT = 0.15
TEST_SPLIT = 0.15
RANDOM_SEED = 42

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

KAGGLE_DATASET = "muhammad0subhan/fruit-and-vegetable-disease-healthy-vs-rotten"


# ── Step 1: Download ──────────────────────────────────────────────────────────

def download_dataset() -> Path:
    """Download (or retrieve cached) dataset via kagglehub. Returns root path."""
    try:
        import kagglehub
    except ImportError:
        raise SystemExit(
            "[Setup] kagglehub is not installed.\n"
            "  Run: pip install kagglehub"
        )
    print(f"[Setup] Downloading dataset: {KAGGLE_DATASET}")
    path = kagglehub.dataset_download(KAGGLE_DATASET)
    print(f"[Setup] Dataset path: {path}")
    return Path(path)


# ── Step 2: Detect structure ───────────────────────────────────────────────────

def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def _normalise_class_name(name: str) -> str:
    """
    Convert whatever folder name the dataset uses into a clean snake_case label.

    Examples:
        "Apple__Fresh"   → "fresh_apple"
        "Rotten Banana"  → "rotten_banana"
        "Fresh-Orange"   → "fresh_orange"
        "apple/healthy"  → "fresh_apple"   (nested case handled by caller)
    """
    name = name.strip().lower()
    name = re.sub(r"[\s\-]+", "_", name)   # spaces / hyphens → underscore
    name = re.sub(r"_+", "_", name)        # collapse double underscores

    # Swap "product__condition" → "condition_product"
    # e.g. "apple__fresh" → parts = ["apple", "fresh"]
    parts = re.split(r"_{1,2}", name)
    if len(parts) == 2:
        a, b = parts
        condition_words = {"fresh", "healthy", "good", "rotten", "bad", "stale", "spoiled"}
        if b in condition_words:
            return f"{b}_{a}"    # already condition_product
        if a in condition_words:
            return f"{a}_{b}"    # swap to condition_product

    return name


def detect_class_folders(dataset_root: Path) -> dict[str, list[Path]]:
    """
    Auto-detect where the per-class image folders are inside the dataset.

    Handles three common layouts:
      A) dataset_root/train|valid|test/<class>/<images>
      B) dataset_root/<class>/<images>                    (flat)
      C) dataset_root/<product>/<condition>/<images>      (nested)

    Returns a dict mapping normalised class name → list of image Paths.
    """
    # Collect all image files and their depths.
    all_images = list(dataset_root.rglob("*"))
    all_images = [p for p in all_images if p.is_file() and _is_image(p)]

    if not all_images:
        raise FileNotFoundError(
            f"[Setup] No images found under {dataset_root}. "
            "Check the download path."
        )

    print(f"[Setup] Found {len(all_images)} images. Detecting folder layout...")

    # Print top-level structure to help with debugging.
    top_dirs = sorted({p.name for p in dataset_root.iterdir() if p.is_dir()})
    print(f"[Setup] Top-level folders: {top_dirs}")

    # ── Layout A: pre-split (train/valid/test at top level) ───────────────────
    split_names = {"train", "valid", "validation", "test"}
    top_level_names = {d.lower() for d in top_dirs}
    if top_level_names & split_names:
        # Use the training split to derive classes; ignore val/test here
        # (we'll re-split ourselves for consistency).
        train_root = None
        for candidate in ("train", "Train", "training"):
            if (dataset_root / candidate).exists():
                train_root = dataset_root / candidate
                break
        if train_root is None:
            # Fall back to whatever split folder exists.
            for d in dataset_root.iterdir():
                if d.is_dir():
                    train_root = d
                    break

        class_map: dict[str, list[Path]] = defaultdict(list)
        # Collect images from ALL splits so we can re-split cleanly.
        for split_dir in dataset_root.iterdir():
            if not split_dir.is_dir():
                continue
            for class_dir in split_dir.iterdir():
                if not class_dir.is_dir():
                    continue
                norm = _normalise_class_name(class_dir.name)
                class_map[norm].extend(
                    p for p in class_dir.iterdir() if _is_image(p)
                )
        if class_map:
            print("[Setup] Detected layout A (pre-split: train/valid/test).")
            return dict(class_map)

    # ── Layout C: nested <product>/<condition>/<images> ───────────────────────
    nested_map: dict[str, list[Path]] = defaultdict(list)
    for product_dir in dataset_root.iterdir():
        if not product_dir.is_dir():
            continue
        sub_dirs = [d for d in product_dir.iterdir() if d.is_dir()]
        for condition_dir in sub_dirs:
            images = [p for p in condition_dir.iterdir() if _is_image(p)]
            if images:
                norm = _normalise_class_name(
                    f"{condition_dir.name}_{product_dir.name}"
                )
                nested_map[norm].extend(images)
    if nested_map:
        print("[Setup] Detected layout C (nested: product/condition/images).")
        return dict(nested_map)

    # ── Layout B: flat <class>/<images> ───────────────────────────────────────
    flat_map: dict[str, list[Path]] = defaultdict(list)
    for class_dir in dataset_root.iterdir():
        if not class_dir.is_dir():
            continue
        images = [p for p in class_dir.iterdir() if _is_image(p)]
        if images:
            norm = _normalise_class_name(class_dir.name)
            flat_map[norm].extend(images)
    if flat_map:
        print("[Setup] Detected layout B (flat: class/images).")
        return dict(flat_map)

    raise RuntimeError(
        "[Setup] Could not detect a recognised folder layout. "
        "Inspect the dataset manually and adjust detect_class_folders()."
    )


# ── Step 3: Split and copy ────────────────────────────────────────────────────

def _split_files(
    files: list[Path],
    val_frac: float,
    test_frac: float,
    seed: int,
) -> tuple[list[Path], list[Path], list[Path]]:
    """Randomly split a file list into train / val / test."""
    rng = random.Random(seed)
    shuffled = files[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_test = max(1, int(n * test_frac))
    n_val = max(1, int(n * val_frac))
    test = shuffled[:n_test]
    val = shuffled[n_test: n_test + n_val]
    train = shuffled[n_test + n_val:]
    return train, val, test


def copy_to_project(
    class_map: dict[str, list[Path]],
    out_root: Path,
    val_frac: float = VAL_SPLIT,
    test_frac: float = TEST_SPLIT,
    dry_run: bool = False,
) -> list[str]:
    """
    Copy images into out_root/{train,val,test}/<class>/ with a stratified split.

    Returns the sorted list of class names (for config.py).
    """
    if not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)

    class_names = sorted(class_map.keys())
    totals = {"train": 0, "val": 0, "test": 0}

    for cls in class_names:
        files = class_map[cls]
        train_f, val_f, test_f = _split_files(files, val_frac, test_frac, RANDOM_SEED)

        for split_name, split_files in (
            ("train", train_f), ("val", val_f), ("test", test_f)
        ):
            dest_dir = out_root / split_name / cls
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
            for src in split_files:
                dest = dest_dir / src.name
                if not dry_run:
                    shutil.copy2(src, dest)
            totals[split_name] += len(split_files)
            if dry_run:
                print(f"  [dry-run] {split_name}/{cls}: {len(split_files)} images")

    print(
        f"\n[Setup] Split summary — "
        f"train: {totals['train']}  val: {totals['val']}  test: {totals['test']}"
    )
    return class_names


# ── Step 4: Patch config.py ───────────────────────────────────────────────────

def patch_config(class_names: list[str], config_path: Path, dry_run: bool = False) -> None:
    """Replace the CLASS_NAMES list in config.py with the detected classes."""
    text = config_path.read_text()

    new_list = (
        "[\n"
        + "".join(f'    "{cls}",\n' for cls in class_names)
        + "]"
    )
    # Replace the existing CLASS_NAMES = [...] block (handles multiline).
    patched = re.sub(
        r"CLASS_NAMES\s*=\s*\[[^\]]*\]",
        f"CLASS_NAMES = {new_list}",
        text,
        flags=re.DOTALL,
    )
    # Also update NUM_CLASSES to match.
    patched = re.sub(
        r"NUM_CLASSES\s*=\s*\S+",
        f"NUM_CLASSES = {len(class_names)}",
        patched,
    )

    if dry_run:
        print(f"\n[dry-run] Would write CLASS_NAMES = {class_names}")
        print(f"[dry-run] Would set NUM_CLASSES = {len(class_names)}")
        return

    config_path.write_text(patched)
    print(f"[Setup] config.py patched — {len(class_names)} classes, NUM_CLASSES updated.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download and prepare the Kaggle dataset.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without copying any files.",
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Skip download and use this local path instead.",
    )
    args = parser.parse_args()

    # ── Download ──────────────────────────────────────────────────────────────
    if args.dataset_path:
        dataset_root = Path(args.dataset_path)
        print(f"[Setup] Using local dataset path: {dataset_root}")
    else:
        dataset_root = download_dataset()

    # ── Detect structure ──────────────────────────────────────────────────────
    class_map = detect_class_folders(dataset_root)
    print(f"\n[Setup] Detected {len(class_map)} classes:")
    for cls, imgs in sorted(class_map.items()):
        print(f"  {cls:<35} {len(imgs):>5} images")

    # ── Copy into project ─────────────────────────────────────────────────────
    print(f"\n[Setup] Copying to {RAW_DATA_DIR} ...")
    class_names = copy_to_project(
        class_map,
        out_root=RAW_DATA_DIR,
        dry_run=args.dry_run,
    )

    # ── Patch config.py ───────────────────────────────────────────────────────
    patch_config(class_names, CONFIG_PATH, dry_run=args.dry_run)

    print("\n[Setup] Done. Next steps:")
    print("  python main.py --mode train")
    print("  python main.py --mode evaluate")
    print("  python main.py --mode predict --image <path>")


if __name__ == "__main__":
    main()
