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

    By default ALL feature extractor layers are frozen so only the
    classifier head is trained in the warmup phase.  Call
    ``unfreeze_top_layers(model, n)`` after warmup to enable
    progressive fine-tuning of the last n feature blocks.

    Args:
        num_classes: 2 for binary Healthy/Rotten.
        pretrained:  Use ImageNet weights for the feature extractor.
    """
    weights = models.MobileNet_V2_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v2(weights=weights)

    # Freeze the entire feature extractor – only the classifier head trains
    # during the warmup phase.
    for param in model.features.parameters():
        param.requires_grad = False

    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, num_classes),
    )
    return model


def unfreeze_top_layers(model: nn.Module, n: int = 3) -> None:
    """
    Unfreeze the last *n* blocks of model.features for fine-tuning.

    Called after the head-only warmup phase so the upper feature layers
    can adapt to produce-domain features (as opposed to generic ImageNet
    features). Lower layers remain frozen — they capture low-level edges
    and textures that transfer well across domains.

    MobileNetV2 has 19 feature blocks (indices 0-18).  n=3 unfreezes
    blocks 16, 17, 18 — the highest-level semantic layers.

    Args:
        model: A MobileNetV2 returned by build_model().
        n:     Number of top feature blocks to unfreeze (default 3).
    """
    blocks_to_unfreeze = list(model.features.children())[-n:]
    for block in blocks_to_unfreeze:
        for param in block.parameters():
            param.requires_grad = True


def load_model(path: str, device: str = "cpu") -> nn.Module:
    """Load a saved model checkpoint from *path* and put it in eval mode."""
    model = build_model(pretrained=False)
    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    model.eval()
    return model
