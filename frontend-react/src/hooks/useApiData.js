import { useEffect, useState } from "react";

export default function useApiData(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");

    fetcher()
      .then((res) => {
        if (!active) return;
        if (!res.ok) {
          setData(null);
          setError(res.data?.detail || `Request failed (${res.status})`);
          return;
        }
        setData(res.data);
      })
      .catch(() => {
        if (!active) return;
        setData(null);
        setError("Network error while loading data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, deps);

  return { data, loading, error };
}
