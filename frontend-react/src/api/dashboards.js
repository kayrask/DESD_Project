import { apiFetch } from "./client";

export const getProducerSummary = (token) => apiFetch("/dashboards/producer", {}, token);
export const getProducerProducts = (token) => apiFetch("/dashboards/producer/products", {}, token);
export const getProducerOrders = (token) => apiFetch("/dashboards/producer/orders", {}, token);
export const getProducerPayments = (token) => apiFetch("/dashboards/producer/payments", {}, token);

export const getAdminSummary = (token) => apiFetch("/dashboards/admin", {}, token);
export const getAdminReports = (token, filters = {}) => {
  const params = new URLSearchParams();
  if (filters.from) params.set("from", filters.from);
  if (filters.to) params.set("to", filters.to);
  const queryString = params.toString();
  return apiFetch(`/admin/commission${queryString ? `?${queryString}` : ""}`, {}, token);
};
export const getAdminUsers = (token) => apiFetch("/dashboards/admin/users", {}, token);
export const getAdminDatabase = (token) => apiFetch("/dashboards/admin/database", {}, token);

export const getCustomerSummary = (token) => apiFetch("/dashboards/customer", {}, token);
export const createOrder = (orderData) => 
  apiFetch("/orders/", {
    method: "POST",
    body: JSON.stringify(orderData),
  });

export const createProducerProduct = (payload, token) =>
  apiFetch(
    "/producer/products",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );

export const updateProducerProduct = (productId, payload, token) =>
  apiFetch(
    `/producer/products/${productId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    token,
  );

export const getProducerOrderDetail = (orderId, token) =>
  apiFetch(`/producer/orders/${encodeURIComponent(orderId)}`, {}, token);

export const updateProducerOrderStatus = (orderId, statusValue, token) =>
  apiFetch(
    `/producer/orders/${encodeURIComponent(orderId)}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status: statusValue }),
    },
    token,
  );
