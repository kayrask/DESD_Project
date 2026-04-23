# Advanced AI — Live Demo Script

**Module:** UFCFUR-15-3 Advanced AI
**Group:** G4
**Date:** 2026-04-23

This script walks a marker through every case-study requirement (1–13) in **order**, with the exact click path, what they should see, and which requirement it satisfies. Follow it top to bottom — each step sets up the next.

---

## 0. Prep (do these BEFORE the demo)

```bash
# From project root
docker compose up -d db redis
cd backend-fastapi
source .venv/bin/activate
DB_HOST=localhost python manage.py runserver 0.0.0.0:8000

# In a second terminal (so the ASGI/WebSocket layer works)
docker compose up -d backend celery_worker
```

**Seed at least these accounts** (use `create_test_users` management command, or the registration form):
- Admin: `admin@desd.local` / `Admin1234!`
- Producer A: `producer_a@desd.local` / `Test1234` — has 3+ products
- Producer B: `producer_b@desd.local` / `Test1234` — has 3+ products
- Customer: `customer@desd.local` / `Test1234` — has 3+ past delivered orders

**Before opening the browser, run the evaluators ONCE** so the admin page has data to show:

```bash
# New 28-class model (produces the per-class classification_report)
python fruit_quality_ai/main.py --mode evaluate

# OR legacy binary (produces fairness metrics + confusion matrix)
python -m ml.evaluate --data_dir "/path/to/Fruit And Vegetable Diseases Dataset"
```

If neither dataset is available on the demo machine, at least have `fruit_quality_ai/results/evaluation_report.json` + `ml/saved_models/model_metrics.json` copied over from a training run — otherwise the admin monitoring page shows blank metric cards.

---

## Part 1 — Customer Flow (Requirements 1, 13)

**Goal:** Show intelligent ordering, recommendations with reasons, and customer-side explainability.

1. **Log in as `customer@desd.local`.**
2. Go to `/marketplace`.
   - **Show the "Recommended for You" row at the top.**
   - Hover/point at each card — each has a plain-language reason:
     *"Recommended because: matches your frequent vegetable purchases; popular with other customers."*
   - **Point out the `rec_model_version` badge** (e.g. `collab-v2`) — proves this is the collaborative model, not a static list.
   - ✅ **Requirement 13** (customer-side explainability)
   - ✅ **Requirement 9** (producer-diversity cap — point out that products come from different producers)
3. Click a product → add to cart → go to cart → checkout → place order.
4. Go to `/customer/` (dashboard).
   - **Show the "Suggested for You — AI Reorder Prediction" card.**
   - Each item has a reason: *"Usually reorders every 14 days — last ordered 9 days ago."*
   - ✅ **Requirement 1** (intelligent ordering, predicts frequent items)
5. Click **"Reorder"** on a past order.
   - **Show it cloned the items back into the cart in one click.**
   - ✅ **Requirement 1** (quick re-order)
6. Open `/customer/recurring-orders/`.
   - **Create a weekly recurring order.**
   - ✅ **Requirement 1** (recurring orders for power users)

---

## Part 2 — Producer Flow (Requirements 2, 3, 7, 8)

**Goal:** Show AI quality assessment, auto-discount, XAI heatmap, demand forecast.

7. **Log in as `producer_a@desd.local`.**
8. Go to `/producer/` (dashboard).
   - **Show the "Demand Forecast" chart** (Chart.js line chart).
   - **Show the "High demand expected for X next week" alert banner** if one is present.
   - Switch product in dropdown — chart updates.
   - ✅ **Requirement 8** (forecast charts for producers)
9. Go to `/producer/quality-check/`.
   - Pick a product from dropdown → upload an image (have a sample apple.jpg / tomato.jpg ready).
   - Submit.
   - **Show the result card:**
     - Overall Grade (A / B / C) badge.
     - Colour / Size / Ripeness bars — each coloured green/amber/red against case-study thresholds (75/65, 80/70, 70/60).
     - Model confidence %.
     - Model version (e.g. `efficientnet-b0-v1`).
     - ✅ **Requirement 2** (A/B/C with breakdown)
   - **Scroll to the XAI section:**
     - Grad-CAM heatmap overlay on the uploaded image.
     - "Why this grade?" plain-language explanation.
     - ✅ **Requirement 7** (XAI transparency)
