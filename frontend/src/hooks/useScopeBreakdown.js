import { useState, useEffect } from "react";
import { getScopeBreakdown } from "../services/emissionsService";

export function useScopeBreakdown(approvedOnly = false) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getScopeBreakdown(approvedOnly)
      .then(setRows)
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [approvedOnly]);

  return { rows, loading };
}
