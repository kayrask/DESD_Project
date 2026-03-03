import { apiFetch } from "./client";

export function loginRequest(credentials) {
  return apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}
