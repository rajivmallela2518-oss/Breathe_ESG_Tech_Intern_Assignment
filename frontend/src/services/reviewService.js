import api from "./api";

export async function getReviewQueue(params = {}) {
  const { data } = await api.get("/reviews/", { params });
  return data;
}

export async function approveRow(emissionId) {
  const { data } = await api.post(`/reviews/${emissionId}/approve/`);
  return data;
}

export async function rejectRow(emissionId, note) {
  const { data } = await api.post(`/reviews/${emissionId}/reject/`, { note });
  return data;
}
