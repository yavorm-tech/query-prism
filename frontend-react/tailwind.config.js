/** @type {import('tailwindcss').Config} */
const flowbite = require("flowbite-react/tailwind");
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    flowbite.content(),
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: "var(--color-surface)",
        panel: "var(--color-panel)",
        border: "var(--color-border)",
        accent: "var(--accent)",
        "accent-dim": "var(--accent-dim)",
        muted: "var(--color-muted)",
        "text-dim": "var(--color-text-dim)",
        text: "var(--color-text)",
        foreground: "var(--color-text)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [flowbite.plugin()],
};
