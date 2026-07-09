/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: {
          cyan: '#0EA5E9',
          purple: '#7C3AED',
        },
        text: {
          primary: '#0F172A',
          secondary: '#475569',
          muted: '#64748B',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
