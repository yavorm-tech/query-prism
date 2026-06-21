import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach } from "vitest";
import { ThemeProvider } from "../../lib/theme-context";
import UISettingsPanel from "./UISettingsPanel";

function renderWithTheme() {
  return render(
    <ThemeProvider>
      <UISettingsPanel />
    </ThemeProvider>
  );
}

describe("UISettingsPanel", () => {
  beforeEach(() => {
    // Reset to a known state
    localStorage.setItem("theme-mode", "dark");
    document.documentElement.classList.add("dark");
  });

  it("renders light/dark toggle", () => {
    renderWithTheme();
    expect(screen.getByRole("button", { name: /light/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dark/i })).toBeInTheDocument();
  });

  it("clicking Light removes the dark class from documentElement", async () => {
    const user = userEvent.setup();
    renderWithTheme();

    // Start in dark mode — dark class should be present
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await user.click(screen.getByRole("button", { name: /light/i }));

    // After clicking Light, the dark class should be gone
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("clicking Dark adds the dark class to documentElement", async () => {
    const user = userEvent.setup();
    // Start in light mode
    localStorage.setItem("theme-mode", "light");
    document.documentElement.classList.remove("dark");

    renderWithTheme();

    await user.click(screen.getByRole("button", { name: /dark/i }));

    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("renders accent color swatches for all ACCENT_CHOICES", () => {
    renderWithTheme();
    // ACCENT_CHOICES has 4 items: #4F8EF7, #22C55E, #A855F7, #F59E0B
    const swatches = screen.getAllByRole("button", { name: /accent/i });
    expect(swatches.length).toBe(4);
  });
});
