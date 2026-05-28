import { useState, useEffect, useCallback } from "react";
import { getReviewQueue, approveRow, rejectRow } from "../services/reviewService";

export function useReviewQueue(filters = {}) {
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getReviewQueue(filters);
      setRows(data.results);
      setCount(data.count);
    } catch {
      setError("Failed to load review queue.");
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);

  async function approve(emissionId) {
    await approveRow(emissionId);
    fetchQueue();
  }

  async function reject(emissionId, note) {
    await rejectRow(emissionId, note);
    fetchQueue();
  }

  return { rows, count, loading, error, approve, reject, refresh: fetchQueue };
}
