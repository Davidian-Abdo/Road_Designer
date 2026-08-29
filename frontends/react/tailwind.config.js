/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // BeamStack palette — mirrors frontends/streamlit/app.py's inline CSS
        // (see the .beamstack-* classes there). Kept in sync by convention,
        // not by shared code — the two frontends are separate products.
        navy: "#202a3a",
        ink: "#18212f",
        accent: {
          DEFAULT: "#d92727",
          50: "#fdf2f2",
        },
        muted: "#697386",
        panel: "#f9fafc",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
