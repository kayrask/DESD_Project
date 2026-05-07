# DESD Group Project

Bristol Regional Food Network — Digital Marketplace Platform

This repository contains work for **two modules** that share a single codebase. The `main` branch is the combined production branch with all features merged.

## Repository Structure

```
/
├── advanced-ai/        ← Advanced AI module (UFCFUR-15-3) — AI/ML code & notebooks
├── backend-fastapi/    ← Django backend (shared between both modules)
├── desd/               ← DESD project documentation & planning
├── documentation/      ← Test cases, case study, assessment specs
├── nginx/              ← Nginx reverse proxy config
└── compose.yaml        ← Docker Compose (all services)
```

> `advanced-ai/ml` and `advanced-ai/fruit_quality_ai` are symlinks into `backend-fastapi/` so Django can import them directly while keeping them visible under the AI folder.

## PR Labels

All pull requests are labelled by module for easy filtering:

- 🟣 [`advanced-ai`](../../pulls?q=label%3Aadvanced-ai+is%3Amerged) — Advanced AI module PRs
- 🔵 [`desd`](../../pulls?q=label%3Adesd+is%3Amerged) — DESD project PRs

---

## Repository Branch Structure

### DESD Project Branches

| Branch | Author | Description |
|--------|--------|-------------|
| `feature/docker-setup` | — | Docker & infrastructure setup |
| `feature/database-and-api-integration` | — | Database and API layer |
| `feature/supabase-migration` | — | SQLite → PostgreSQL migration |
| `feature/checkout-and-registration` | — | Checkout and registration flow |
| `feature/enhanced-customer-experience` | — | Customer UX improvements |
| `feature/auth-cors-error-messages` | — | Auth, CORS, error messages |
| `feature/marketing-pages-split` | — | Marketing and landing pages |
| `feature/frontend-django-polish` | — | Frontend polish |
| `feature/sprint2-concurrency-realtime-catalogue` | — | Sprint 2: concurrency, real-time catalogue |
| `feature/sprint1-sprint2-nazli-fixes` | Nazlican | Sprint 1/2 bug fixes |
| `feature/sprint2-kayra-producer-final` | Kayra | Producer dashboard, sprint 2 |
| `feature/desd-sprint2-sprint3-kayra` | Kayra | Sprint 2/3 DESD features |
| `feature/tc-013-017-018-020-community-foodmiles` | — | TC-013/017/018/020: community accounts & food miles |
| `feature/cart-quantity-ux-improvements` | — | Cart quantity UX |
| `feature/ada-sprint3-final` | Ada | Sprint 3 marketplace fixes |
| `feature/ada-sprint3-order-history-security` | Ada | Order history, session security (TC-021/022) |
| `feature/ada-auth-security-fixes` | Ada | Role protection, ownership checks |
| `feature/admin-report-implementation-and-cleanup` | — | Admin reports, backend cleanup |
| `feature/tc-012-payment-settlements` | — | TC-012: weekly payment settlements |
| `feature/producer-storefront` | — | Producer public storefront pages |
| `feature/recurring-order-improvements` | — | Recurring orders, pause/resume, approval |
| `final-sprint` | — | Final sprint feature implementation |
| `feature/nazli-product-approval-otp-allergens` | Nazlican | Product approval workflow, admin OTP 2FA, allergen filter |
| `feature/nazli-sendgrid-auth-ux` | Nazlican | SendGrid email, auth flows, user management UX |
| `feature/nazli-test-case-completion` | Nazlican | TC-009/019/020/022/023/024 completion, low-stock alerts |
| `feature/food-miles-postcode` | Kayra | TC-013 food miles, account settings, allergen checkboxes, TC-004 session management |
| `feature/sorted-out-producer-and-admin-to-suit-test-cases` | — | Producer & admin fixes for test case compliance |

### Advanced AI (UFCFUR-15-3) Branches

| Branch | Author | Description |
|--------|--------|-------------|
| `feature/ai-ml-forecasting-reorder` | Nazlican | EfficientNet-B0, SARIMA forecasting, reorder prediction |
| `feature/ada-ml-pipeline-eval-tracking` | Ada | ML data pipeline, accuracy-over-time tracking |
| `feature/nazli-ai-modelling-engine` | Nazlican | ML modelling engine |
| `feature/nazli-ai-ux-improvements` | Nazlican | AI output visibility — confidence badges, training chart |
| `feature/nazli-ai-enhancements` | Nazlican | Waste risk scoring, quality trend chart, price recommendations |
| `feat/ai-case-study-audit-fixes` | Kayra | Runtime hardening, grade thresholds, evaluator routing |
| `feature/admin-ai-fixes-model-eval` | Kayra | Auto-evaluate on upload, Celery task, OOM fix |
| `feature/kayra-ai-ml-improvements` | Kayra | Model upload, surplus discounts |
| `feature/ai-producer-quality-check-and-backend-improvements` | Matt | AI quality assessment, backend improvements |
| `feature/ada-ai-and-missing-features` | Ada | AI monitoring, XAI, model upload/export |
| `feature/pep8-compliance` | Kayra | PEP 8 compliance for all ML/AI Python modules |
| `feature/nazli-auc-roc-evaluation` | Nazlican | AUC-ROC added to EfficientNet-B0 evaluator |
| `feature/docs-docstrings-readme-v2` | Kayra | Docstrings added to all AI/ML functions and classes |

