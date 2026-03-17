/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        mc: {
          bg: '#08080f',
          surface: '#0d0d1a',
          border: '#1a1a2e',
          accent: '#00ffc8',
          pink: '#ff6b9d',
          yellow: '#ffd166',
          purple: '#a78bfa',
          red: '#ff4444',
          text: '#e0e0e0',
          muted: '#8a8aad',
          dim: '#444',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
