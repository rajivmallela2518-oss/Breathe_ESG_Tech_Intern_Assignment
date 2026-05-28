import { useNavigate } from "react-router-dom";
import { useDashboard } from "../hooks/useDashboard";
import { useScopeBreakdown } from "../hooks/useScopeBreakdown";
import LoadingSpinner from "../components/common/LoadingSpinner";
import StatusBadge from "../components/common/StatusBadge";
import { formatDate, formatKgCo2e, sourceTypeLabel } from "../utils/formatters";

const SCOPE_META = {
  1: { label: "Scope 1 — Direct emissions",       color: "text-orange-700 bg-orange-50 border-orange-200" },
  2: { label: "Scope 2 — Electricity",             color: "text-blue-700 bg-blue-50 border-blue-200"    },
  3: { label: "Scope 3 — Value-chain & travel",    color: "text-purple-700 bg-purple-50 border-purple-200" },
};

function SummaryCard({ label, value, sub, onClick }) {
  const interactive = !!onClick;
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-gray-200 rounded-lg p-5 ${
        interactive ? "cursor-pointer hover:border-brand-600 hover:shadow-sm transition-all" : ""
      }`}
    >
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-semibold text-gray-900 mt-1">{value ?? "—"}</p>
      {sub && (
        <p className={`text-xs mt-1 ${interactive ? "text-brand-600" : "text-gray-400"}`}>
          {sub}
        </p>
      )}
    </div>
  );
}

function ScopeBreakdownTable({ rows, loading }) {
  if (loading) return <LoadingSpinner />;
  if (!rows.length) {
    return (
      <p className="text-sm text-gray-400 py-4">
        No emissions normalised yet — upload data to see the breakdown.
      </p>
    );
  }

  const totalKg = rows.reduce((sum, r) => sum + parseFloat(r.total_kg_co2e || 0), 0);
  const totalRows = rows.reduce((sum, r) => sum + (r.row_count || 0), 0);

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {["GHG Scope", "Data source", "Rows", "Total emissions"].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.map((r) => {
            const meta = SCOPE_META[r.scope] ?? { label: `Scope ${r.scope}`, color: "text-gray-700 bg-gray-50 border-gray-200" };
            return (
              <tr key={`${r.scope}-${r.batch__source_type}`} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium border ${meta.color}`}>
                    {meta.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700">{sourceTypeLabel(r.batch__source_type)}</td>
                <td className="px-4 py-3 text-gray-600">{r.row_count}</td>
                <td className="px-4 py-3 font-mono text-gray-800 text-xs">
                  {formatKgCo2e(r.total_kg_co2e)}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot className="border-t border-gray-200 bg-gray-50">
          <tr>
            <td className="px-4 py-3 text-xs font-semibold text-gray-700" colSpan={2}>
              Total
            </td>
            <td className="px-4 py-3 text-xs font-semibold text-gray-700">{totalRows}</td>
            <td className="px-4 py-3 text-xs font-semibold text-gray-700 font-mono">
              {formatKgCo2e(totalKg)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { summary, batches, loading } = useDashboard();
  const { rows: scopeRows, loading: scopeLoading } = useScopeBreakdown();

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-8">
      <h2 className="text-lg font-semibold text-gray-900">Overview</h2>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard
          label="Total rows ingested"
          value={summary?.total_rows}
        />
        <SummaryCard
          label="Pending review"
          value={summary?.pending}
          sub={summary?.pending > 0 ? "Click to review →" : "All reviewed"}
          onClick={() => navigate("/review")}
        />
        <SummaryCard
          label="Flagged rows"
          value={summary?.flagged}
          sub={summary?.flagged > 0 ? "Suspicious — click to inspect →" : "None flagged"}
          onClick={summary?.flagged > 0 ? () => navigate("/review") : undefined}
        />
        <SummaryCard
          label="Approved"
          value={summary?.approved}
          sub="locked for audit"
        />
      </div>

      {/* Scope breakdown */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-700">Emissions by GHG scope</h3>
          <span className="text-xs text-gray-400">All normalised rows</span>
        </div>
        <ScopeBreakdownTable rows={scopeRows} loading={scopeLoading} />
      </div>

      {/* Recent uploads */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Recent uploads</h3>
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Filename", "Source", "Uploaded", "Total", "Flagged", "Failed", "Status"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {batches.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-400">
                    No uploads yet. Go to{" "}
                    <button
                      onClick={() => navigate("/upload")}
                      className="text-brand-600 hover:underline"
                    >
                      Upload data
                    </button>{" "}
                    to get started.
                  </td>
                </tr>
              )}
              {batches.map((b) => (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-800 font-mono text-xs max-w-xs truncate">
                    {b.original_filename}
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{sourceTypeLabel(b.source_type)}</td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">
                    {formatDate(b.created_at)}
                  </td>
                  <td className="px-4 py-3 text-gray-800">{b.total_rows}</td>
                  <td className="px-4 py-3">
                    {b.flagged_rows > 0 ? (
                      <span className="text-yellow-700 font-medium">{b.flagged_rows}</span>
                    ) : (
                      <span className="text-gray-400">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {b.failed_rows > 0 ? (
                      <span className="text-red-600 font-medium">{b.failed_rows}</span>
                    ) : (
                      <span className="text-gray-400">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={b.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
