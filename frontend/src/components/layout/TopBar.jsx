import { useAuth } from "../../hooks/useAuth";

const ROLE_LABEL = { ANALYST: "Analyst", ADMIN: "Admin" };

export default function TopBar() {
  const { logout, claims } = useAuth();
  return (
    <header className="h-12 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <span className="text-xs text-gray-400 uppercase tracking-wide font-medium">
        ESG Data Platform
      </span>
      <div className="flex items-center gap-4">
        {claims?.full_name && (
          <div className="text-right">
            <p className="text-sm font-medium text-gray-800 leading-tight">{claims.full_name}</p>
            <p className="text-xs text-gray-400 leading-tight">
              {ROLE_LABEL[claims.role] ?? claims.role}
            </p>
          </div>
        )}
        <button
          onClick={logout}
          className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
