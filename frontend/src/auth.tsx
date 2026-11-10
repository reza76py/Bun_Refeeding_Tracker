import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, ensureCsrf, SESSION_CHECK_EVENT } from "./api/client";
import type { User } from "./api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        await ensureCsrf();
        setUser(await api.me());
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // One browser holds one session: if another login (e.g. another role in
  // another tab) replaced it, follow the server so nav + pages match it.
  useEffect(() => {
    const recheck = async () => {
      try {
        const me = await api.me();
        setUser((cur) =>
          cur &&
          cur.id === me.id &&
          cur.role === me.role &&
          cur.pages.join() === me.pages.join()
            ? cur
            : me
        );
      } catch {
        setUser(null); // signed out elsewhere -> show the sign-in screen
      }
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") recheck();
    };
    window.addEventListener(SESSION_CHECK_EVENT, recheck);
    window.addEventListener("focus", recheck);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener(SESSION_CHECK_EVENT, recheck);
      window.removeEventListener("focus", recheck);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setUser(await api.login(username, password));
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
