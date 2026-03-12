# Sprint 3 Evidence Pack (Kayra)

Owner: Kayra  
Scope: Producer workflow polish + Admin commission reporting + evidence readiness

| Test Case | Feature | PR/File Evidence | Screenshot/GIF placeholder | Notes |
|---|---|---|---|---|
| TC-009 | Producer incoming orders list | `frontend-react/src/pages/ProducerOrdersPage.jsx` | `evidence/TC-009-orders-list.png` | Sorted by delivery date |
| TC-010 | Producer status transitions | `frontend-react/src/pages/ProducerOrdersPage.jsx`, `backend-fastapi/app/services/dashboard_service.py` | `evidence/TC-010-status-pass.png` and `evidence/TC-010-invalid-transition.png` | FE only valid options + BE lock |
| TC-025 | Admin commission report | `frontend-react/src/pages/AdminReportsPage.jsx`, `backend-fastapi/api/views.py` | `evidence/TC-025-report-filter.png` | Date range + totals + CSV |
| TC-022 | Route/role protection | `frontend-react/src/components/ProtectedRoute.jsx` | `evidence/TC-022-forbidden.gif` | 401/403 behavior |

## Error Contract Proof
- Endpoint contract used for admin commission:
  - `GET /admin/commission?from=YYYY-MM-DD&to=YYYY-MM-DD`
- Validation responses:
  - invalid format -> `{ error: "validation_error", message: "Dates must use YYYY-MM-DD" }`
  - from > to -> `{ error: "validation_error", message: "from date must be before to date" }`

## Payload/Response Notes
- Report response shape:
  - `{ rows: [{ date, orders, gross, commission }] }`
- CSV export generated directly from visible filtered rows in UI.

