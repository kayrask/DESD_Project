"""
Entry point for the Fruit & Vegetable Quality Assessment System.

Usage
─────
# Train a new model
    python main.py --mode train

# Evaluate the best checkpoint on the test set
    python main.py --mode evaluate

# Assess a single image (generates report + Grad-CAM heatmap)
    python main.py --mode predict --image path/to/apple.jpg

# Start the REST API service
    python main.py --mode serve
"""

import argparse

import torch

import config
from data.dataset import get_dataloaders, get_class_names
from models.classifier import build_model, count_parameters
from training.trainer import Trainer
from evaluation.evaluator import evaluate
from inference.predictor import QualityPredictor
from utils.helpers import get_device, set_seed, plot_training_history


def cmd_train(args) -> None:
    set_seed(42)
    device = get_device()
    print(f"[Main] Training on device: {device}")

    train_loader, val_loader, _ = get_dataloaders()

    model = build_model()
    trainable, total = count_parameters(model)
    print(f"[Main] Parameters — trainable: {trainable:,} / total: {total:,}")

    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        backbone=config.BACKBONE,
        pretrained=config.PRETRAINED,
    )
    history = trainer.train()

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_training_history(history, config.RESULTS_DIR / "training_history.png")
    print("[Main] Training complete. Best checkpoint → checkpoints/best_model.pth")


def cmd_evaluate(args) -> None:
    device = get_device()

    class_names_map = get_class_names()
    class_names = [class_names_map[i] for i in sorted(class_names_map)]

    model = build_model()
    checkpoint = config.CHECKPOINT_DIR / "best_model.pth"
    model.load_state_dict(torch.load(checkpoint, map_location=device))
    model.to(device)

    _, _, test_loader = get_dataloaders()
    evaluate(model, test_loader, device, class_names=class_names)


def cmd_predict(args) -> None:
    predictor = QualityPredictor.from_checkpoint()
    result = predictor.predict(args.image)
    result.print_report()


def cmd_serve(args) -> None:
    import uvicorn
    uvicorn.run("app:app", host=config.API_HOST, port=config.API_PORT, reload=False)


def main():
    parser = argparse.ArgumentParser(
        description="Fruit & Vegetable Quality Assessment — Bristol Regional Food Network"
    )
    parser.add_argument(
        "--mode",
        choices=["train", "evaluate", "predict", "serve"],
        required=True,
        help="Operation to run.",
    )
    parser.add_argument(
        "--image",
        type=str,
        help="Image path (required for --mode predict).",
    )
    args = parser.parse_args()

    if args.mode == "train":
        cmd_train(args)
    elif args.mode == "evaluate":
        cmd_evaluate(args)
    elif args.mode == "predict":
        if not args.image:
            parser.error("--image is required for --mode predict")
        cmd_predict(args)
    elif args.mode == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
