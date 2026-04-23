"""
Inference module — single-image prediction pipeline.

Chains preprocessing → model forward pass → rule-based grading → Grad-CAM
into one callable class. The structured PredictionResult output is easy to
print for a demo, serialise to JSON for the API, or log for audit trails.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn
from PIL import Image

from config import BACKBONE, CHECKPOINT_DIR, CLASS_NAMES, IMAGE_SIZE, XAI_OUTPUT_DIR
from data.transforms import get_inference_transforms, get_tta_transforms
from grading.grader import GradeResult, assign_grade
from xai.gradcam import generate_explanation


@dataclass
class PredictionResult:
    """All outputs from a single quality assessment run."""
    image_path: str
    predicted_class: str
    confidence: float
    all_probabilities: Dict[str, float]
    quality_score: float
    grade: str
    condition: str
    recommendation: str
    reasoning: str
    explanation_path: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the prediction result to a plain dict."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialise the prediction result to an indented JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def print_report(self) -> None:
        """Pretty-print a demo-friendly assessment summary."""
        sep = "─" * 58
        print(f"\n{sep}")
        print("  FRUIT & VEGETABLE QUALITY ASSESSMENT REPORT")
        print(sep)
        print(f"  Image           : {self.image_path}")
        print(f"  Predicted class : {self.predicted_class}")
        print(f"  Confidence      : {self.confidence:.1%}")
        print(f"  Condition       : {self.condition.upper()}")
        print(f"  Quality score   : {self.quality_score:.2f} / 1.00")
        print(f"  Grade           : {self.grade}")
        print(f"  Recommendation  : {self.recommendation}")
        print(sep)
        print(f"  Reasoning:\n    {self.reasoning}")
        if self.explanation_path:
            print(f"  XAI heatmap     : {self.explanation_path}")
        print(sep)
        print("\n  Class probabilities:")
        for cls, prob in sorted(
            self.all_probabilities.items(), key=lambda x: x[1], reverse=True
        ):
            bar = "█" * int(prob * 24)
            print(f"    {cls:<28} {prob:6.2%}  {bar}")
        print()


class QualityPredictor:
    """
    Full inference pipeline: loads a trained model and assesses single images.

    Usage:
        predictor = QualityPredictor.from_checkpoint()
        result = predictor.predict("path/to/apple.jpg")
        result.print_report()
    """

    def __init__(
        self,
        model: nn.Module,
        class_names: List[str] = CLASS_NAMES,
        backbone: str = BACKBONE,
        image_size: int = IMAGE_SIZE,
        device: Optional[torch.device] = None,
        generate_xai: bool = True,
        xai_output_dir: Path = XAI_OUTPUT_DIR,
    ) -> None:
        """Initialise the predictor with a model, device, and inference config."""
        self.model = model
        self.class_names = class_names
        self.backbone = backbone
        self.image_size = image_size
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.generate_xai = generate_xai
        self.xai_output_dir = xai_output_dir
        self.transform = get_inference_transforms(image_size)

        self.tta_transforms = get_tta_transforms(image_size)
        self.model.to(self.device)
        self.model.eval()

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: Path = CHECKPOINT_DIR / "best_model.pth",
        **kwargs,
    ) -> "QualityPredictor":
        """Convenience constructor: build a model and load saved weights."""
        from models.classifier import build_model

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = build_model()
        model.load_state_dict(torch.load(checkpoint_path, map_location=device))
        print(f"[Predictor] Loaded checkpoint: {checkpoint_path}")
        return cls(model=model, device=device, **kwargs)

    def predict(self, image_path: str) -> PredictionResult:
        """
        Run the complete quality assessment for one image.

        Args:
            image_path: Absolute or relative path to a JPEG/PNG image.

        Returns:
            PredictionResult containing class, grade, recommendation, and
            optionally the path to the Grad-CAM explanation image.
        """
        image_path = str(image_path)
        image = Image.open(image_path).convert("RGB")

        # Test-Time Augmentation: average softmax probabilities over multiple
        # transforms to reduce prediction variance and gain ~1-2% accuracy.
        with torch.no_grad():
            all_probs = []
            for tf in self.tta_transforms:
                tensor = tf(image).unsqueeze(0).to(self.device)
                out = self.model(tensor)
                all_probs.append(torch.softmax(out, dim=1).squeeze().cpu())
            probabilities = torch.stack(all_probs).mean(dim=0).numpy()

        predicted_idx = int(probabilities.argmax())
        predicted_class = self.class_names[predicted_idx]
        confidence = float(probabilities[predicted_idx])
        all_probs = {
            cls: float(prob)
            for cls, prob in zip(self.class_names, probabilities)
        }

        # Rule-based grading — separate from the neural network by design.
        grade_result: GradeResult = assign_grade(predicted_class, confidence)

        # Explainability via Grad-CAM.
        explanation_path: Optional[str] = None
        if self.generate_xai:
            stem = Path(image_path).stem
            xai_path = generate_explanation(
                model=self.model,
                image_path=image_path,
                backbone=self.backbone,
                class_idx=predicted_idx,
                image_size=self.image_size,
                output_dir=self.xai_output_dir,
                filename=f"gradcam_{stem}.png",
            )
            explanation_path = str(xai_path)

        return PredictionResult(
            image_path=image_path,
            predicted_class=predicted_class,
            confidence=confidence,
            all_probabilities=all_probs,
            quality_score=grade_result.quality_score,
            grade=grade_result.grade,
            condition=grade_result.condition,
            recommendation=grade_result.recommendation,
            reasoning=grade_result.reasoning,
            explanation_path=explanation_path,
        )