---

## Setup

### Requirements
- Docker & Docker Compose (**recommended — all services run automatically**)
- Python 3.11+ *(manual setup only)*

### Environment File

Create a `.env` file in the project root (copy from `.env.example`):

```env
# Email — leave blank to use console backend (OTP codes print to Docker logs)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@desd.local

# SendGrid (optional — set API key to enable transactional email)
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=noreply@desd.local
SENDGRID_FROM_NAME=DESD
```

### Start with Docker (recommended)

```bash
docker compose up -d --build
```

That's it. Docker automatically runs migrations, seeds the database, and starts all services:

| Service | Container | Description |
|---------|-----------|-------------|
| PostgreSQL 16 | `desd-db` | Primary database |
| Redis 7 | `desd-redis` | Cache & Celery broker |
| Django/Daphne | `desd-backend` | App server (port 8000) |
| Celery Worker | `desd-celery-worker` | Background tasks |
| Celery Beat | `desd-celery-beat` | Scheduled tasks (low-stock alerts, etc.) |
| Nginx | `desd-nginx` | Reverse proxy (port 80) |

App runs at **`http://localhost`**

To view OTP codes when using the console email backend:
```bash
docker compose logs -f backend
```

### Start Manually (without Docker)

```bash
cd backend-fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_db
python manage.py runserver 0.0.0.0:8000
```

App runs at `http://localhost:8000`

---

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Producer | `producer@desd.local` | `Password123` |
| Admin | `admin@desd.local` | `Password123` |
| Customer | `customer@desd.local` | `Password123` |
| Admin (Gmail) | `desdproject.test@gmail.com` | `Admin1234!` |

---

## Features

### Customer
- Register as Individual, Community Group, or Restaurant
- Browse and search products by name, category, and description
- Filter by organic certification, allergen exclusion, and category
- Add to cart, adjust quantities, remove items
- Checkout with per-producer delivery dates (48-hour minimum lead time)
- Multi-vendor orders with 5% network commission calculated automatically
- Order history and order status tracking
- Rate and review purchased products
- Recurring/regular orders with pause, resume, and end-date controls
- Food miles display on product pages (based on postcode)
- Account settings: update name, phone, postcode, password

### Producer
- Register with postcode; pending admin approval
- Product catalogue: add, edit, set price, stock, discount, allergens, seasonal dates, harvest date
- Inline quick-stock editor on the products table
- Organic certification flag and seasonal availability (season start/end)
- UK FSA 14-allergen checkbox list on products
- Surplus discount (manual 0–50%) and AI quality discount (set via quality check)
- Waste risk scoring badge on each product
- Incoming order dashboard with full customer contact details
- Order status transitions: Pending → Confirmed → Ready → Delivered
- Weekly payment settlement summaries (95% of order value after 5% commission)
- Low-stock alerts via Celery Beat when stock falls to or below threshold
- Recipes and farm stories (community content)
- Public storefront page visible to customers

### Admin
- Product approval queue (approve / reject with reason)
- OTP two-factor authentication for admin login
- Site-wide sales reports with date range filter and CSV export
- User management
- Network commission monitoring

### Security (TC-022)
- Role-based access control — wrong role returns 403
- Unauthenticated requests redirect to login
- Session expiry detection: `desd_sid` hint cookie distinguishes expired sessions from never-logged-in
- `SessionAwareLoginMixin` shows "session expired" message with `?expired=1` redirect
- Remember Me: 14-day session for checkbox selected; browser-close session otherwise (carried through OTP flow)
- CSRF protection on all state-changing endpoints
- Passwords hashed with Django's PBKDF2-SHA256

---

## Code Quality

- **PEP 8 compliant** — validated with `flake8`, violations resolved
- **Full docstring coverage** — every AI/ML function and class has a docstring
- **Test suite** — `backend-fastapi/api/tests.py`

```bash
cd backend-fastapi
python3 -m flake8 --max-line-length=120 --statistics .
```

---

## Pre-Demo Checklist

- [ ] `docker compose up -d --build` completes without errors
- [ ] App loads at `http://localhost`
- [ ] All three demo accounts log in successfully
- [ ] **Producer flow**: add product → allergen checkboxes → edit product → quick-stock update → order status transitions
- [ ] **Customer flow**: browse → filter organic → filter allergen → add to cart → checkout → order history → review
- [ ] **Admin flow**: approve product → date-range report → CSV export → OTP login works
- [ ] **Food miles**: set postcode in Account Settings → visit product page → food miles displayed
- [ ] **Session management**: login with Remember Me → close browser → reopen → still logged in; logout → protected page → redirects with "session expired"
- [ ] **Security**: visit `/producer/` as customer → 403; visit `/admin/` unauthenticated → redirect to login
