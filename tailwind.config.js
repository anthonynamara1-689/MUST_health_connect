/**
 * Tailwind build config. Only needed if you change classes in the templates
 * and want to rebuild static/css/tailwind.css (see README, "Changing the look").
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./portal/**/*.py",
    "./tracker/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0E3F73", 900: "#0A2F57", 950: "#071F3B" },
        brand: { DEFAULT: "#14508C", 600: "#1A5FA3" },
        link: "#145A9E",
        sun: { DEFAULT: "#FFB547", 600: "#F2A12B", 50: "#FFF6E6" },
        ink: "#1B2430",
        muted: "#4E5866",
        subtle: "#6B7685",
        mist: "#F2F5F9",
        line: "#E3E7EC",
        sky: { 50: "#EEF4FA", 100: "#DCE7F3", 200: "#C3D6EA" },
        ok: { DEFAULT: "#1E7A45", 50: "#EAF6EF" },
        warn: { DEFAULT: "#9A5B00", 50: "#FFF4E0", 500: "#C26A00" },
        bad: { DEFAULT: "#B42318", 50: "#FDEDEB" },
      },
      fontFamily: {
        sans: ['"Public Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        // Navy-tinted shadows: resting cards barely lift, hovered and floating things lift more.
        rest: "0 1px 2px rgba(14, 63, 115, 0.06)",
        lift: "0 10px 28px -10px rgba(14, 63, 115, 0.28), 0 2px 6px rgba(14, 63, 115, 0.06)",
        float: "0 24px 60px -18px rgba(7, 31, 59, 0.45)",
      },
      maxWidth: { page: "76rem" },
    },
  },
  plugins: [],
};
