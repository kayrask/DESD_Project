import React from "react";
import { createContext, useContext, useMemo, useState } from "react";
import { loginRequest, logoutRequest } from "../api/auth";
import { getApiMessage } from "../api/client";

const AuthContext = createContext(null);
const STORAGE_KEY = "desd_react_session";

function readSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const initial = readSession();
  const [user, setUser] = useState(initial?.user || null);
  const [token, setToken] = useState(initial?.token || null);

  const login = async (email, password) => {
    try {
      const response = await loginRequest({ email, password });
      if (!response.ok) {
        return { ok: false, message: getApiMessage(response.data, "Login failed") };
      }

      const session = {
        user: response.data.user,
        token: response.data.access_token,
      };
      setUser(session.user);
      setToken(session.token);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      return { ok: true, user: session.user };
    } catch {
      return { ok: false, message: "Network error" };
    }
  };

  const logout = async () => {
    let message = "Logged out successfully";
    if (token) {
      try {
        const response = await logoutRequest(token);
        if (response.ok) {
          message = getApiMessage(response.data, message);
        } else {
          message = getApiMessage(response.data, message);
        }
      } catch {
        message = "Logged out locally (network issue)";
      }
    }
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_KEY);
    return { ok: true, message };
  };

  const value = useMemo(() => ({ user, token, login, logout }), [user, token]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
