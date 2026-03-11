# Sprint 3 Demo Script (Kayra)

Date: 2026-03-11  
Focus: Producer workflow + Admin reporting (Sprint 2/3 ownership)

## 1. Producer Functional Flow
1. Login as producer: `producer@desd.local`.
2. Open `/producer/products`.
3. Create a new product (name/category/price/stock/status).
4. Edit an existing product and save.
5. Open `/producer/orders`.
6. Open one order detail page.
7. Update order status in valid sequence:
   - Pending -> Confirmed -> Ready -> Delivered.
8. Confirm updated status is visible in list and detail.

## 2. Admin Reporting Flow (TC-025)
1. Login as admin: `admin@desd.local`.
2. Open `/admin/reports`.
3. Show totals cards (orders/gross/commission).
4. Apply a date range filter and show updated report rows.
5. Reset filters and confirm default report view returns.
6. Mention loading/empty/error state handling.

## 3. Access-Control Check (TC-022)
1. Login as customer and try `/producer/orders`.
2. Show forbidden behavior (`/403`) and confirm role protection.

## 4. Closing Statement
- Producer side supports product management and order status progression.
- Admin side supports commission visibility with date filtering.
- Role-based access control is enforced across dashboard routes.

