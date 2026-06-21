import axios, { AxiosError } from "axios";
import { getToken, clearToken } from "../token";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  headers: { "Content-Type": "application/json" },
});

export function normalizeError(err: any): Error {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return new Error(detail);
  if (detail?.message) return new Error(detail.message);
  return new Error(err?.message || "Request failed");
}

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      clearToken();
      if (window.location.pathname !== "/login") window.location.assign("/login");
    }
    return Promise.reject(normalizeError(err));
  }
);
