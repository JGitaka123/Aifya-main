import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        'medical-blue': {
          DEFAULT: '#1A5276',
          light: '#2980B9',
          dark: '#154360'
        },
        'status-passed': '#27AE60',
        'status-warning': '#F39C12',
        'status-blocked': '#C0392B',
        'status-overridden': '#2980B9'
      },
    },
  },
  plugins: [],
};
export default config;
