import { apiFetch } from "./client";

export const getProducerSummary = (token) => apiFetch("/dashboards/producer", {}, token);
export const getProducerProducts = (token) => apiFetch("/dashboards/producer/products", {}, token);
export const getProducerOrders = (token) => apiFetch("/dashboards/producer/orders", {}, token);
export const getProducerPayments = (token) => apiFetch("/dashboards/producer/payments", {}, token);

export const getAdminSummary = (token) => apiFetch("/dashboards/admin", {}, token);
export const getAdminReports = (token) => apiFetch("/dashboards/admin/reports", {}, token);
export const getAdminUsers = (token) => apiFetch("/dashboards/admin/users", {}, token);
export const getAdminDatabase = (token) => apiFetch("/dashboards/admin/database", {}, token);

export const getCustomerSummary = (token) => apiFetch("/dashboards/customer", {}, token);
