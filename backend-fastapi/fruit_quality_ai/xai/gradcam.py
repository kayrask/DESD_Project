"""
Grad-CAM — Gradient-weighted Class Activation Mapping.

Grad-CAM uses the gradients flowing into the last convolutional layer to
produce a coarse spatial heatmap highlighting which image regions most
influenced the prediction. It requires no surrogate model and works with any
CNN architecture via forward/backward hooks.

Reference:
    Selvaraju et al., "Grad-CAM: Visual Explanations from Deep Networks via
    Gradient-based Localization", ICCV 2017.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe for server/API use.
import matplotlib.pyplot as plt
import matplotlib.cm as mcm
from PIL import Image
from torchvision import transforms

from config import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD, XAI_OUTPUT_DIR, BACKBONE


class GradCAM:
    """
    Attaches forward and backward hooks to a target layer and computes
    the Grad-CAM heatmap for a given input tensor and class index.
    """

    def __init__(self, model: nn.Module, target_layer: nn.Module) -> None:
        """Register forward and backward hooks on target_layer for Grad-CAM."""
        self.model = model
        self._activations: Optional[torch.Tensor] = None
        self._gradients: Optional[torch.Tensor] = None

        self._fwd_hook = target_layer.register_forward_hook(self._save_activation)
        self._bwd_hook = target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, module, input, output) -> None:
        """Forward hook that caches layer activations."""
        self._activations = output.detach()

    def _save_gradient(self, module, grad_input, grad_output) -> None:
        """Backward hook that caches layer gradients."""
        self._gradients = grad_output[0].detach()

    def generate(
        self,
        input_tensor: torch.Tensor,
        class_idx: Optional[int] = None,
    ) -> np.ndarray:
        """
        Compute the Grad-CAM heatmap for a single preprocessed image.

        Args:
            input_tensor: Shape (1, C, H, W) — already normalised.
            class_idx:    Target class; defaults to the predicted class.

        Returns:
            2-D float32 array in [0, 1] at the spatial resolution of the
            target layer's feature maps. Call the caller to upsample.
        """
        self.model.eval()
        input_tensor = input_tensor.clone().requires_grad_(True)

        output = self.model(input_tensor)
        if class_idx is None:
            class_idx = int(output.argmax(dim=1).item())

        self.model.zero_grad()
        output[0, class_idx].backward()

        # Global average pool gradients → channel importance weights.
        weights = self._gradients.mean(dim=(2, 3), keepdim=True)  # (1, C, 1, 1)

        # Weighted sum of activation maps, then ReLU.
        cam = (weights * self._activations).sum(dim=1, keepdim=True)
        cam = torch.relu(cam).squeeze().cpu().numpy()

        if cam.max() > 0:
            cam = cam / cam.max()

        return cam.astype(np.float32)

    def remove_hooks(self) -> None:
        """Detach hooks to free resources after use."""
        self._fwd_hook.remove()
        self._bwd_hook.remove()


def get_target_layer(model: nn.Module, backbone: str = BACKBONE) -> nn.Module:
    """
    Return the last convolutional block for the given backbone.

    The last feature layer carries the richest spatial representation,
    making it the best choice for Grad-CAM in all supported architectures.
    """
    if backbone == "efficientnet_b0":
        return model.features[-1]
    if backbone == "resnet18":
        return model.layer4[-1]
    if backbone == "mobilenet_v3_small":
        return model.features[-1]
    raise ValueError(f"No Grad-CAM target layer defined for backbone '{backbone}'.")


def generate_explanation(
    model: nn.Module,
    image_path: str,
    backbone: str = BACKBONE,
    class_idx: Optional[int] = None,
    image_size: int = IMAGE_SIZE,
    output_dir: Path = XAI_OUTPUT_DIR,
    filename: str = "gradcam_output.png",
) -> Path:
    """
    Generate and save a Grad-CAM overlay for a single image.

    Saves a three-panel figure: original image | heatmap | blended overlay.

    Args:
        model:      Trained model.
        image_path: Path to the raw image file.
        backbone:   Architecture name — used to select the target layer.
        class_idx:  Class to explain; defaults to the predicted class.
        image_size: Preprocessing resolution.
        output_dir: Directory to write the output PNG.
        filename:   Output file name.

    Returns:
        Path to the saved explanation image.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    device = next(model.parameters()).device

    original_image = Image.open(image_path).convert("RGB")

    preprocess = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    input_tensor = preprocess(original_image).unsqueeze(0).to(device)

    target_layer = get_target_layer(model, backbone)
    gradcam = GradCAM(model, target_layer)
    heatmap = gradcam.generate(input_tensor, class_idx=class_idx)
    gradcam.remove_hooks()

    # Upsample heatmap to match display resolution.
    heatmap_pil = Image.fromarray(np.uint8(heatmap * 255)).resize(
        (image_size, image_size), Image.BILINEAR
    )
    heatmap_arr = np.array(heatmap_pil) / 255.0

    original_arr = np.array(original_image.resize((image_size, image_size))) / 255.0

    # Blend heatmap (jet colormap) with the original image.
    colormap = mcm.get_cmap("jet")
    heatmap_rgb = colormap(heatmap_arr)[:, :, :3]
    overlay = np.clip(0.55 * original_arr + 0.45 * heatmap_rgb, 0, 1)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    titles = ["Original Image", "Grad-CAM Heatmap", "Overlay"]
    panels = [original_arr, heatmap_arr, overlay]
    cmaps = [None, "jet", None]

    for ax, title, panel, cmap in zip(axes, titles, panels, cmaps):
        ax.imshow(panel, cmap=cmap)
        ax.set_title(title, fontsize=11)
        ax.axis("off")

    plt.suptitle("Explainability: Grad-CAM Visualisation", fontsize=13, y=1.01)
    plt.tight_layout()

    save_path = output_dir / filename
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"[Grad-CAM] Explanation saved → {save_path}")
    return save_path
