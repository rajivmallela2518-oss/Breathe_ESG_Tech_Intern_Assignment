/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0fdf4",
          600: "#16a34a",
          700: "#15803d",
        },
      },
    },
  },
  plugins: [],
};
