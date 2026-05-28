export const SOURCE_TYPES = [
  { value: "SAP_FUEL",             label: "SAP — Fuel & Procurement" },
  { value: "UTILITY_ELECTRICITY",  label: "Utility — Electricity"    },
  { value: "CORPORATE_TRAVEL",     label: "Corporate Travel"         },
];

export const REVIEW_STATUSES = ["PENDING", "APPROVED", "REJECTED"];

export const FLAG_SEVERITY_COLORS = {
  ERROR:   "bg-red-100 text-red-800",
  WARNING: "bg-yellow-100 text-yellow-800",
  INFO:    "bg-blue-100 text-blue-800",
};

export const REVIEW_STATUS_COLORS = {
  PENDING:  "bg-gray-100 text-gray-700",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
};

export const SCOPE_COLORS = {
  1: "bg-orange-100 text-orange-800",
  2: "bg-blue-100 text-blue-800",
  3: "bg-purple-100 text-purple-800",
};
