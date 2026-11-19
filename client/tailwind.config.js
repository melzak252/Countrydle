/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        app: {
          canvas: 'rgb(var(--app-canvas) / <alpha-value>)',
          surface: 'rgb(var(--app-surface) / <alpha-value>)',
          'surface-raised': 'rgb(var(--app-surface-raised) / <alpha-value>)',
          'surface-muted': 'rgb(var(--app-surface-muted) / <alpha-value>)',
          text: 'rgb(var(--app-text) / <alpha-value>)',
          'text-secondary': 'rgb(var(--app-text-secondary) / <alpha-value>)',
          'text-muted': 'rgb(var(--app-text-muted) / <alpha-value>)',
          border: 'rgb(var(--app-border) / <alpha-value>)',
          accent: 'rgb(var(--app-accent) / <alpha-value>)',
          'accent-hover': 'rgb(var(--app-accent-hover) / <alpha-value>)',
          focus: 'rgb(var(--app-focus) / <alpha-value>)',
        },
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
