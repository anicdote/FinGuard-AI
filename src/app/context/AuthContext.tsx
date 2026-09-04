/**
 * AuthContext — provides current user, login, logout across the app.
 * Wrap <App /> with <AuthProvider />.
 */

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { authApi, tokenStore } from "../services/api";

interface User {
  _id: string;
  email: string;
  name: string;
  role: "admin" | "manager" | "officer" | "analyst";
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  beginLogin: (email: string, password: string) => Promise<any>;
  checkLoginChallenge: (challengeId: string, challengeToken: string) => Promise<any>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,    setUser]    = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Rehydrate from stored token on first load
  useEffect(() => {
    if (!tokenStore.access) { setLoading(false); return; }
    authApi.me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  async function beginLogin(email: string, password: string) {
    return authApi.beginLogin(email, password);
  }

  async function checkLoginChallenge(challengeId: string, challengeToken: string) {
    const challenge = await authApi.checkLoginChallenge(challengeId, challengeToken);
    if (challenge.accessToken) setUser(await authApi.me());
    return challenge;
  }

  function logout() {
    tokenStore.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, beginLogin, checkLoginChallenge, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
