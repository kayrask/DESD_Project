"""
Quality classifier model definitions.

Architectures
-------------
mobilenetv2 (default / production)
    MobileNetV2 pretrained on ImageNet, final classifier replaced with a
    2-class head (Healthy / Rotten).  Chosen for inference speed and small
    footprint — suitable for deployment inside the Django container.

resnet18 (baseline for comparative evaluation)
    ResNet18 pretrained on ImageNet, same 2-class head.  Serves as the
    baseline in the multi-architecture experiment because it is a well-known,
    slightly larger model (11 M params vs 3.4 M for MobileNetV2) with a
    different inductive bias (residual connections vs depthwise separable
    convolutions).  Comparing the two isolates the architectural contribution
    independent of the training recipe.

Factory
-------
Use ``build_model_by_arch(arch)`` to select an architecture by name so that
train.py and experiment.py can drive both models with the same code path.
"""

import torch
import torch.nn as nn
from torchvision import models


# ── MobileNetV2 (production model) ────────────────────────────────────────────

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


# ── ResNet18 (baseline for comparative evaluation) ────────────────────────────

def build_resnet18_baseline(num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    """
    Return a ResNet18 with a custom 2-class head, used as a baseline.

    Architectural contrast vs MobileNetV2:
    - Residual (skip) connections vs depthwise-separable convolutions
    - 11.7 M parameters vs 3.4 M (MobileNetV2) — larger but less mobile-optimised
    - Standard BatchNorm throughout vs efficient inverted residuals

    All feature extractor layers are frozen initially; the fc head trains
    during warmup.  Use ``unfreeze_resnet_top_layers`` for fine-tuning.

    Args:
        num_classes: 2 for binary Healthy/Rotten.
        pretrained:  Use ImageNet weights for the feature extractor.
    """
    weights = models.ResNet18_Weights.DEFAULT if pretrained else None
    model = models.resnet18(weights=weights)

    for param in model.parameters():
        param.requires_grad = False

    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, num_classes),
    )
    return model


def unfreeze_resnet_top_layers(model: nn.Module, n: int = 2) -> None:
    """
    Unfreeze the last *n* layer-groups of a ResNet18 for fine-tuning.

    ResNet18 has 4 residual layer groups (layer1–layer4).  n=2 unfreezes
    layer3 and layer4 — the highest-level feature maps.

    Args:
        model: A ResNet18 returned by build_resnet18_baseline().
        n:     Number of top layer-groups to unfreeze (default 2).
    """
    layer_groups = [model.layer1, model.layer2, model.layer3, model.layer4]
    for group in layer_groups[-n:]:
        for param in group.parameters():
            param.requires_grad = True


# ── Architecture factory ───────────────────────────────────────────────────────

SUPPORTED_ARCHS = ("mobilenetv2", "resnet18")


def build_model_by_arch(arch: str, num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    """
    Construct a model by architecture name.

    Args:
        arch:        One of ``SUPPORTED_ARCHS`` — 'mobilenetv2' or 'resnet18'.
        num_classes: Number of output classes (default 2).
        pretrained:  Use ImageNet pretrained weights (default True).

    Returns:
        Initialised nn.Module in training mode.

    Raises:
        ValueError: If *arch* is not in SUPPORTED_ARCHS.
    """
    if arch == "mobilenetv2":
        return build_model(num_classes=num_classes, pretrained=pretrained)
    if arch == "resnet18":
        return build_resnet18_baseline(num_classes=num_classes, pretrained=pretrained)
    raise ValueError(f"Unknown architecture '{arch}'. Choose from: {SUPPORTED_ARCHS}")


def unfreeze_top_layers_by_arch(model: nn.Module, arch: str, n: int) -> None:
    """Dispatch to the correct unfreeze function for the given architecture."""
    if arch == "mobilenetv2":
        unfreeze_top_layers(model, n=n)
    elif arch == "resnet18":
        unfreeze_resnet_top_layers(model, n=n)
    else:
        raise ValueError(f"Unknown architecture '{arch}'.")


# ── Shared loader ──────────────────────────────────────────────────────────────

def load_model(path: str, device: str = "cpu", arch: str = "mobilenetv2") -> nn.Module:
    """Load a saved model checkpoint from *path* and put it in eval mode."""
    model = build_model_by_arch(arch, pretrained=False)
    model.load_state_dict(torch.load(path, map_location=device, weights_only=True))
    model.eval()
    return model
