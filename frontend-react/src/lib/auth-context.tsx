import { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { getMe, getTeams } from "./api/auth";
import type { User, Team } from "./api/types";
import { getToken, setToken, clearToken } from "./token";

interface AuthContextType {
  user: User | null;
  teams: Team[];
  activeTeamId: string | null;
  setActiveTeamId: (id: string | null) => void;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refreshTeams: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeamId, setActiveTeamId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const loadUserAndTeams = useCallback(async () => {
    try {
      const [me, userTeams] = await Promise.all([getMe(), getTeams()]);
      setUser(me);
      setTeams(userTeams);
      const defaultId = me.default_team_id ?? userTeams[0]?.id ?? null;
      setActiveTeamId((prev) => prev || defaultId);
    } catch {
      clearToken();
      setUser(null);
      setTeams([]);
      setActiveTeamId(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (getToken()) {
      loadUserAndTeams();
    } else {
      setLoading(false);
    }
  }, [loadUserAndTeams]);

  const login = async (token: string) => {
    setToken(token);
    setLoading(true);
    await loadUserAndTeams();
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setTeams([]);
    setActiveTeamId(null);
    navigate("/login");
  };

  const refreshTeams = async () => {
    const userTeams = await getTeams();
    setTeams(userTeams);
  };

  const refreshUser = async () => {
    const me = await getMe();
    setUser(me);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        teams,
        activeTeamId,
        setActiveTeamId,
        loading,
        login,
        logout,
        refreshTeams,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
