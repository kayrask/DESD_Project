# Backend FastAPI (Supabase)

## Libraries (requirements.txt)
- `fastapi==0.115.6`
- `uvicorn==0.32.1`
- `python-dotenv==1.0.1`
- `passlib==1.7.4`
- `bcrypt==4.2.1`
- `python-jose[cryptography]==3.3.0`
- `supabase==2.11.0`

## Environment
Backend reads root `.env` at project root.

Required keys:
```env
FRONTEND_URL=http://127.0.0.1:5173
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
```

## Database (Supabase)
Run this once in Supabase SQL Editor:
- `backend-fastapi/sql/supabase_schema.sql`

Core tables used now:
- `users`
- `products`
- `orders`

Future-ready tables included in schema:
- `producer_settlements`
- `commission_reports`
- `customer_favorites`

## Run
```bash
cd "/Users/kayra/Developer/DESD Group Project/backend-fastapi"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Main Endpoints
- `GET /health`
- `POST /auth/login`
- `POST /auth/register`
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
