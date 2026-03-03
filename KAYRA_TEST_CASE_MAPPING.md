# Kayra Sprint 1 Test-Case Mapping

Owner: Kayra (Frontend 4 - Admin/Staff UI + Integration Polish)
Date: 2026-03-03

## Scope delivered
- Role-based dashboard routing and guard behavior
- Producer dashboard pages: products, orders, payments
- Admin dashboard pages: reports, users
- Shared reusable UI: badge, status pill, toast
- Integration polish: loading, empty, and API error states

## Mapping matrix
| Test Case | Frontend Route/Page | Backend Endpoint(s) | Demo Steps | Status |
|---|---|---|---|---|
| TC-022 (Auth/Role access control) | `/login`, `/401`, `/403`, guarded `/producer`, `/admin`, `/customer` | `POST /auth/login`, protected `/dashboards/*` | Login as producer, customer, admin; attempt unauthorized route to trigger 403; open protected route without login for 401 | Pass |
| TC-009 (Producer incoming orders list) | `/producer/orders` | `GET /dashboards/producer/orders` | Login as producer and open orders page; verify table rows render from API response | Pass |
| TC-010 (Producer order status workflow visibility) | `/producer/orders` | `GET /dashboards/producer/orders` | Verify order status values displayed with status pill states (Pending/Confirmed/etc.) | Pass (shell) |
| TC-012 (Producer settlement summary) | `/producer/payments` | `GET /dashboards/producer/payments` | Open payments view and verify this week/pending/commission cards | Pass (shell) |
| TC-025 (Admin commission reports) | `/admin/reports` | `GET /dashboards/admin/reports` | Login as admin and verify report rows and currency formatting | Pass (shell) |

## Evidence files
- `frontend-react/src/App.jsx`
- `frontend-react/src/components/ProtectedRoute.jsx`
- `frontend-react/src/components/DashboardLayout.jsx`
- `frontend-react/src/components/Badge.jsx`
- `frontend-react/src/components/StatusPill.jsx`
- `frontend-react/src/components/Toast.jsx`
- `frontend-react/src/pages/ProducerDashboard.jsx`
- `frontend-react/src/pages/ProducerProductsPage.jsx`
- `frontend-react/src/pages/ProducerOrdersPage.jsx`
- `frontend-react/src/pages/ProducerPaymentsPage.jsx`
- `frontend-react/src/pages/AdminDashboard.jsx`
- `frontend-react/src/pages/AdminReportsPage.jsx`
- `frontend-react/src/pages/AdminUsersPage.jsx`
