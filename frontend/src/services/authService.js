import api from "./api";

export async function login(email, password) {
  const { data } = await api.post("/auth/token/", { email, password });
  localStorage.setItem("access_token", data.access);
  localStorage.setItem("refresh_token", data.refresh);
  return data;
}

export function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function getToken() {
  return localStorage.getItem("access_token");
}
