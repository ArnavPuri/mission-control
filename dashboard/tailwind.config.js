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
          // Primary accent
          accent: '#2563eb',
          'accent-hover': '#1d4ed8',
          'accent-light': '#dbeafe',
          // Semantic: success
          green: '#059669',
          'green-hover': '#047857',
          'green-light': '#d1fae5',
          'green-dark': '#065f46',
          'green-text': '#047857',
          'green-bg': '#ecfdf5',
          'green-bg-dark': '#022c22',
          // Semantic: warning
          yellow: '#d97706',
          'yellow-light': '#fef3c7',
          'yellow-dark': '#92400e',
          'yellow-text': '#b45309',
          'yellow-bg': '#fffbeb',
          'yellow-bg-dark': '#422006',
          // Semantic: error/danger
          red: '#dc2626',
          'red-hover': '#b91c1c',
          'red-light': '#fee2e2',
          'red-dark': '#991b1b',
          'red-text': '#dc2626',
          'red-bg': '#fef2f2',
          'red-bg-dark': '#450a0a',
          // Semantic: info / purple
          purple: '#7c3aed',
          'purple-light': '#ede9fe',
          'purple-dark': '#5b21b6',
          'purple-text': '#6d28d9',
          'purple-bg': '#f5f3ff',
          'purple-bg-dark': '#2e1065',
          // Semantic: blue (info variant)
          blue: '#2563eb',
          'blue-light': '#dbeafe',
          'blue-text': '#1d4ed8',
          'blue-bg': '#eff6ff',
          'blue-bg-dark': '#172554',
          // Neutral text
          text: '#111827',
          secondary: '#374151',
          muted: '#6b7280',
          dim: '#9ca3af',
          subtle: '#f3f4f6',
          // Priority
          'priority-critical': '#dc2626',
          'priority-high': '#f97316',
          'priority-medium': '#3b82f6',
          'priority-low': '#9ca3af',
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
