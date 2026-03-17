/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        mc: {
          bg: '#fafafa',
          surface: '#ffffff',
          border: '#e5e7eb',
          accent: '#2563eb',
          'accent-light': '#dbeafe',
          green: '#059669',
          'green-light': '#d1fae5',
          yellow: '#d97706',
          'yellow-light': '#fef3c7',
          red: '#dc2626',
          'red-light': '#fee2e2',
          purple: '#7c3aed',
          'purple-light': '#ede9fe',
          text: '#111827',
          secondary: '#374151',
          muted: '#6b7280',
          dim: '#9ca3af',
          subtle: '#f3f4f6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.04)',
        'dropdown': '0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.04)',
      },
      borderRadius: {
        'xl': '12px',
      },
    },
  },
  plugins: [],
}
