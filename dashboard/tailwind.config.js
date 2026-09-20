/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          blue: "#004b87",
          dark: "#003366",
          light: "#e8f0fe",
        }
      }
    },
  },
  plugins: [],
}