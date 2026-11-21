import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setReady(true);
      return;
    }
    try {
      setUser(await api("/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    const onExpired = () => setUser(null);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, [refresh]);

  const value = useMemo(
    () => ({
      user,
      ready,
      setUser,
      refresh,
      async login(login, password) {
        const res = await api("/auth/login", { method: "POST", body: { login, password } });
        setToken(res.access_token);
        setUser(res.user);
        return res.user;
      },
      async register(fields) {
        const res = await api("/auth/register", { method: "POST", body: fields });
        setToken(res.access_token);
        setUser(res.user);
        return res.user;
      },
      logout() {
        setToken(null);
        setUser(null);
      },
    }),
    [user, ready, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
