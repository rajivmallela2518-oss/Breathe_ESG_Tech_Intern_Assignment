import { useState, useEffect } from "react";
import { getDashboardSummary, getBatches } from "../services/ingestionService";

export function useDashboard() {
  const [summary, setSummary] = useState(null);
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [s, b] = await Promise.all([getDashboardSummary(), getBatches()]);
      setSummary(s);
      setBatches(b.results || b);
      setLoading(false);
    }
    load();
  }, []);

  return { summary, batches, loading };
}
