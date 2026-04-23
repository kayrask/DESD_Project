# Backend Django API (Supabase)

---

## Advanced AI — Case Study Requirements Map

This section maps every requirement in the Advanced AI case study to the code that implements it, so a marker can jump straight to the evidence.

| # | Case Study Requirement | Implementation | Tests |
|---|---|---|---|
| 1 | Intelligent ordering (predict frequent items, quick re-order) | `app/services/reorder_service.py:41` (Logistic-Regression, RFM features); surfaced on customer dashboard — [views_web.py:389](api/views_web.py#L389), [customer/dashboard.html:68](api/templates/customer/dashboard.html#L68). Quick re-order: `ReorderView` at [views_web.py:1640](api/views_web.py#L1640). Recurring orders: [models.py:250](api/models.py#L250) | `tests.py:352 ReorderViewTest`, `tests.py:2780` |
| 2 | AI quality assessment (A/B/C grade with Color/Size/Ripeness breakdown) | `ml/inference.py:337 classify_image` — 4-tier fallback chain (EfficientNet-B0 → MobileNetV2 → KMeans → greenness). Thresholds at `ml/inference.py:235` match case study (A ≥ 75/80/70, B ≥ 65/70/60, else C). Score breakdown at `ml/inference.py:193` | `tests.py:2033 ProducerQualityCheckTest` |
| 3 | Auto-update inventory + discount Grade C | `app/services/quality_service.py:63` auto-writes 20% `ai_discount_percentage` on Grade C (cleared on A). Rotten-stock deduction UI at `views_web.py:1296 deduct_rotten_stock` | `tests.py:2033` |
| 4 | Multi-producer isolation | Every `Product` has FK `producer`; all producer views filter `producer=request.user`. Recommendation diversity cap at `app/services/ai_service.py:163` prevents single-producer bias | `tests.py:2122` |
| 5 | AI-engineer: upload model + access interaction DB | `AdminModelUploadView` at `views_web.py:1492` (validates .pth/.pt via `torch.load(weights_only=True)`, backs up previous weights, clears cache). Async evaluation via Celery: `api/tasks.py:11 evaluate_model_after_upload`. CSV export of all assessments + overrides: `AdminInteractionExportView` at `views_web.py:1573` | `tests.py:2697 EvaluateModelTaskTest` |
| 6 | Admin full visibility | `AdminAIMonitoringView` at `views_web.py:1407` → [admin_panel/ai_monitoring.html](api/templates/admin_panel/ai_monitoring.html): totals, confidence, overrides, grade distribution, model metrics + fairness, confusion matrix, accuracy-over-time chart, recent assessments, XAI drill-down | `tests.py:2645 AdminAIMonitoringViewTest` |
| 7 | XAI transparency | Grad-CAM heatmap + plain-language explanation on every quality check. New model: `fruit_quality_ai/xai/gradcam.py`. Legacy: `ml/inference.py:264 _grad_cam_heatmap`. Surfaces on producer quality-check page and admin assessment-detail page | — |
| 8 | Producer demand forecast charts | SARIMA service at `app/services/forecast_service.py:41` (moving-average fallback); dashboard aggregator at `:128`; `producer/dashboard.html:94` renders Chart.js line chart + "High demand expected for X" alert | — |
| 9 | Fairness / avoid producer bias | FPR / FNR / equalized-odds gap computed by `ml/evaluate.py:81` and by per-produce bridge `app/services/quality_service.py:195`. Displayed on admin monitoring with green/red verdict badge + food-safety spotlight for weakest rotten-class. Override-per-producer review at `views_web.py:1895` | `tests.py:2033` |
| 10 | Accuracy monitoring over time | `ModelEvaluation` model at `api/models.py:356`; row written after every upload by `tasks.py:42`; Chart.js line chart on admin monitoring | `tests.py:2611`, `tests.py:2697` |
| 11 | Override handling + retraining loop | `QualityOverride` model at `models.py:319`; producer can override from `producer/quality_check.html`; admin can override from assessment-detail page; `ml/prepare_feedback.py` exports overrides as labelled CSV for fine-tuning (override_grade = ground truth) | `tests.py:2033` |
| 12 | Scalability | Cached inference predictors (module-level); `select_related`/`prefetch_related` in hot paths; CartReservation cleanup via Celery Beat (`tasks.py:53`); async model evaluation in subprocess isolates PyTorch memory | — |
| 13 | Customer-side explainability | Every recommendation carries a plain-language `reason` from `ai_service.py:215 _build_reason` ("matches your frequent vegetable purchases; popular with other customers; often bought alongside your other choices"), rendered on `marketplace.html:86`. Reorder reason rendered on `customer/dashboard.html:84` | — |

### Running the AI Stack

**Train the new 28-class EfficientNet-B0 quality classifier:**
```bash
cd fruit_quality_ai
python main.py --mode train            # phase-1 warmup + phase-2 fine-tune
python main.py --mode evaluate         # writes results/evaluation_report.json + confusion_matrix.png
python main.py --mode predict --image path/to/apple.jpg
```

**Train the legacy binary Healthy/Rotten classifier:**
```bash
python -m ml.train --data_dir /path/to/fruit_vegetable_dataset
python -m ml.evaluate --data_dir /path/to/fruit_vegetable_dataset
```

Both evaluators populate the admin monitoring page via the bridge in `app/services/quality_service.py:295 load_latest_model_metrics` (prefers the new model when present).

**Train the SARIMA demand-forecast model:**
Open `ml/forecasting/demand_forecast.ipynb` (writes `ml/forecasting/demand_model.pkl`).

**Train the reorder-prediction logistic model:**
Open `ml/reorder/reorder_prediction.ipynb` (writes `ml/reorder/reorder_model.pkl`).

Services degrade gracefully when model files are absent — see the fallback branches in each service.

### Running Tests

```bash
# Start just Postgres (tests use the InMemoryChannelLayer, no Redis needed)
docker compose up -d db
cd backend-fastapi
source .venv/bin/activate
DB_HOST=localhost python manage.py test
```

---



## Libraries (requirements.txt)
- `Django==5.1.5`
- `djangorestframework==3.15.2`
- `django-cors-headers==4.6.0`
- `python-dotenv==1.0.1`
- `passlib==1.7.4`
- `bcrypt==4.2.1`
- `supabase==2.11.0`

## Environment
Backend reads root `.env` at project root.

Required keys:
```env
FRONTEND_URLS=http://localhost:5173,http://127.0.0.1:5173,http://frontend:5173
FRONTEND_URL=http://127.0.0.1:5173
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
```

## Database (Supabase)
Run this once in Supabase SQL Editor:
- `backend-fastapi/sql/supabase_schema.sql`

## Run
```bash
cd "/Users/kayra/Developer/DESD Group Project/backend-fastapi"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:8000
```

## Main Endpoints
- `GET /health`
- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/logout`
- `GET /dashboards/me`
- `GET /dashboards/producer`
- `GET /dashboards/producer/products`
- `GET /dashboards/producer/orders`
- `GET /dashboards/producer/payments`
- `GET /dashboards/admin`
- `GET /dashboards/admin/reports`
- `GET /dashboards/admin/users`
- `GET /dashboards/admin/database`
- `GET /dashboards/customer`
- `POST /orders/`
- `GET /orders/{id}`
