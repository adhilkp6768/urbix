/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101826",
        shell: "#15202e",
        panel: "#1b2938",
        raised: "#243447",
        line: "#38536c",
        mist: "#b7c9d8",
        paper: "#e9f3f8",
        cyan: "#6ad7ef",
        good: "#7dcea0",
        warn: "#e4c56a",
        bad: "#f0997f",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
