import React from "react";

export default function StatusPill({ value }) {
  const normalized = String(value || "").toLowerCase();
  let tone = "neutral";
  if (["available", "confirmed", "ready", "active"].includes(normalized)) tone = "success";
  if (["pending", "warning"].includes(normalized)) tone = "warning";
  if (["out of stock", "suspended", "denied", "cancelled"].includes(normalized)) tone = "danger";

  return <span className={`status-pill status-${tone}`}>{value || "-"}</span>;
}
