# DESD Group Project - Sprint 1 Setup

This repo has two apps:
- `backend-fastapi` (FastAPI API + Supabase)
- `frontend-react` (React + Vite)

## 1) Requirements
- Python 3.11+ (3.12 tested)
- Node.js 18+
- npm 9+
- Supabase project (shared team project)

## 2) Shared Environment File
Create/edit root `.env`:

```env
FRONTEND_URLS=http://localhost:5173,http://127.0.0.1:5173,http://frontend:5173
FRONTEND_URL=http://127.0.0.1:5173
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_MOCK_AUTH_FALLBACK=false
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
```

## 3) Database Setup (Supabase)
In Supabase SQL Editor, run:
- `backend-fastapi/sql/supabase_schema.sql`

This creates tables:
- `users`
- `products`
- `orders`
- future tables: `producer_settlements`, `commission_reports`, `customer_favorites`

## 4) Start Backend
```bash
cd "/Users/kayra/Developer/DESD Group Project/backend-fastapi"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend URL: `http://127.0.0.1:8000`

## 5) Start Frontend
```bash
cd "/Users/kayra/Developer/DESD Group Project/frontend-react"
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Frontend URL: `http://127.0.0.1:5173`

## 6) Demo Users (seeded by SQL)
- `producer@desd.local / password123`
- `admin@desd.local / password123`
- `customer@desd.local / password123`
