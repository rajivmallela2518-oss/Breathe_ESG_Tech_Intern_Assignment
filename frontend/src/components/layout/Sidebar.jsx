import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { getDashboardSummary } from "../../services/ingestionService";

const NAV_LINKS = [
  { to: "/dashboard", label: "Dashboard"    },
  { to: "/upload",    label: "Upload Data"  },
  { to: "/review",    label: "Review Queue" },
  { to: "/audit",     label: "Audit Log"    },
];

export default function Sidebar() {
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    getDashboardSummary()
      .then((s) => setPendingCount(s.pending ?? 0))
      .catch(() => {});
  }, []);

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-200">
        <span className="text-sm font-semibold text-brand-600 tracking-wide uppercase">
          Breathe ESG
        </span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`
            }
          >
            <span>{label}</span>
            {to === "/review" && pendingCount > 0 && (
              <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-brand-600 text-white text-xs font-semibold">
                {pendingCount > 99 ? "99+" : pendingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
