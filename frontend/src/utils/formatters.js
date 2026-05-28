export function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function formatKgCo2e(value) {
  if (value == null) return "—";
  const n = parseFloat(value);
  return n >= 1000
    ? `${(n / 1000).toFixed(2)} t CO₂e`
    : `${n.toFixed(2)} kg CO₂e`;
}

export function scopeLabel(scope) {
  return { 1: "Scope 1", 2: "Scope 2", 3: "Scope 3" }[scope] ?? `Scope ${scope}`;
}

export function sourceTypeLabel(type) {
  return {
    SAP_FUEL: "SAP — Fuel & Procurement",
    UTILITY_ELECTRICITY: "Utility — Electricity",
    CORPORATE_TRAVEL: "Corporate Travel",
  }[type] ?? type;
}
