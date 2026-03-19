"""
Quality classifier model definition.

Architecture: MobileNetV2 pretrained on ImageNet, final classifier
replaced with a 2-class head (Healthy / Rotten).

Training produces a single .pt file saved to ml/saved_models/.
Inference loads that file and returns softmax probabilities.
"""

import torch
import torch.nn as nn
from torchvision import models


def build_model(num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    """
    Return a MobileNetV2 with a custom classification head.

    Args:
        num_classes: 2 for binary Healthy/Rotten.
        pretrained:  Use ImageNet weights for the feature extractor.
    """
    weights = models.MobileNet_V2_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v2(weights=weights)

    # Freeze the feature extractor – only fine-tune the classifier head.
    for param in model.features.parameters():
        param.requires_grad = False

    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.2),
        nn.Linear(in_features, num_classes),
    )
    return model


def load_model(path: str, device: str = "cpu") -> nn.Module:
    """Load a saved model checkpoint from *path* and put it in eval mode."""
    model = build_model(pretrained=False)
    model.load_state_dict(torch.load(path, map_location=device))
    model.eval()
    return model
