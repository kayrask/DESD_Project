# Kayra Test-Case Mapping (Sprint 1-3)

Owner: Kayra (Frontend Producer/Admin + Integration Polish)  
Updated: 2026-03-11

## Scope Delivered
- Role-based route protection and forbidden/unauthorized handling.
- Producer dashboard flow:
  - products create/edit UI
  - incoming orders list
  - order detail page
  - status update controls
- Admin reporting flow:
  - commission report table
  - date range filter
  - totals summary
  - loading/empty/error state consistency across admin pages.

## Mapping Matrix
| Test Case | Frontend Route/Page | Backend Endpoint(s) | Demo Steps | Status |
|---|---|---|---|---|
| TC-022 (Auth/Role access control) | `/login`, `/401`, `/403`, guarded `/producer`, `/admin`, `/customer` | `POST /auth/login`, protected `/dashboards/*` | Login with different roles and verify route restrictions | Pass |
| TC-009 (Producer incoming orders list) | `/producer/orders` | `GET /dashboards/producer/orders` | Login as producer and verify sorted order list | Pass |
| TC-010 (Producer status workflow) | `/producer/orders`, `/producer/orders/:orderId` | `GET /producer/orders/:orderId`, `PATCH /producer/orders/:orderId/status` | Open detail and move status through valid transitions | Pass |
| TC-012 (Producer settlement summary) | `/producer/payments` | `GET /dashboards/producer/payments` | Verify weekly/pending/commission figures render | Pass (current placeholder data) |
| TC-025 (Admin commission reporting) | `/admin/reports` | `GET /dashboards/admin/reports?from=&to=` | Apply date range filter and verify totals/table update | Pass |

## Evidence Files
- `frontend-react/src/App.jsx`
- `frontend-react/src/components/ProtectedRoute.jsx`
- `frontend-react/src/components/DashboardLayout.jsx`
- `frontend-react/src/pages/ProducerProductsPage.jsx`
- `frontend-react/src/pages/ProducerOrdersPage.jsx`
- `frontend-react/src/pages/ProducerOrderDetailPage.jsx`
- `frontend-react/src/pages/ProducerPaymentsPage.jsx`
- `frontend-react/src/pages/AdminReportsPage.jsx`
- `frontend-react/src/pages/AdminDashboard.jsx`
- `frontend-react/src/pages/AdminUsersPage.jsx`
- `frontend-react/src/pages/AdminDatabasePage.jsx`
- `backend-fastapi/api/urls.py`
- `backend-fastapi/api/views.py`
- `backend-fastapi/app/services/dashboard_service.py`

