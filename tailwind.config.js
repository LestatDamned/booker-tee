/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/app/templates/**/*.html", "./src/app/**/*.py"],
  theme: {
    extend: {
      colors: {
        base: "#11111b",
        mantle: "#181825",
        crust: "#1e1e2e",
        text: "#cdd6f4",
        subtext: "#a6adc8",
        blue: "#89b4fa",
        green: "#a6e3a1",
        border: "#585b70",
      },
      borderRadius: {
        DEFAULT: "0",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
