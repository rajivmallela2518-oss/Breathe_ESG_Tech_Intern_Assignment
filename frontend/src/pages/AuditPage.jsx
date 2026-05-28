import { useState } from "react";
import { useAuditLog } from "../hooks/useAuditLog";
import LoadingSpinner from "../components/common/LoadingSpinner";
import EmptyState from "../components/common/EmptyState";
import Pagination from "../components/common/Pagination";
import { formatDateTime } from "../utils/formatters";

const ACTION_COLORS = {
  ROW_APPROVED:    "bg-green-100 text-green-800",
  ROW_REJECTED:    "bg-red-100 text-red-800",
  BATCH_INGESTED:  "bg-blue-100 text-blue-800",
  ROW_FLAGGED:     "bg-yellow-100 text-yellow-800",
  ROW_NORMALIZED:  "bg-gray-100 text-gray-700",
  NOTE_EDITED:     "bg-purple-100 text-purple-800",
  ROW_UNLOCKED:    "bg-orange-100 text-orange-800",
};

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const { logs, count, loading } = useAuditLog(page);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Audit log</h2>
        <span className="text-sm text-gray-400">{count} events — read only</span>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : logs.length === 0 ? (
        <EmptyState message="No audit events yet." />
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Timestamp", "Actor", "Action", "Object", "Note"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs font-mono">
                    {formatDateTime(log.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-gray-800">
                    {log.actor_name ?? <span className="text-gray-400">system</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${ACTION_COLORS[log.action] ?? "bg-gray-100 text-gray-700"}`}>
                      {log.action?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs font-mono">{log.object_repr}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs max-w-xs truncate">
                    {log.after_state?.note ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4">
            <Pagination page={page} count={count} onChange={setPage} />
          </div>
        </div>
      )}
    </div>
  );
}
