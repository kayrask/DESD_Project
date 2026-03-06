import { apiFetch } from "./client";

export function loginRequest(credentials) {
  return apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function registerRequest(userData) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(userData),
  });
}

export function logoutRequest(token) {
  return apiFetch(
    "/auth/logout",
    {
      method: "POST",
    },
    token
  );
}
