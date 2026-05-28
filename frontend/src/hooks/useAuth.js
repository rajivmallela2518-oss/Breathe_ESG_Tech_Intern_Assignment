import { useState } from "react";
import { login as loginService, logout as logoutService, getToken } from "../services/authService";

export function useAuth() {
  const [token, setToken] = useState(() => getToken());
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function login(email, password) {
    setLoading(true);
    setError(null);
    try {
      const data = await loginService(email, password);
      setToken(data.access);
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    logoutService();
    setToken(null);
  }

  return { token, login, logout, error, loading };
}
