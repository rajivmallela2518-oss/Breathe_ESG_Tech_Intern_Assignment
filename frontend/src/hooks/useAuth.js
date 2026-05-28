import { useState } from "react";
import { login as loginService, logout as logoutService, getToken } from "../services/authService";

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return {};
  }
}

export function useAuth() {
  const [token, setToken] = useState(() => getToken());
  const [claims, setClaims] = useState(() => {
    const tok = getToken();
    return tok ? parseJwt(tok) : null;
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function login(email, password) {
    setLoading(true);
    setError(null);
    try {
      const data = await loginService(email, password);
      setToken(data.access);
      setClaims(parseJwt(data.access));
      return true;
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed.");
      return false;
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    logoutService();
    setToken(null);
    setClaims(null);
  }

  return { token, claims, login, logout, error, loading };
}
