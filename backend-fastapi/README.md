# Backend Django API (Supabase)

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
