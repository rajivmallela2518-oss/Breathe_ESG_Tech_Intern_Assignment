import { FLAG_SEVERITY_COLORS } from "../../utils/constants";

export default function FlagBadge({ severity, code }) {
  const cls = FLAG_SEVERITY_COLORS[severity] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {code?.replace(/_/g, " ")}
    </span>
  );
}
