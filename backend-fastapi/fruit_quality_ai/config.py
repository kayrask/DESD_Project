"""
Central configuration for the Fruit & Vegetable Quality Assessment System.

A single config module avoids scattered magic numbers and makes the whole
system easy to reconfigure for demo or production without touching core logic.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
RESULTS_DIR = BASE_DIR / "results"
XAI_OUTPUT_DIR = RESULTS_DIR / "xai"

# ── Image normalisation (ImageNet statistics required for pretrained backbones) ─
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# ── Dataset ────────────────────────────────────────────────────────────────────
IMAGE_SIZE = 224       # Full resolution — pretrained weights are optimised for 224px.
BATCH_SIZE = 32        # Smaller batch needed for 224px on MPS memory.
NUM_WORKERS = 2        # Parallel data loading without macOS fork overhead.
VALIDATION_SPLIT = 0.15
TEST_SPLIT = 0.15

# Class names follow the torchvision ImageFolder convention (folder names).
# Assumption: each class folder uses one of these exact names.
# "fresh_*" labels map to healthy condition; "rotten_*" to degraded.
CLASS_NAMES = [
    "apple_healthy_fruit_and_vegetable_diseases_dataset",
    "apple_rotten_fruit_and_vegetable_diseases_dataset",
    "banana_healthy_fruit_and_vegetable_diseases_dataset",
    "banana_rotten_fruit_and_vegetable_diseases_dataset",
    "bellpepper_healthy_fruit_and_vegetable_diseases_dataset",
    "bellpepper_rotten_fruit_and_vegetable_diseases_dataset",
    "carrot_healthy_fruit_and_vegetable_diseases_dataset",
    "carrot_rotten_fruit_and_vegetable_diseases_dataset",
    "cucumber_healthy_fruit_and_vegetable_diseases_dataset",
    "cucumber_rotten_fruit_and_vegetable_diseases_dataset",
    "grape_healthy_fruit_and_vegetable_diseases_dataset",
    "grape_rotten_fruit_and_vegetable_diseases_dataset",
    "guava_healthy_fruit_and_vegetable_diseases_dataset",
    "guava_rotten_fruit_and_vegetable_diseases_dataset",
    "jujube_healthy_fruit_and_vegetable_diseases_dataset",
    "jujube_rotten_fruit_and_vegetable_diseases_dataset",
    "mango_healthy_fruit_and_vegetable_diseases_dataset",
    "mango_rotten_fruit_and_vegetable_diseases_dataset",
    "orange_healthy_fruit_and_vegetable_diseases_dataset",
    "orange_rotten_fruit_and_vegetable_diseases_dataset",
    "pomegranate_healthy_fruit_and_vegetable_diseases_dataset",
    "pomegranate_rotten_fruit_and_vegetable_diseases_dataset",
    "potato_healthy_fruit_and_vegetable_diseases_dataset",
    "potato_rotten_fruit_and_vegetable_diseases_dataset",
    "strawberry_healthy_fruit_and_vegetable_diseases_dataset",
    "strawberry_rotten_fruit_and_vegetable_diseases_dataset",
    "tomato_healthy_fruit_and_vegetable_diseases_dataset",
    "tomato_rotten_fruit_and_vegetable_diseases_dataset",
]
NUM_CLASSES = 28

# ── Model ──────────────────────────────────────────────────────────────────────
BACKBONE = "efficientnet_b0"   # Stronger than ResNet18 for fine-grained quality tasks.
PRETRAINED = True              # Requires weights downloaded via download_weights.py
DROPOUT_RATE = 0.4

# ── Two-stage training ─────────────────────────────────────────────────────────
# Stage 1: backbone frozen, only the classification head trains (fast convergence).
# Stage 2: full network unfrozen, fine-tuned with a very low LR (squeezes accuracy).
STAGE1_EPOCHS = 10
STAGE2_EPOCHS = 30
STAGE1_LR = 1e-3               # High LR is fine when only the head is training.
STAGE2_LR = 1e-5               # Very low LR to avoid destroying pretrained features.
WEIGHT_DECAY = 1e-4
EARLY_STOPPING_PATIENCE = 8
LABEL_SMOOTHING = 0.1          # Prevents overconfident predictions, reduces overfitting.

# Legacy single-stage fields (kept for backwards compatibility with Trainer).
LEARNING_RATE = STAGE1_LR
NUM_EPOCHS = STAGE1_EPOCHS + STAGE2_EPOCHS
LR_SCHEDULER_STEP = 7
LR_SCHEDULER_GAMMA = 0.5

# ── Rule-based grading thresholds ──────────────────────────────────────────────
# These constants drive the grading layer independently of the neural network.
GRADE_A_CONFIDENCE_THRESHOLD = 0.85
GRADE_B_CONFIDENCE_THRESHOLD = 0.60

# ── Service ────────────────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000
