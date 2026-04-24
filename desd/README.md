# DESD Group Project — UFCF7S-30-2

This folder represents the DESD web application work.

## Source Code
All DESD application code lives in the repository root:

| Folder | Description |
|--------|-------------|
| `backend-fastapi/api/` | Django views, models, URLs, templates |
| `backend-fastapi/app/services/` | Business logic services (excluding AI services) |
| `backend-fastapi/desd_backend/` | Django settings, ASGI, Celery config |
| `compose.yaml` | Docker Compose — db, backend, celery, nginx |

## Key Features Implemented
- Producer dashboard — product management, order status transitions (TC-010)
- Admin reports — date range filter, totals summary, CSV export
- Customer marketplace — cart, checkout, order history
- Django MVT architecture — replaced React SPA with Django templates
- Food miles (TC-013), community accounts (TC-017), recurring orders (TC-018)
- Session-based authentication with role enforcement
