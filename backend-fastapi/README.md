# DESD Sprint 1 Backend (FastAPI MVC)

## Shared env
Use one root file: `/Users/kayra/Developer/DESD Group Project/.env`

```env
FRONTEND_URL=http://127.0.0.1:5173
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ENABLE_MOCK_AUTH_FALLBACK=false
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

## Run
```bash
cd "/Users/kayra/Developer/DESD Group Project/backend-fastapi"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
