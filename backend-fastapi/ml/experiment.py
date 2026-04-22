"""
Hyperparameter grid search for the quality classifier.

Usage (from backend-fastapi/):
    python -m ml.experiment --data_dir "ml/Fruit And Vegetable Diseases Dataset"

    # Dry-run: print the grid without training
    python -m ml.experiment --data_dir "..." --dry_run

    # Restrict to one architecture
    python -m ml.experiment --data_dir "..." --arch mobilenetv2

What this does
--------------
Systematically trains the model under every combination of:
    - architecture:    mobilenetv2, resnet18
    - learning rate:   1e-3, 5e-4
    - warmup_epochs:   3, 5
    - unfreeze_n:      2, 3

Total grid: 2 × 2 × 2 × 2 = 16 configurations (or 8 per arch).

Each run is:
  1. Trained with short finetune (3 epochs) to rank configs quickly.
  2. Logged to ml/saved_models/experiments/runs.json (via train.py).
  3. The checkpoint is saved to ml/saved_models/experiments/<run_id>.pt.

After the sweep, the best configuration per architecture is printed and
written to ml/saved_models/experiments/best_configs.json.

Design rationale
----------------
A full grid search over all epochs is expensive; using a short finetune_epochs
for the grid search follows the successive halving principle — configs that
do not perform well with 3 fine-tune epochs are unlikely to win with 10.
The winning config from the grid is then retrained with full epochs using
ml/train.py.

Evidence value
--------------
The runs.json and best_configs.json files are the evidence that systematic
hyperparameter exploration was performed — addressing the "no experiment
tracking" gap identified in the project review.
"""

import argparse
import itertools
import json
import pathlib
from datetime import datetime

from ml.train import train as run_training

MODELS_DIR      = pathlib.Path(__file__).parent / "saved_models"
EXPERIMENTS_DIR = MODELS_DIR / "experiments"

# ── Search grid ────────────────────────────────────────────────────────────────
GRID = {
    "arch":          ["mobilenetv2", "resnet18"],
    "lr":            [1e-3, 5e-4],
    "warmup_epochs": [3, 5],
    "unfreeze_n":    [2, 3],
}
# Short finetune for grid search — rank configs cheaply, then retrain the winner
GRID_FINETUNE_EPOCHS = 3


def _all_configs(arch_filter: str | None = None):
    """Yield all (arch, lr, warmup_epochs, unfreeze_n) combinations."""
    keys   = list(GRID.keys())
    values = list(GRID.values())
    for combo in itertools.product(*values):
        cfg = dict(zip(keys, combo))
        if arch_filter and cfg["arch"] != arch_filter:
            continue
        yield cfg


def run_grid_search(data_dir: str, arch_filter: str | None = None, dry_run: bool = False):
    """
    Execute the hyperparameter grid search.

    Args:
        data_dir:     Dataset root path.
        arch_filter:  If set, only search this architecture.
        dry_run:      Print the grid without training.

    Returns:
        best_configs dict keyed by architecture.
    """
    configs = list(_all_configs(arch_filter))
    total   = len(configs)
    print(f"\n{'='*60}")
    print(f"Hyperparameter grid search — {total} configurations")
    print(f"{'='*60}")
    if dry_run:
        for i, cfg in enumerate(configs, 1):
            print(f"  [{i:>2}/{total}] arch={cfg['arch']}  lr={cfg['lr']}  "
                  f"warmup={cfg['warmup_epochs']}  unfreeze_n={cfg['unfreeze_n']}  "
                  f"finetune={GRID_FINETUNE_EPOCHS}")
        print("\n[dry_run] No training performed.")
        return {}

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for i, cfg in enumerate(configs, 1):
        run_id   = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        save_pt  = EXPERIMENTS_DIR / f"{run_id}_{cfg['arch']}.pt"

        print(f"\n[{i:>2}/{total}] arch={cfg['arch']}  lr={cfg['lr']}  "
              f"warmup={cfg['warmup_epochs']}  unfreeze_n={cfg['unfreeze_n']}  "
              f"finetune={GRID_FINETUNE_EPOCHS}")

        try:
            best_val_acc = run_training(
                data_dir=data_dir,
                arch=cfg["arch"],
                warmup_epochs=cfg["warmup_epochs"],
                finetune_epochs=GRID_FINETUNE_EPOCHS,
                lr=cfg["lr"],
                log_every=0,          # suppress batch-level output during sweep
                unfreeze_n=cfg["unfreeze_n"],
                save_path=save_pt,
            )
            results.append({**cfg, "finetune_epochs": GRID_FINETUNE_EPOCHS,
                            "best_val_acc": best_val_acc, "checkpoint": str(save_pt)})
            print(f"  → val_acc={best_val_acc:.4f}")
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({**cfg, "error": str(exc)})

    # Identify best config per architecture
    best_configs = {}
    for arch in set(r["arch"] for r in results if "best_val_acc" in r):
        arch_results = [r for r in results if r.get("arch") == arch and "best_val_acc" in r]
        if arch_results:
            best = max(arch_results, key=lambda r: r["best_val_acc"])
            best_configs[arch] = best

    # Persist
    summary = {
        "completed_at": datetime.utcnow().isoformat(),
        "grid":         GRID,
        "finetune_epochs_used": GRID_FINETUNE_EPOCHS,
        "all_results":  results,
        "best_configs": best_configs,
    }
    summary_path = EXPERIMENTS_DIR / "best_configs.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print("Grid search complete. Best configs per architecture:")
    for arch, cfg in best_configs.items():
        print(f"  {arch}: lr={cfg['lr']}  warmup={cfg['warmup_epochs']}  "
              f"unfreeze_n={cfg['unfreeze_n']}  → val_acc={cfg['best_val_acc']:.4f}")
    print(f"\nFull results → {summary_path}")
    print(f"Run logs     → {EXPERIMENTS_DIR / 'runs.json'}")
    print("\nTo retrain the best MobileNetV2 config with full epochs:")
    if "mobilenetv2" in best_configs:
        b = best_configs["mobilenetv2"]
        print(f"  python -m ml.train --data_dir <path> --arch mobilenetv2 "
              f"--lr {b['lr']} --warmup_epochs {b['warmup_epochs']} "
              f"--unfreeze_n {b['unfreeze_n']} --finetune_epochs 10")

    return best_configs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hyperparameter grid search for quality classifier")
    parser.add_argument("--data_dir", required=True,       help="Path to dataset root folder")
    parser.add_argument("--arch",     default=None,        choices=list(GRID["arch"]) + [None],
                        help="Restrict search to one architecture (default: all)")
    parser.add_argument("--dry_run",  action="store_true", help="Print grid without training")
    args = parser.parse_args()
    run_grid_search(args.data_dir, arch_filter=args.arch, dry_run=args.dry_run)
