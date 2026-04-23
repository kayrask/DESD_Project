"""
Robust pretrained weight downloader with resume support.

torch.hub's built-in downloader does not resume interrupted downloads,
so a partial file causes a hash mismatch on the next attempt. This script
downloads in chunks and resumes from where it left off after any interruption.

Usage:
    python download_weights.py                    # downloads resnet18 (default)
    python download_weights.py --backbone resnet18
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests
import torch

WEIGHTS = {
    "resnet18": {
        "url": "https://download.pytorch.org/models/resnet18-f37072fd.pth",
        "filename": "resnet18-f37072fd.pth",
        "expected_bytes": 46827520,
    },
    "efficientnet_b0": {
        "url": "https://download.pytorch.org/models/efficientnet_b0_rwightman-7f5810bc.pth",
        "filename": "efficientnet_b0_rwightman-7f5810bc.pth",
        "expected_bytes": 21437363,
    },
}

CACHE_DIR = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
CHUNK = 16_384
MAX_RETRIES = 30


def _download_with_resume(url: str, dest: Path, expected_bytes: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        existing = dest.stat().st_size if dest.exists() else 0

        if existing >= expected_bytes:
            print(f"  File already complete ({existing:,} bytes).")
            return

        headers = {}
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"
            print(f"[Attempt {attempt}] Resuming from {existing:,} / {expected_bytes:,} bytes ...")
        else:
            print(f"[Attempt {attempt}] Starting download ...")

        try:
            with requests.get(url, stream=True, headers=headers, timeout=60) as r:
                if r.status_code == 416:
                    print("  Server says file is complete.")
                    return
                r.raise_for_status()

                mode = "ab" if r.status_code == 206 else "wb"
                if mode == "wb":
                    existing = 0

                content_len = int(r.headers.get("content-length", 0))
                total = content_len + existing

                with open(dest, mode) as f:
                    downloaded = existing
                    for chunk in r.iter_content(chunk_size=CHUNK):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pct = downloaded / total * 100 if total else 0
                            filled = int(pct / 2)
                            bar = "█" * filled + "░" * (50 - filled)
                            print(f"\r  [{bar}] {pct:5.1f}%  {downloaded:,}/{total:,}", end="", flush=True)

            print("\n  Download segment complete.")

        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as exc:
            print(f"\n  Connection dropped: {exc}")
            wait = min(2 ** (attempt - 1), 60)
            print(f"  Waiting {wait}s before retry ...")
            time.sleep(wait)
        except Exception as exc:
            print(f"\n  Unexpected error: {exc}")
            time.sleep(5)

    raise RuntimeError(f"Download failed after {MAX_RETRIES} attempts.")


def _verify(path: Path) -> bool:
    """Return True if the file is a valid PyTorch checkpoint."""
    try:
        torch.load(path, map_location="cpu", weights_only=True)
        print("  ✓ File verified — valid PyTorch checkpoint.")
        return True
    except Exception as exc:
        print(f"  ✗ File corrupted ({exc}), will re-download from scratch.")
        path.unlink(missing_ok=True)
        return False


def download_backbone(backbone: str = "resnet18") -> Path:
    if backbone not in WEIGHTS:
        raise ValueError(f"Unknown backbone '{backbone}'. Choose: {list(WEIGHTS)}")

    info = WEIGHTS[backbone]
    dest = CACHE_DIR / info["filename"]

    print(f"\n{'─'*55}")
    print(f"  Backbone      : {backbone}")
    print(f"  Destination   : {dest}")
    print(f"  Expected size : {info['expected_bytes']:,} bytes")
    print(f"{'─'*55}\n")

    # Keep retrying until we have a complete, valid file.
    while True:
        _download_with_resume(info["url"], dest, info["expected_bytes"])
        if _verify(dest):
            break

    print(f"\n{'─'*55}")
    print("  Weights ready. Now update config.py:")
    print("    PRETRAINED         = True")
    print("    IMAGE_SIZE         = 128")
    print("    LEARNING_RATE      = 1e-4")
    print("    WEIGHT_DECAY       = 1e-5")
    print("    NUM_EPOCHS         = 30")
    print("    EARLY_STOPPING_PATIENCE = 7")
    print("  Then run: python main.py --mode train")
    print(f"{'─'*55}\n")
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download pretrained weights with resume support.")
    parser.add_argument("--backbone", default="resnet18", choices=list(WEIGHTS))
    args = parser.parse_args()

    try:
        download_backbone(args.backbone)
    except RuntimeError as exc:
        print(f"\n[Error] {exc}")
        sys.exit(1)
