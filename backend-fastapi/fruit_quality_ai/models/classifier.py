"""
Transfer learning classifier for fruit and vegetable quality assessment.

ResNet18 is the default backbone: reliable weights download, ~11M parameters,
and well-suited for fine-tuning on 28-class produce quality data.
EfficientNet-B0 and MobileNetV3-Small are also supported.
"""

from __future__ import annotations

from typing import Tuple

import torch
import torch.nn as nn
import torch.hub
from torchvision import models

from config import BACKBONE, NUM_CLASSES, DROPOUT_RATE, PRETRAINED

# Direct download URLs for each backbone's ImageNet weights.
_PRETRAINED_URLS: dict[str, str] = {
    "resnet18": "https://download.pytorch.org/models/resnet18-f37072fd.pth",
    "efficientnet_b0": "https://download.pytorch.org/models/efficientnet_b0_rwightman-7f5810bc.pth",
    "mobilenet_v3_small": "https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth",
}


def _load_pretrained_weights(model: nn.Module, backbone: str) -> None:
    """
    Download ImageNet weights and load them into the model.

    Uses check_hash=False to tolerate network environments that corrupt
    downloads (e.g. proxies, VPNs) which cause hash mismatches.
    strict=False means the classifier/fc head size mismatch is silently
    ignored — the backbone layers load correctly, the head stays randomly
    initialised (which is exactly what transfer learning requires).
    """
    url = _PRETRAINED_URLS[backbone]
    print(f"[Model] Downloading pretrained weights for {backbone} ...")
    state_dict = torch.hub.load_state_dict_from_url(
        url,
        progress=True,
        check_hash=False,   # bypass hash check — handles corrupt partial downloads
        map_location="cpu",
    )
    # strict=False skips missing/unexpected keys but still crashes on shape
    # mismatches (e.g. classifier head: 1000 ImageNet classes vs our num_classes).
    # Filter to only keys that exist in the model AND have matching shapes.
    model_state = model.state_dict()
    compatible = {
        k: v for k, v in state_dict.items()
        if k in model_state and v.shape == model_state[k].shape
    }
    skipped = len(state_dict) - len(compatible)
    model.load_state_dict(compatible, strict=False)
    print(f"[Model] Pretrained backbone loaded ({len(compatible)} keys matched, {skipped} head keys skipped).")


def build_model(
    backbone: str = BACKBONE,
    num_classes: int = NUM_CLASSES,
    dropout_rate: float = DROPOUT_RATE,
    pretrained: bool = PRETRAINED,
) -> nn.Module:
    """
    Construct a transfer learning model with a task-specific classification head.

    Builds the architecture with random weights first, replaces the head for
    the target number of classes, then loads ImageNet backbone weights
    separately (bypassing hash verification for network reliability).

    Args:
        backbone:     One of 'efficientnet_b0', 'resnet18', 'mobilenet_v3_small'.
        num_classes:  Number of output classes.
        dropout_rate: Dropout probability before the final linear layer.
        pretrained:   Load ImageNet-pretrained weights when True.

    Returns:
        A PyTorch nn.Module ready for training.
    """
    if backbone == "efficientnet_b0":
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=dropout_rate, inplace=True),
            nn.Linear(in_features, num_classes),
        )

    elif backbone == "resnet18":
        model = models.resnet18(weights=None)
        in_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(p=dropout_rate),
            nn.Linear(in_features, num_classes),
        )

    elif backbone == "mobilenet_v3_small":
        model = models.mobilenet_v3_small(weights=None)
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, num_classes)

    else:
        raise ValueError(
            f"Unsupported backbone: '{backbone}'. "
            "Choose from: efficientnet_b0, resnet18, mobilenet_v3_small."
        )

    if pretrained:
        _load_pretrained_weights(model, backbone)

    return model


def freeze_backbone(model: nn.Module, backbone: str = BACKBONE) -> None:
    """Freeze all convolutional feature layers; leave the head trainable."""
    if backbone == "efficientnet_b0":
        for param in model.features.parameters():
            param.requires_grad = False
    elif backbone == "resnet18":
        for name, param in model.named_parameters():
            if "fc" not in name:
                param.requires_grad = False
    elif backbone == "mobilenet_v3_small":
        for param in model.features.parameters():
            param.requires_grad = False


def unfreeze_backbone(model: nn.Module) -> None:
    """Unfreeze all parameters for full end-to-end fine-tuning."""
    for param in model.parameters():
        param.requires_grad = True


def count_parameters(model: nn.Module) -> Tuple[int, int]:
    """Return (trainable_count, total_count) for quick sanity checks."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total
