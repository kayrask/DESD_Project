import React from "react";

export default function Toast({ message, tone = "info" }) {
  if (!message) return null;
  return <p className={`toast toast-${tone}`}>{message}</p>;
}
