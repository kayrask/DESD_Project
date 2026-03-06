import React, { useEffect, useState } from "react";

export default function Toast({ message, tone = "info" }) {
  const [visible, setVisible] = useState(Boolean(message));
  const [shouldRender, setShouldRender] = useState(Boolean(message));

  useEffect(() => {
    if (!message) {
      setVisible(false);
      return;
    }

    setShouldRender(true);
    setVisible(true);
    const timer = setTimeout(() => setVisible(false), 5000);
    return () => clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    if (visible) return;
    const timer = setTimeout(() => setShouldRender(false), 320);
    return () => clearTimeout(timer);
  }, [visible]);

  if (!message || !shouldRender) return null;
  return <p className={`toast toast-${tone} ${visible ? "toast-enter" : "toast-exit"}`}>{message}</p>;
}
