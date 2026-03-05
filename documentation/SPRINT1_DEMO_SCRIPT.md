# Sprint 1 Demo Script (March 4, 2026)

## Objective
Show role separation, auth integration, and dashboard shells.

## Steps
1. Start backend (`backend-fastapi`) on port `8000`.
2. Start frontend (`frontend-react`) on port `5173`.
3. Login as producer (`producer@desd.local`).
4. Show `/producer` and child routes:
   - `/producer/products`
   - `/producer/orders`
   - `/producer/payments`
5. Logout and login as customer (`customer@desd.local`).
6. Attempt `/producer` and show `403 Access Denied`.
7. Logout and login as admin (`admin@desd.local`).
8. Show `/admin`, `/admin/reports`, `/admin/users`.
9. Open protected route in incognito without login and show `401 Unauthorized`.

## Acceptance for Sprint 1
- Auth works.
- Route guards work by role.
- 401/403 states are visible.
- Producer/Admin dashboard shells exist.
