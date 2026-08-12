import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        graphite: {
          950: "#14171A",
          900: "#1C2024",
          800: "#282D33",
          700: "#3D444C",
          600: "#565F69",
          400: "#8A9099",
          200: "#D3D7DC",
          100: "#E7E9EC",
          50: "#F6F7F8",
        },
        signal: {
          amber: "#C17F2B",
          "amber-soft": "#F3E2C8",
          green: "#1D8A5E",
          "green-soft": "#D6EFE3",
          red: "#C4432B",
          "red-soft": "#F5DDD6",
          gray: "#8A9099",
        },
      },
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.4rem" }],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
      },
      boxShadow: {
        "glow-amber": "0 0 0 3px rgba(193, 127, 43, 0.18)",
        "glow-green": "0 0 0 3px rgba(29, 138, 94, 0.18)",
        "glow-red": "0 0 0 3px rgba(196, 67, 43, 0.18)",
        card: "0 1px 2px rgba(20, 23, 26, 0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
