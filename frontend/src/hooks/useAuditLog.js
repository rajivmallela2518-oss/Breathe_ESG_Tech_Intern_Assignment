import { useState, useEffect } from "react";
import { getAuditLog } from "../services/auditService";

export function useAuditLog(page = 1) {
  const [logs, setLogs] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAuditLog({ page }).then((data) => {
      setLogs(data.results);
      setCount(data.count);
      setLoading(false);
    });
  }, [page]);

  return { logs, count, loading };
}
