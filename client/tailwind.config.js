/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: '#06080d',
          900: '#0b0f17',
          850: '#101622',
          800: '#161f30',
          750: '#1c283f',
          700: '#243350',
          600: '#344970',
        },
        sand: {
          50: '#fcfaf6',
          100: '#f7f2e8',
          200: '#ecdfc9',
          400: '#cbb389',
          500: '#b09462',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
