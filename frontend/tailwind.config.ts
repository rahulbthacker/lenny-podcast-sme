import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // claude.ai-inspired palette
        parchment: "#faf9f5",
        parchmentAlt: "#f5f4ee",
        ink: "#1a1a1a",
        inkMuted: "#6b6b6b",
        border: "#e7e5dc",
        accent: "#c96442",
        accentDark: "#a14f33",
        accentSoft: "#f4e4dc",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Inter", "sans-serif"],
        serif: ["Copernicus", "Tiempos Text", "Georgia", "serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
