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

const SEVERITY_RANK = { ERROR: 0, WARNING: 1, INFO: 2 };

function worstSeverity(flags) {
  if (!flags?.length) return null;
  return flags.reduce((best, f) =>
    (SEVERITY_RANK[f.severity] ?? 9) < (SEVERITY_RANK[best.severity] ?? 9) ? f : best
  ).severity;
}

function NoteModal({ onConfirm, onCancel }) {
  const [note, setNote] = useState("");
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md space-y-4">
        <p className="font-medium text-gray-900">Rejection reason</p>
        <p className="text-xs text-gray-500">
          This note is stored in the audit log and shown in the Approved/Rejected view.
          Minimum 5 characters.
        </p>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Describe why this row is being rejected…"
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-600 resize-none"
          autoFocus
        />
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => note.trim().length >= 5 && onConfirm(note)}
            disabled={note.trim().length < 5}
            className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded disabled:opacity-50 transition-colors"
          >
            Confirm rejection
          </button>
        </div>
      </div>
    </div>
  );
}

function FlagDetails({ flags }) {
  if (!flags?.length) return null;
  return (
    <div className="mt-1 space-y-0.5">
      {flags.map((f, i) => (
        <p key={i} className="text-xs text-gray-500 leading-snug">
          <span className="font-medium">{f.field_name || "row"}</span>: {f.message}
        </p>
      ))}
    </div>
  );
}

function RowExpandPanel({ row, onClose, onApprove, onReject }) {
  return (
    <tr className="bg-blue-50">
      <td colSpan={9} className="px-6 py-4">
        <div className="flex items-start justify-between gap-8">
          <div className="flex-1 space-y-2">
            <p className="text-sm font-medium text-gray-800">
              {row.source_label ?? row.activity_type}
            </p>
            <p className="text-xs text-gray-500">
              <span className="font-medium">Location:</span> {row.location || "—"} &nbsp;·&nbsp;
              <span className="font-medium">Cost centre:</span> {row.cost_center || "—"}
            </p>
            {row.flags?.length > 0 && (
              <div className="space-y-1 pt-1">
                <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  Validation flags
                </p>
                <FlagDetails flags={row.flags} />
              </div>
            )}
            {row.analyst_note && (
              <p className="text-xs text-gray-500 italic">
                Note: {row.analyst_note}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {row.review_status === "PENDING" && (
              <>
                <button
                  onClick={() => { onApprove(row.id); onClose(); }}
                  className="text-sm px-3 py-1.5 rounded bg-green-600 text-white hover:bg-green-700 font-medium transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => { onReject(row.id); onClose(); }}
                  className="text-sm px-3 py-1.5 rounded bg-red-600 text-white hover:bg-red-700 font-medium transition-colors"
                >
                  Reject…
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="text-xs text-gray-400 hover:text-gray-600 ml-2 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </td>
    </tr>
  );
}

export default function ReviewPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [rejectTarget, setRejectTarget] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const { rows, count, loading, approve, reject } = useReviewQueue({ status: statusFilter, page });

  // Sort PENDING view: ERROR rows first, then WARNING, then clean
  const sortedRows = statusFilter === "PENDING"
    ? [...rows].sort((a, b) => {
        const ra = SEVERITY_RANK[worstSeverity(a.flags)] ?? 9;
        const rb = SEVERITY_RANK[worstSeverity(b.flags)] ?? 9;
        return ra - rb;
      })
    : rows;

  async function handleApprove(id) {
    await approve(id);
    setExpandedId(null);
  }

  async function handleReject(note) {
    await reject(rejectTarget, note);
    setRejectTarget(null);
    setExpandedId(null);
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
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Review queue</h2>
          {statusFilter === "PENDING" && count > 0 && (
            <p className="text-xs text-gray-400 mt-0.5">
              Flagged rows sorted to top. Click any row to expand details.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {REVIEW_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); setExpandedId(null); }}
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
      ) : sortedRows.length === 0 ? (
        <EmptyState message={`No ${statusFilter.toLowerCase()} rows.`} />
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Source", "Activity", "Scope", "Period", "Quantity", "kg CO₂e", "Flags", "Status", "Actions"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sortedRows.map((row) => {
                const worst = worstSeverity(row.flags);
                const isExpanded = expandedId === row.id;
                const rowBg = isExpanded
                  ? "bg-blue-50"
                  : worst === "ERROR"
                  ? "bg-red-50/40 hover:bg-red-50"
                  : worst === "WARNING"
                  ? "bg-yellow-50/40 hover:bg-yellow-50"
                  : "hover:bg-gray-50";

                return [
                  <tr
                    key={row.id}
                    className={`cursor-pointer transition-colors ${rowBg}`}
                    onClick={() => setExpandedId(isExpanded ? null : row.id)}
                  >
                    <td className="px-4 py-3 text-gray-600 text-xs whitespace-nowrap">
                      {sourceTypeLabel(row.source_type)}
                    </td>
                    <td className="px-4 py-3 text-gray-800 capitalize">
                      {row.activity_type?.replace(/_/g, " ")}
                    </td>
                    <td className="px-4 py-3">
                      <ScopeBadge scope={row.scope} />
                    </td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap text-xs">
                      {formatDate(row.period_start)} – {formatDate(row.period_end)}
                    </td>
                    <td className="px-4 py-3 text-gray-800 whitespace-nowrap text-xs">
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
                    <td className="px-4 py-3">
                      <StatusBadge status={row.review_status} />
                    </td>
                    <td className="px-4 py-3">
                      {row.review_status === "PENDING" && (
                        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => handleApprove(row.id)}
                            className="text-xs px-2 py-1 rounded bg-green-100 text-green-800 hover:bg-green-200 font-medium transition-colors"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => setRejectTarget(row.id)}
                            className="text-xs px-2 py-1 rounded bg-red-100 text-red-800 hover:bg-red-200 font-medium transition-colors"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                      {row.review_status !== "PENDING" && (
                        <span className="text-xs text-gray-400 max-w-[12rem] block truncate" title={row.analyst_note}>
                          {row.analyst_note || "—"}
                        </span>
                      )}
                    </td>
                  </tr>,
                  isExpanded && (
                    <RowExpandPanel
                      key={`${row.id}-expand`}
                      row={row}
                      onClose={() => setExpandedId(null)}
                      onApprove={handleApprove}
                      onReject={(id) => setRejectTarget(id)}
                    />
                  ),
                ];
              })}
            </tbody>
          </table>
          <div className="px-4 border-t border-gray-100">
            <Pagination page={page} count={count} onChange={(p) => { setPage(p); setExpandedId(null); }} />
          </div>
        </div>
      )}
    </div>
  );
}
