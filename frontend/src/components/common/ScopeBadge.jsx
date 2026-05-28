import { SCOPE_COLORS } from "../../utils/constants";
import { scopeLabel } from "../../utils/formatters";

export default function ScopeBadge({ scope }) {
  const cls = SCOPE_COLORS[scope] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {scopeLabel(scope)}
    </span>
  );
}
