import axios, { AxiosError } from "axios";
import type { InternalAxiosRequestConfig } from "axios";
import { getToken, setToken, clearToken } from "../token";

const baseURL = import.meta.env.VITE_API_URL ?? "";

// withCredentials: the refresh token is an httpOnly cookie scoped to /auth,
// so it must be stored and sent even when the API is on another port in dev.
export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

export function normalizeError(err: any): Error {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return new Error(detail);
  if (detail?.message) return new Error(detail.message);
  return new Error(err?.message || "Request failed");
}

// Endpoints whose 401 means "wrong credentials / no session", not "access token expired".
const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout", "/auth/oauth/complete"];

let refreshing: Promise<string | null> | null = null;

/**
 * Exchange the refresh cookie for a new access token. Concurrent callers share
 * one request, so a burst of 401s triggers a single refresh.
 * Resolves to the new token, or null when there is no valid session.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = axios
      .post<{ access_token: string }>(`${baseURL}/auth/refresh`, null, { withCredentials: true })
      .then((r) => {
        setToken(r.data.access_token);
        return r.data.access_token;
      })
      .catch(() => {
        clearToken();
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

function goToLogin() {
  clearToken();
  if (window.location.pathname !== "/login") window.location.assign("/login");
}

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const config = err.config as RetriableConfig | undefined;
    const url = config?.url ?? "";
    if (err.response?.status === 401 && config && !config._retried && !NO_REFRESH.some((p) => url.startsWith(p))) {
      config._retried = true;
      const token = await refreshAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
        return api(config);
      }
      goToLogin();
    }
    return Promise.reject(normalizeError(err));
  }
);
