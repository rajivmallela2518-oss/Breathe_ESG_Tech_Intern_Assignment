import { REVIEW_STATUS_COLORS } from "../../utils/constants";

export default function StatusBadge({ status }) {
  const cls = REVIEW_STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
