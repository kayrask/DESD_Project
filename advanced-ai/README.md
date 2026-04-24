# Advanced AI — UFCFUR-15-3

This folder contains all AI/ML work for the Advanced Artificial Intelligence module.

## Notebooks
| Notebook | Description |
|----------|-------------|
| `notebooks/demand_forecast.ipynb` | SARIMA demand forecasting — training, evaluation, MAE comparison |
| `notebooks/reorder_prediction.ipynb` | Logistic Regression reorder prediction — RFM features, AUC-ROC 0.9417 |

## Source Code
| Folder | Description |
|--------|-------------|
| `ml/` | Binary-stage classifiers (MobileNetV2 v1/v2), evaluation, SARIMA forecasting, reorder model |
| `fruit_quality_ai/` | Production EfficientNet-B0 pipeline — training, evaluation, Grad-CAM XAI, 28-class grading |

> `ml/` and `fruit_quality_ai/` are symlinks to `backend-fastapi/ml/` and `backend-fastapi/fruit_quality_ai/`
> respectively. The code lives there so Django can import it directly.

## Key Files
- `fruit_quality_ai/training/trainer.py` — Two-stage transfer learning trainer
- `fruit_quality_ai/evaluation/evaluator.py` — Per-class F1, confusion matrix
- `fruit_quality_ai/xai/gradcam.py` — Grad-CAM heatmap generation
- `ml/evaluate.py` — Fairness metrics (FPR, FNR, equalized-odds gap)
- `ml/forecasting/` — SARIMA model and forecasting service
- `ml/reorder/` — Logistic Regression reorder prediction
