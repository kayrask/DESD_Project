"""
Evaluation script – run after training to get precision, recall, F1, confusion matrix.

Usage (from backend-fastapi/):
    python -m ml.evaluate --data_dir "../Fruit And Vegetable Diseases Dataset"

Prints per-class metrics and saves a confusion matrix PNG.

Author (ai-eval): Member 2
Evidence prefix: ai-eval
"""

import argparse
import pathlib

import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader
from torchvision import transforms

from ml.model import load_model
from ml.train import HealthyRottenDataset

MODEL_PATH = pathlib.Path(__file__).parent / "saved_models" / "quality_classifier.pt"
IMG_SIZE = 224
BATCH_SIZE = 32


def evaluate(data_dir: str):
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No trained model at {MODEL_PATH}. Run ml/train.py first.")

    tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    dataset = HealthyRottenDataset(root=data_dir, transform=tf)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(str(MODEL_PATH), device=device)

    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            preds = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)

    print("\n── Classification Report ─────────────────────────────────")
    print(classification_report(all_labels, all_preds, target_names=["Healthy", "Rotten"]))

    cm = confusion_matrix(all_labels, all_preds)
    print("Confusion matrix (rows=actual, cols=predicted):")
    print(f"             Healthy  Rotten")
    print(f"  Healthy    {cm[0,0]:>7}  {cm[0,1]:>6}")
    print(f"  Rotten     {cm[1,0]:>7}  {cm[1,1]:>6}")

    # Compute precision@k proxy (hit-rate): fraction of top-k healthy correctly identified
    healthy_mask = all_labels == 0
    hit_rate = (all_preds[healthy_mask] == 0).mean() if healthy_mask.any() else 0
    print(f"\nHit-rate (healthy correctly identified): {hit_rate:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    args = parser.parse_args()
    evaluate(args.data_dir)
