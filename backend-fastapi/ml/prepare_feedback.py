"""
Export producer grade-override records as a labelled dataset for model retraining.

Usage (from backend-fastapi/ with Django environment active):

    python -m ml.prepare_feedback

    # Write to a specific output file
    python -m ml.prepare_feedback --output ml/feedback_labels.csv

    # Only export overrides from the last N days
    python -m ml.prepare_feedback --days 90

    # Dry-run: print summary without writing files
    python -m ml.prepare_feedback --dry_run

Output
------
A CSV file with columns:
    image_path, ai_grade, override_grade, reason, producer_id, assessed_at

The `override_grade` column is the ground-truth label to use when fine-tuning:
- A → class 0 (Healthy / Premium)
- B → class 0 (Healthy / Standard — still acceptable)
- C → class 1 (Rotten / Borderline)

This mapping is intentionally conservative: Grade C produce is treated the same
as Rotten for retraining purposes because the class-weighted loss already handles
the Healthy/Rotten imbalance, and conflating borderline cases with clear failures
is safer from a food-safety perspective.

Design notes
------------
- Only exports overrides where the producer changed the grade (ai_grade ≠ override_grade).
  Same-grade overrides (where the producer confirmed the AI) are skipped — they add no
  new information for supervised correction.
- The image_path column points to the MEDIA_ROOT-relative path stored in the DB.
  Use the --media_root flag if evaluating outside the Docker container.
- Running this script requires a configured Django environment (DJANGO_SETTINGS_MODULE).
  Inside Docker: docker exec desd-backend python -m ml.prepare_feedback
"""

import argparse
import csv
import os
import pathlib
import sys
from datetime import timedelta

# ── Django bootstrap ───────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

try:
    import django
    django.setup()
except Exception as exc:
    print(f"[ERROR] Django setup failed: {exc}", file=sys.stderr)
    print("Run this script from the backend-fastapi/ directory with Django configured.", file=sys.stderr)
    sys.exit(1)

from django.utils import timezone

from api.models import QualityOverride  # noqa: E402 — must come after django.setup()

# Grade → binary label mapping (conservative: C treated as rotten for food safety)
GRADE_TO_LABEL = {"A": 0, "B": 0, "C": 1}

DEFAULT_OUTPUT = pathlib.Path(__file__).parent / "saved_models" / "feedback_labels.csv"


def _iter_overrides(days: int | None):
    """Yield QualityOverride records, optionally filtered to the last `days` days."""
    qs = QualityOverride.objects.select_related(
        "assessment", "assessment__product", "producer"
    ).order_by("assessment__assessed_at")

    if days is not None:
        cutoff = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=cutoff)

    for override in qs:
        yield override


def prepare_feedback(
    output_path: pathlib.Path = DEFAULT_OUTPUT,
    days: int | None = None,
    dry_run: bool = False,
    media_root: str | None = None,
) -> int:
    """
    Export correction overrides as a CSV labelled dataset.

    Args:
        output_path: Destination CSV file.
        days:        If set, only export overrides from the last N days.
        dry_run:     Print summary without writing anything.
        media_root:  Override the image path prefix (default: MEDIA_ROOT from settings).

    Returns:
        Number of rows exported.
    """
    from django.conf import settings
    root = pathlib.Path(media_root or settings.MEDIA_ROOT)

    rows_exported = 0
    rows_skipped_same_grade = 0
    rows_missing_image = 0

    rows = []
    for override in _iter_overrides(days):
        assessment = override.assessment

        # Skip same-grade confirmations — no corrective signal
        if override.ai_grade == override.override_grade:
            rows_skipped_same_grade += 1
            continue

        image_full = root / assessment.image.name
        if not image_full.exists():
            rows_missing_image += 1
            continue

        rows.append({
            "image_path":     str(image_full),
            "ai_grade":       override.ai_grade,
            "override_grade": override.override_grade,
            "binary_label":   GRADE_TO_LABEL[override.override_grade],
            "reason":         override.reason,
            "producer_id":    override.producer_id,
            "product_name":   assessment.product.name,
            "assessed_at":    assessment.assessed_at.date().isoformat(),
        })
        rows_exported += 1

    print(f"\nFeedback export summary")
    print(f"  Total overrides queried : {rows_exported + rows_skipped_same_grade + rows_missing_image}")
    print(f"  Same-grade (skipped)    : {rows_skipped_same_grade}")
    print(f"  Missing image (skipped) : {rows_missing_image}")
    print(f"  Rows to export          : {rows_exported}")

    if rows_exported == 0:
        print("\nNothing to export.")
        return 0

    if dry_run:
        print("\n[dry_run] No file written.")
        for r in rows[:5]:
            print(f"  {r['image_path']}  ai={r['ai_grade']} → override={r['override_grade']}  label={r['binary_label']}")
        if len(rows) > 5:
            print(f"  … and {len(rows) - 5} more rows")
        return rows_exported

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["image_path", "ai_grade", "override_grade", "binary_label",
                  "reason", "producer_id", "product_name", "assessed_at"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  Feedback labels written → {output_path}")
    print(f"\nNext step — fine-tune on corrections:")
    print(f"  python -m ml.train --data_dir <path> --feedback_csv {output_path}")
    return rows_exported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export grade overrides as retraining labels")
    parser.add_argument("--output",     default=str(DEFAULT_OUTPUT), help="Output CSV path")
    parser.add_argument("--days",       type=int, default=None,      help="Export only overrides from last N days")
    parser.add_argument("--media_root", default=None,                help="Override MEDIA_ROOT path for image resolution")
    parser.add_argument("--dry_run",    action="store_true",         help="Print summary without writing files")
    args = parser.parse_args()

    prepare_feedback(
        output_path=pathlib.Path(args.output),
        days=args.days,
        dry_run=args.dry_run,
        media_root=args.media_root,
    )
