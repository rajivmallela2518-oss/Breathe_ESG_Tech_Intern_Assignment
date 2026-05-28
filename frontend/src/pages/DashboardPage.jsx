import { useDashboard } from "../hooks/useDashboard";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { formatDate, sourceTypeLabel } from "../utils/formatters";
import StatusBadge from "../components/common/StatusBadge";

function SummaryCard({ label, value, sub }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-semibold text-gray-900 mt-1">{value ?? "—"}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { summary, batches, loading } = useDashboard();
  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Overview</h2>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard label="Total rows ingested"  value={summary?.total_rows}   />
        <SummaryCard label="Pending review"        value={summary?.pending}      sub="needs analyst action" />
        <SummaryCard label="Flagged"               value={summary?.flagged}      sub="suspicious rows" />
        <SummaryCard label="Approved"              value={summary?.approved}     sub="locked for audit" />
      </div>

      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3">Recent uploads</h3>
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Filename", "Source", "Uploaded", "Rows", "Flagged", "Status"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {batches.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    No uploads yet.
                  </td>
                </tr>
              )}
              {batches.map((b) => (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-800 font-mono text-xs">{b.original_filename}</td>
                  <td className="px-4 py-3 text-gray-600">{sourceTypeLabel(b.source_type)}</td>
                  <td className="px-4 py-3 text-gray-600">{formatDate(b.created_at)}</td>
                  <td className="px-4 py-3 text-gray-800">{b.total_rows}</td>
                  <td className="px-4 py-3 text-gray-800">{b.flagged_rows}</td>
                  <td className="px-4 py-3"><StatusBadge status={b.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
