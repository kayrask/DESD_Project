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

## Branch Structure

| Branch | Author | Description |
|--------|--------|-------------|
| `feature/ai-ml-forecasting-reorder` | Nazlican | EfficientNet-B0 integration, SARIMA demand forecasting, reorder prediction |
| `feature/ada-ml-pipeline-eval-tracking` | Ada | ML data pipeline extraction, accuracy-over-time tracking |
| `feature/nazli-ai-modelling-engine` | Nazlican | ML modelling engine |
| `feature/nazli-ai-ux-improvements` | Nazlican | AI output visibility — predicted class, confidence badges, training chart |
| `feature/nazli-ai-enhancements` | Nazlican | Waste risk scoring, quality trend chart, price recommendations, Celery alerts |
| `feat/ai-case-study-audit-fixes` | Kayra | Runtime hardening, grade thresholds, evaluator routing, fairness UX |
| `feature/admin-ai-fixes-model-eval` | Kayra | Auto-evaluate model on upload, Celery task, OOM fix |
| `feature/kayra-ai-ml-improvements` | Kayra | AI/ML improvements, model upload, surplus discounts |
| `feature/ai-producer-quality-check-and-backend-improvements` | Matt | AI quality assessment, backend improvements |
| `feature/ada-ai-and-missing-features` | Ada | AI monitoring, XAI, model upload/export |
| `feature/pep8-compliance` | Kayra | PEP 8 compliance for all ML/AI Python modules |
| `feature/nazli-auc-roc-evaluation` | Nazlican | AUC-ROC added to EfficientNet-B0 evaluator |
| `feature/docs-docstrings-readme-v2` | Kayra | Docstrings added to all AI/ML functions and classes |
| `feature/repo-restructure` *(latest)* | Kayra | `advanced-ai/` and `desd/` folder separation, PR labels |

## Key Files
- `fruit_quality_ai/training/trainer.py` — Two-stage transfer learning trainer
- `fruit_quality_ai/evaluation/evaluator.py` — Per-class F1, confusion matrix
- `fruit_quality_ai/xai/gradcam.py` — Grad-CAM heatmap generation
- `ml/evaluate.py` — Fairness metrics (FPR, FNR, equalized-odds gap)
- `ml/forecasting/` — SARIMA model and forecasting service
- `ml/reorder/` — Logistic Regression reorder prediction

## How to Run

### Prerequisites
```bash
cd backend-fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Train EfficientNet-B0
```bash
cd backend-fastapi
python fruit_quality_ai/main.py --mode train
```

### Evaluate EfficientNet-B0 (regenerates confusion matrix + metrics)
```bash
cd backend-fastapi
python fruit_quality_ai/main.py --mode evaluate
```

### Run Fairness Metrics (binary MobileNetV2 models)
```bash
cd backend-fastapi
python -m ml.evaluate --data_dir "ml/Fruit And Vegetable Diseases Dataset"
```

### Compare All Models Side-by-Side
```bash
cd backend-fastapi
python -m ml.evaluate --data_dir "ml/Fruit And Vegetable Diseases Dataset" --compare
```

### Notebooks
Open in Jupyter:
```bash
pip install jupyter
jupyter notebook advanced-ai/notebooks/
```
- \`demand_forecast.ipynb\` — SARIMA training and MAE evaluation
- \`reorder_prediction.ipynb\` — Logistic Regression training, AUC-ROC 0.9417

### Run via Docker (recommended for full system)
```bash
docker compose up -d --build
docker compose exec backend python fruit_quality_ai/main.py --mode evaluate
```