10. **If the image came back Grade C:**
    - Go to `/producer/products/` → open that product.
    - **Point out the "AI Discount Applied: 20%"** line (or whatever the admin has configured).
    - Point out the effective discount caps at 50% (manual + AI combined).
    - ✅ **Requirement 3** (auto-discount Grade C, auto-update inventory)
11. Still on quality-check page, use the **"Deduct rotten stock"** form.
    - Reduce stock by N → if it hits 0, product auto-flips to "Out of Stock".
    - ✅ **Requirement 3** (auto-update inventory)
12. **Override the AI:** back on the quality-check result, if you disagree with the grade:
    - Click **"Override grade"** → pick a different grade + reason + notes → submit.
    - Success message: *"Override recorded: AI said Grade B, you marked Grade A. This feedback will be used to improve the model."*
    - ✅ **Requirement 11** (override handling + retraining loop)

---

## Part 3 — Multi-producer Isolation (Requirement 4)

13. **While still logged in as Producer A:**
    - Try to navigate directly to `/producer/products/{id-of-producer-B-product}/` — you get 404 or redirect.
    - Try to upload a quality image against Producer B's product_id (via URL manipulation or DevTools form post) — get *"Product not found or does not belong to you"*.
    - ✅ **Requirement 4** (multi-producer isolation)

---

## Part 4 — Admin / AI Engineer Flow (Requirements 5, 6, 9, 10, 11)

**Goal:** Show full visibility, model upload, accuracy tracking, fairness, overrides.

14. **Log in as `admin@desd.local`.**
15. Go to `/admin/ai-monitoring/`.
    - **Walk through every card top-to-bottom:**
      - **Totals row:** Total assessments, Avg confidence, Low-confidence count, Override count.
      - Click the override-count card → opens **override review page**. Point out the per-producer count table — *"if any producer > 30% of overrides, investigate systematic bias"*.
      - ✅ **Requirement 9** (fairness / bias detection in recommendations + overrides)
16. Back on monitoring page, **"Responsible AI" principles card** — show the 3 design choices visible.
17. **Model Evaluation Metrics card:**
    - Accuracy, Precision, Recall, F1 — big numbers.
    - Classes: 28 (for new model) or AUC-ROC (for legacy).
    - Dataset name + samples + updated_at.
    - ✅ **Requirement 10** (accuracy tracked over time)
18. **Scroll down to the Fairness Metrics sub-card** (inside the same card):
    - FPR Healthy, FNR Rotten, Equalized-Odds Gap — 3 numbers.
    - Green verdict badge *"Acceptable (per-class recall gap ≤ 0.10)"*.
    - **Food-safety spotlight callout** (yellow banner): *"Weakest rotten-detection is Tomato (recall 0.67). Prioritise collecting more labelled rotten examples for this produce."*
    - ✅ **Requirement 9** (fairness metrics computed + displayed)
19. **Confusion Matrix** — image from the last evaluator run.
20. **Accuracy-Over-Time chart:**
    - Chart.js line chart across uploads (versions on X-axis, accuracy/precision/recall/F1 on Y).
    - ✅ **Requirement 10** (monitoring over time)
21. **Recent Assessments table** (bottom of page):
    - 20 most recent with producer, product, grade, confidence.
    - Click **"View XAI"** on any row → opens assessment-detail page.
22. On assessment-detail page:
    - Grad-CAM heatmap, scores, explanation — **the marker can see what the admin sees**.
    - Optional: override from here too.
    - ✅ **Requirement 7** (XAI for admin)

### AI Engineer sub-flow (still on monitoring page)

