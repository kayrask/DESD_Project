import { apiFetch } from "./client.js";

export async function getRecommendations({ limit = 4, category = "" } = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (category) params.set("category", category);

  const response = await apiFetch(`/ai/recommendations?${params.toString()}`);
  if (!response.ok) {
    throw new Error(response.data?.message || "Failed to load recommendations");
  }
  return response.data?.items || [];
}

