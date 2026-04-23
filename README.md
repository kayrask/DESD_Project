# DESD Group Project

This repository contains work for **two modules** that share a single codebase. The `main` branch is the combined production branch with all features merged.

---

## Repository Branch Structure

### Advanced AI (UFCFUR-15-3) Branches

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
| `main` *(latest)* | Kayra | Docstrings added to all AI/ML functions and classes |

### DESD Project Branches

| Branch | Author | Description |
|--------|--------|-------------|
| `feature/docker-setup` | — | Docker & infrastructure setup |
| `feature/database-and-api-integration` | — | Database and API layer |
| `feature/supabase-migration` | — | SQLite to Supabase migration |
| `feature/checkout-and-registration` | — | Checkout and registration flow |
| `feature/enhanced-customer-experience` | — | Customer UX improvements |
| `feature/auth-cors-error-messages` | — | Auth, CORS, error messages |
| `feature/marketing-pages-split` | — | Marketing and landing pages |
| `feature/frontend-django-polish` | — | Frontend polish |
| `feature/sprint2-concurrency-realtime-catalogue` | — | Sprint 2: concurrency, real-time catalogue |
| `feature/sprint1-sprint2-nazli-fixes` | Nazlican | Sprint 1/2 bug fixes |
| `feature/sprint2-kayra-producer-final` | Kayra | Producer dashboard, sprint 2 |
| `feature/desd-sprint2-sprint3-kayra` | Kayra | Sprint 2/3 DESD features |
| `feature/tc-013-017-018-020-community-foodmiles` | — | Test cases: community & food miles |
| `feature/cart-quantity-ux-improvements` | — | Cart quantity UX |
| `feature/ada-sprint3-final` | Ada | Sprint 3 marketplace fixes |
| `feature/ada-sprint3-order-history-security` | Ada | Order history, session security (TC-021/022) |
| `feature/ada-auth-security-fixes` | Ada | Role protection, ownership checks |
| `feature/admin-report-implementation-and-cleanup` | — | Admin reports, backend cleanup |

---

## Setup

This repo has two apps:
- `backend-fastapi` (Django/DRF API + PostgreSQL)
- `frontend-react` (React + Vite)

### Requirements
- Python 3.11+
- Node.js 18+
- npm 9+
- Docker & Docker Compose (recommended)

### Environment File
Create a `.env` file in the project root:

```env
FRONTEND_URLS=http://localhost:5173,http://127.0.0.1:5173,http://frontend:5173
FRONTEND_URL=http://127.0.0.1:5173
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_MOCK_AUTH_FALLBACK=false
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
```

### Start with Docker (recommended)
```bash
docker compose up -d --build
docker compose exec backend python manage.py migrate
```

App runs at `http://localhost`

### Start Manually

**Backend:**
```bash
cd backend-fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:8000
```

**Frontend:**
```bash
cd frontend-react
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## Demo Users

| Role | Email | Password |
|------|-------|----------|
| Producer | `producer@desd.local` | `Password123` |
| Admin | `admin@desd.local` | `Password123` |
| Customer | `customer@desd.local` | `Password123` |

---

## Code Quality

All Python source code across `ml/`, `fruit_quality_ai/`, and `app/services/` meets the following standards:

- **PEP 8 compliant** — validated with `flake8`, 105 violations resolved (`feature/pep8-compliance`)
- **Full docstring coverage** — every function and class has a docstring explaining its purpose
- **Test suite** — `backend-fastapi/api/tests.py`

To run the linter:
```bash
cd backend-fastapi
python3 -m flake8 --max-line-length=120 --statistics .
```

---

## Pre-Demo Checklist
- [ ] Backend and frontend running successfully
- [ ] Database migrations applied
- [ ] Role login works for producer / admin / customer
- [ ] Producer flow: create/edit products, order status transitions, order detail
- [ ] Admin flow: reports date range filter, totals summary, CSV export
- [ ] Security: wrong role returns `403`, unauthenticated returns `401`
