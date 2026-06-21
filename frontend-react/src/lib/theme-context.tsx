import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

type Mode = "light" | "dark";
interface ThemeCtx { mode: Mode; setMode: (m: Mode) => void; accent: string; setAccent: (a: string) => void; }
const Ctx = createContext<ThemeCtx | null>(null);

const ACCENTS: Record<string, [string, string]> = {
  "#4F8EF7": ["#4F8EF7", "#3B6FD4"],
  "#22C55E": ["#22C55E", "#16A34A"],
  "#A855F7": ["#A855F7", "#7E22CE"],
  "#F59E0B": ["#F59E0B", "#B45309"],
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem("theme-mode") as Mode) || "dark");
  const [accent, setAccent] = useState<string>(() => localStorage.getItem("theme-accent") || "#4F8EF7");

  useEffect(() => {
    localStorage.setItem("theme-mode", mode);
    document.documentElement.classList.toggle("dark", mode === "dark");
  }, [mode]);

  useEffect(() => {
    localStorage.setItem("theme-accent", accent);
    const [a, dim] = ACCENTS[accent] ?? ACCENTS["#4F8EF7"];
    document.documentElement.style.setProperty("--accent", a);
    document.documentElement.style.setProperty("--accent-dim", dim);
  }, [accent]);

  return <Ctx.Provider value={{ mode, setMode, accent, setAccent }}>{children}</Ctx.Provider>;
}

export const ACCENT_CHOICES = Object.keys(ACCENTS);
export function useTheme() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used within ThemeProvider");
  return v;
}