23. **Model Upload form:**
    - Upload a `.pth` file (EfficientNet) or `.pt` (MobileNet) with optional metrics JSON.
    - Submit → success flash.
    - ✅ **Requirement 5** (AI engineers can upload new model)
    - Open a terminal → `celery -A desd_backend worker` logs → show the `evaluate_model_after_upload` task running.
    - Refresh monitoring page → new row in the accuracy-over-time chart.
    - ✅ **Requirement 10** (auto-eval writes ModelEvaluation row)
24. **Interaction DB export:**
    - Click **"Export All Interactions (CSV)"** button.
    - CSV downloads: every assessment + its override (ai_grade, override_grade, reason, notes, overridden_by, overridden_at).
    - Open the CSV → scroll to show the override columns.
    - ✅ **Requirement 5** (access DB of end-user interactions)

---

## Part 5 — Scalability / Robustness Notes (Requirement 12)

25. Open a second browser tab as a different customer → add an item to cart.
    - Point out: **CartReservation row created**, stale reservations auto-cleaned by Celery Beat (`cleanup_stale_reservations`).
26. **While still in demo,** in a terminal:

    ```bash
    docker compose down redis
    ```

    - Go back to the producer dashboard → **page still renders** (the try/except we added falls back to empty forecast).
    - Customer dashboard → **still renders** (empty reorder list, no crash).
    - Go back up:
    ```bash
    docker compose up -d redis
    ```
    - ✅ **Requirement 12** (graceful degradation, scalability)

---

## Part 6 — Tests (Requirements 1–13, test coverage)

27. **Show the test suite passing:**

    ```bash
    cd backend-fastapi
    DB_HOST=localhost python manage.py test
    ```

    - Expected output: `Ran 255 tests in 93s — OK`.
28. Highlight these specific tests for the marker:
    - `PredictReorderItemsSmokeTest` — reorder predictor safe-return + reason
    - `RecommendProductsSmokeTest` — recommender returns reasoned items + producer-diversity cap
    - `CustomerDashboardDegradedAIPathTest` — dashboard still renders when reorder service crashes
    - `ProducerDashboardDegradedAIPathTest` — same for forecast
    - `MarketplaceDegradedAIPathTest` — same for recommender
    - `EvaluateModelTaskTest.test_successful_evaluation_writes_row_new_arch` — EfficientNet upload path
    - `AdminAIMonitoringViewTest` — admin monitoring page loads with metrics
    - `ProducerQualityCheckTest` — assessment + discount + deduction + cross-producer isolation

---

## Quick Requirement → Demo Step Map (for marker cross-ref)

| # | Requirement | Demo Step |
|---|---|---|
| 1 | Intelligent ordering, reorder | 4, 5, 6 |
| 2 | AI quality assessment A/B/C | 9 |
| 3 | Auto-update inventory + discount | 10, 11 |
| 4 | Multi-producer isolation | 13 |
| 5 | Upload model + interaction DB | 23, 24 |
| 6 | Admin full visibility | 15–21 |
| 7 | XAI transparency | 9, 22 |
| 8 | Forecast for producers | 8 |
| 9 | Fairness / avoid bias | 2, 15, 18 |
| 10 | Accuracy over time | 17, 20, 23 |
| 11 | Override handling | 12, 15 |
| 12 | Scalability / graceful degradation | 25, 26 |
| 13 | Customer-side explainability | 2, 4 |

---

## If something breaks mid-demo

- **Dashboard page blank / 500:** check `logger.exception` output in the runserver terminal — our try/except should prevent this, but the log still tells you which service failed.
- **Heatmap missing:** model checkpoint not loaded; fallback chain kicks in — point out that the grading still works from the 4-tier fallback (KMeans → greenness).
- **Admin metrics card empty:** evaluator hasn't been run yet. Run `python fruit_quality_ai/main.py --mode evaluate` (or the legacy `python -m ml.evaluate`) — or refresh if it's a Celery task still running.
- **Redis disconnected:** WebSocket real-time updates stop but everything else works — show this is *intentional* graceful degradation (Requirement 12).
