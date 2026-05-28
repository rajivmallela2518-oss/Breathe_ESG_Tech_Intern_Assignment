import { useAuth } from "../../hooks/useAuth";

export default function TopBar() {
  const { logout } = useAuth();
  return (
    <header className="h-12 bg-white border-b border-gray-200 flex items-center justify-end px-6">
      <button
        onClick={logout}
        className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
      >
        Sign out
      </button>
    </header>
  );
}
