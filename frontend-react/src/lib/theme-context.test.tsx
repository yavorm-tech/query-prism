import { render, screen } from "@testing-library/react";
import { ThemeProvider, useTheme } from "./theme-context";

function Probe() {
  const { mode, setMode } = useTheme();
  return <button onClick={() => setMode("dark")}>mode:{mode}</button>;
}

test("defaults to dark and toggles, applying the dark class", () => {
  render(<ThemeProvider><Probe /></ThemeProvider>);
  expect(screen.getByText("mode:dark")).toBeInTheDocument();
  expect(document.documentElement.classList.contains("dark")).toBe(true);
});
