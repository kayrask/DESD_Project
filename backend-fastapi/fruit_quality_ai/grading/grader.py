"""
Rule-based grading layer.

This module is deliberately decoupled from the neural network so the project
demonstrates a hybrid AI design: the CNN provides a probabilistic classification,
while this layer applies transparent, interpretable business logic to convert
model outputs into an actionable grade and recommendation.

Grading rules
─────────────
Condition is derived from the predicted class label:
  • Label contains "fresh" / "good" / "healthy"  → condition = "fresh"
  • Label contains "rotten" / "bad" / "stale"    → condition = "rotten"
  • Otherwise                                     → condition = "uncertain"

Grades:
  Grade A — fresh, confidence ≥ GRADE_A_THRESHOLD  → normal sale
  Grade B — fresh, confidence ≥ GRADE_B_THRESHOLD  → discount / quick sale
  Grade C — rotten (any confidence) or low-confidence fresh → remove / inspect
"""

from __future__ import annotations

from dataclasses import dataclass

from config import GRADE_A_CONFIDENCE_THRESHOLD, GRADE_B_CONFIDENCE_THRESHOLD


@dataclass
class GradeResult:
    grade: str            # "A", "B", or "C"
    condition: str        # "fresh", "rotten", or "uncertain"
    recommendation: str
    quality_score: float  # Continuous proxy in [0.0, 1.0]
    reasoning: str        # Human-readable explanation of the decision


def _extract_condition(class_name: str) -> str:
    """Map a class label string to a binary condition keyword."""
    name = class_name.lower()
    if any(kw in name for kw in ("fresh", "good", "healthy")):
        return "fresh"
    if any(kw in name for kw in ("rotten", "bad", "stale", "spoiled")):
        return "rotten"
    return "uncertain"


def _quality_score(condition: str, confidence: float) -> float:
    """
    Derive a continuous quality score in [0, 1].

    Fresh products start from 0.5; rotten from 0.0.
    Confidence scales the score within each band.
    """
    if condition == "fresh":
        return 0.5 + 0.5 * confidence    # [0.50, 1.00]
    if condition == "rotten":
        return 0.5 * (1.0 - confidence)  # [0.00, 0.50]
    return 0.3  # uncertain default


def assign_grade(predicted_class: str, confidence: float) -> GradeResult:
    """
    Apply rule-based grading to a model prediction.

    Args:
        predicted_class: Class label string from the model (e.g. 'fresh_apple').
        confidence:      Softmax probability for the predicted class in [0, 1].

    Returns:
        GradeResult containing the grade, recommendation, score, and reasoning.
    """
    condition = _extract_condition(predicted_class)
    score = _quality_score(condition, confidence)

    if condition == "fresh":
        if confidence >= GRADE_A_CONFIDENCE_THRESHOLD:
            return GradeResult(
                grade="A",
                condition=condition,
                recommendation="Normal sale — product meets quality standards.",
                quality_score=score,
                reasoning=(
                    f"Predicted '{predicted_class}' with {confidence:.1%} confidence. "
                    f"High-confidence fresh prediction exceeds Grade A threshold "
                    f"(≥ {GRADE_A_CONFIDENCE_THRESHOLD:.0%})."
                ),
            )
        if confidence >= GRADE_B_CONFIDENCE_THRESHOLD:
            return GradeResult(
                grade="B",
                condition=condition,
                recommendation="Discount for quick sale — acceptable but not peak freshness.",
                quality_score=score,
                reasoning=(
                    f"Predicted '{predicted_class}' with {confidence:.1%} confidence. "
                    f"Moderate confidence falls in Grade B band "
                    f"({GRADE_B_CONFIDENCE_THRESHOLD:.0%}–{GRADE_A_CONFIDENCE_THRESHOLD:.0%})."
                ),
            )
        # Fresh but low confidence — ambiguous; flag for human review.
        return GradeResult(
            grade="C",
            condition=condition,
            recommendation="Manual inspection required — low-confidence fresh prediction.",
            quality_score=score,
            reasoning=(
                f"Predicted '{predicted_class}' with {confidence:.1%} confidence. "
                f"Confidence below Grade B threshold ({GRADE_B_CONFIDENCE_THRESHOLD:.0%}). "
                f"Flagged for human review."
            ),
        )

    if condition == "rotten":
        return GradeResult(
            grade="C",
            condition=condition,
            recommendation="Remove from stock — product classified as rotten/degraded.",
            quality_score=score,
            reasoning=(
                f"Predicted '{predicted_class}' with {confidence:.1%} confidence. "
                f"Any rotten classification results in Grade C regardless of confidence."
            ),
        )

    # Unknown class — default to safe manual inspection.
    return GradeResult(
        grade="C",
        condition=condition,
        recommendation="Manual inspection required — unrecognised class.",
        quality_score=score,
        reasoning=(
            f"Class '{predicted_class}' could not be mapped to a known condition. "
            f"Defaulting to manual inspection for safety."
        ),
    )
