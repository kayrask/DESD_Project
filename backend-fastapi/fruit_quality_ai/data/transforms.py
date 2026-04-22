"""
Image transforms and augmentation pipeline.

Training augmentations simulate real-world variation that occurs in produce
markets and warehouse scanning (lighting, orientation, partial occlusion).
RandomErasing simulates physical damage or stickers on produce.
Validation and test use only resize + normalise for deterministic results.
"""

from torchvision import transforms

from config import IMAGE_SIZE, IMAGENET_MEAN, IMAGENET_STD


def get_train_transforms(image_size: int = IMAGE_SIZE) -> transforms.Compose:
    """Strong augmentation pipeline for training."""
    return transforms.Compose([
        transforms.Resize((image_size + 32, image_size + 32)),
        transforms.RandomCrop(image_size),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(20),
        transforms.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.3, hue=0.1),
        transforms.RandomGrayscale(p=0.05),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        # Simulates partial occlusion (stickers, damage, shadows on produce).
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.15), ratio=(0.3, 3.0)),
    ])


def get_val_transforms(image_size: int = IMAGE_SIZE) -> transforms.Compose:
    """Deterministic transform for validation and test splits."""
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def get_inference_transforms(image_size: int = IMAGE_SIZE) -> transforms.Compose:
    """Single-image inference transform — identical to val."""
    return get_val_transforms(image_size)


def get_tta_transforms(image_size: int = IMAGE_SIZE) -> list:
    """
    Test-Time Augmentation transforms.

    Returns a list of transforms; the predictor averages predictions across
    all of them to reduce variance and squeeze out extra accuracy.
    """
    return [
        # Original
        get_val_transforms(image_size),
        # Horizontal flip
        transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=1.0),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]),
        # Slight brightness boost
        transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ColorJitter(brightness=0.2),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]),
        # Slight crop variation
        transforms.Compose([
            transforms.Resize((image_size + 16, image_size + 16)),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]),
    ]
