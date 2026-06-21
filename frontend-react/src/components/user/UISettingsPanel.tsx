import { useTheme, ACCENT_CHOICES } from "../../lib/theme-context";

export default function UISettingsPanel() {
  const { mode, setMode, accent, setAccent } = useTheme();

  return (
    <div className="p-6 space-y-8">
      <section>
        <h2 className="text-base font-semibold mb-3">Appearance</h2>
        <div className="flex gap-3">
          <button
            aria-label="Light mode"
            onClick={() => setMode("light")}
            className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
              mode === "light"
                ? "border-accent bg-accent text-white"
                : "border-border bg-panel text-text-dim hover:border-accent"
            }`}
          >
            Light
          </button>
          <button
            aria-label="Dark mode"
            onClick={() => setMode("dark")}
            className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
              mode === "dark"
                ? "border-accent bg-accent text-white"
                : "border-border bg-panel text-text-dim hover:border-accent"
            }`}
          >
            Dark
          </button>
        </div>
      </section>

      <section>
        <h2 className="text-base font-semibold mb-3">Accent Color</h2>
        <div className="flex gap-3 flex-wrap">
          {ACCENT_CHOICES.map((color) => (
            <button
              key={color}
              aria-label={`accent ${color}`}
              onClick={() => setAccent(color)}
              style={{ backgroundColor: color }}
              className={`w-8 h-8 rounded-full transition-all ${
                accent === color
                  ? "ring-2 ring-offset-2 ring-offset-surface ring-white scale-110"
                  : "hover:scale-110"
              }`}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
