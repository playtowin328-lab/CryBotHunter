/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101418",
        panel: "#f6f8fb",
        line: "#d7dee8",
        accent: "#0f766e",
        warning: "#b45309",
        danger: "#b91c1c"
      }
    }
  },
  plugins: []
};
