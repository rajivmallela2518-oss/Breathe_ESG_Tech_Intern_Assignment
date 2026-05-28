import api from "./api";

export async function uploadFile(file, sourceType) {
  const form = new FormData();
  form.append("file", file);
  form.append("source_type", sourceType);
  const { data } = await api.post("/ingestion/upload/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getBatches() {
  const { data } = await api.get("/ingestion/batches/");
  return data;
}

export async function getBatchDetail(batchId) {
  const { data } = await api.get(`/ingestion/batches/${batchId}/`);
  return data;
}

export async function getDashboardSummary() {
  const { data } = await api.get("/ingestion/summary/");
  return data;
}

export async function getBatchRows(batchId, params = {}) {
  const { data } = await api.get(`/ingestion/batches/${batchId}/rows/`, { params });
  return data;
}

export async function getSuspiciousRows(params = {}) {
  const { data } = await api.get("/ingestion/suspicious/", { params });
  return data;
}
