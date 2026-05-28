import { useState } from "react";
import { useReviewQueue } from "../hooks/useReviewQueue";
import LoadingSpinner from "../components/common/LoadingSpinner";
import EmptyState from "../components/common/EmptyState";
import StatusBadge from "../components/common/StatusBadge";
import ScopeBadge from "../components/common/ScopeBadge";
import FlagBadge from "../components/common/FlagBadge";
import Pagination from "../components/common/Pagination";
import { formatKgCo2e, formatDate, sourceTypeLabel } from "../utils/formatters";
import { REVIEW_STATUSES } from "../utils/constants";

function NoteModal({ onConfirm, onCancel }) {
  const [note, setNote] = useState("");
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md space-y-4">
        <p className="font-medium text-gray-900">Rejection reason</p>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Describe why this row is being rejected…"
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600"
        />
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-800">
            Cancel
          </button>
          <button
            onClick={() => note.trim() && onConfirm(note)}
            disabled={!note.trim()}
            className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [rejectTarget, setRejectTarget] = useState(null);
  const { rows, count, loading, approve, reject } = useReviewQueue({ status: statusFilter, page });

  async function handleApprove(id) {
    await approve(id);
  }

  async function handleReject(note) {
    await reject(rejectTarget, note);
    setRejectTarget(null);
  }

  return (
    <div className="space-y-4">
      {rejectTarget && (
        <NoteModal
          onConfirm={handleReject}
          onCancel={() => setRejectTarget(null)}
        />
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Review queue</h2>
        <div className="flex gap-2">
          {REVIEW_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
              className={`px-3 py-1.5 rounded text-xs font-medium border transition-colors ${
                statusFilter === s
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : rows.length === 0 ? (
        <EmptyState message={`No ${statusFilter.toLowerCase()} rows.`} />
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Source", "Activity", "Scope", "Period", "Quantity", "kg CO₂e", "Flags", "Status", "Actions"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-600 text-xs">{sourceTypeLabel(row.source_type)}</td>
                  <td className="px-4 py-3 text-gray-800">{row.activity_type?.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3"><ScopeBadge scope={row.scope} /></td>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    {formatDate(row.period_start)} – {formatDate(row.period_end)}
                  </td>
                  <td className="px-4 py-3 text-gray-800 whitespace-nowrap">
                    {row.quantity_normalized} {row.unit_normalized}
                  </td>
                  <td className="px-4 py-3 text-gray-800 whitespace-nowrap font-mono text-xs">
                    {formatKgCo2e(row.kg_co2e)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {row.flags?.map((f, i) => (
                        <FlagBadge key={i} severity={f.severity} code={f.flag_code} />
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={row.review_status} /></td>
                  <td className="px-4 py-3">
                    {row.review_status === "PENDING" && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleApprove(row.id)}
                          className="text-xs px-2 py-1 rounded bg-green-100 text-green-800 hover:bg-green-200 font-medium"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => setRejectTarget(row.id)}
                          className="text-xs px-2 py-1 rounded bg-red-100 text-red-800 hover:bg-red-200 font-medium"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                    {row.review_status !== "PENDING" && (
                      <span className="text-xs text-gray-400">{row.analyst_note || "—"}</span>
                    )}
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
