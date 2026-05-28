import api from "./api";

export async function getEmissions(params = {}) {
  const { data } = await api.get("/emissions/", { params });
  return data;
}

export async function getScopeBreakdown(approvedOnly = false) {
  const { data } = await api.get("/emissions/scope-breakdown/", {
    params: { approved_only: approvedOnly },
  });
  return data;
}
