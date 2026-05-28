import api from "./api";

export async function getAuditLog(params = {}) {
  const { data } = await api.get("/audit/", { params });
  return data;
}
