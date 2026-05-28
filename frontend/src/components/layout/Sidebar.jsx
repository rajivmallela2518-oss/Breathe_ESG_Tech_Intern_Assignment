import { NavLink } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard"    },
  { to: "/upload",    label: "Upload Data"  },
  { to: "/review",    label: "Review Queue" },
  { to: "/audit",     label: "Audit Log"    },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-200">
        <span className="text-sm font-semibold text-brand-600 tracking-wide uppercase">
          Breathe ESG
        </span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-gray-600 hover:bg-gray-100"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
