import React from "react";
import { createContext, useContext, useMemo, useState } from "react";
import { loginRequest } from "../api/auth";

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
    console.log("Attempting login for:", email);
    try {
      const response = await loginRequest({ email, password });
      console.log("Login response:", response);
      if (!response.ok) {
        console.error("Login failed:", response.data);
        return { ok: false, message: response.data?.detail || "Login failed" };
      }

      const session = {
        user: response.data.user,
        token: response.data.access_token,
      };
      console.log("Login successful, setting session:", session);
      setUser(session.user);
      setToken(session.token);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      return { ok: true, user: session.user };
    } catch (error) {
      console.error("Login error:", error);
      return { ok: false, message: "Network error" };
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  const value = useMemo(() => ({ user, token, login, logout }), [user, token]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
