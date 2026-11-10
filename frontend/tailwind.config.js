/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#e7edf2",
        shell: "#f4f7fa",
        panel: "#ffffff",
        raised: "#eef3f7",
        line: "#c5d0da",
        mist: "#5c6e7d",
        paper: "#14202b",
        cyan: "#1f6f8b",
        accent: "#1f6f8b",
        sand: "#9a7b4f",
        good: "#2f8f6b",
        warn: "#b8862a",
        bad: "#c45c4a",
      },
      fontFamily: {
        sans: ["Source Sans 3", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "Source Sans 3", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        soft: "0 10px 28px rgba(20, 32, 43, 0.08)",
        glow: "0 0 0 1px rgba(31, 111, 139, 0.18), 0 14px 28px rgba(20, 32, 43, 0.08)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 420ms ease-out both",
      },
    },
  },
  plugins: [],
};
