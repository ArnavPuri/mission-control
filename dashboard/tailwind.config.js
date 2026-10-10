const colors = require('tailwindcss/colors');

const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./app/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Neutral grays everywhere are zinc
        gray: colors.zinc,
        // Semantic tokens (see globals.css). Older class names map onto them too.
        mc: {
          canvas: token('canvas'),
          bg: token('canvas'),
          panel: token('panel'),
          surface: token('panel'),
          subtle: token('subtle'),
          hover: token('hover'),
          line: token('line'),
          border: token('line'),
          'line-strong': token('line-strong'),
          text: token('fg'),
          secondary: token('fg-secondary'),
          muted: token('fg-muted'),
          dim: token('fg-faint'),
          accent: token('accent'),
          'accent-hover': token('accent-hover'),
          'accent-light': token('accent-soft'),
          'accent-fg': token('accent-fg'),
          green: colors.emerald[600],
          'green-light': colors.emerald[50],
          yellow: colors.amber[600],
          'yellow-light': colors.amber[50],
          red: colors.red[600],
          'red-light': colors.red[50],
          purple: colors.violet[600],
          'purple-light': colors.violet[50],
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', '16px'],
        xs: ['12px', '16px'],
        sm: ['13px', '20px'],
        base: ['14px', '22px'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(var(--shadow-color) / 0.04)',
        'card-hover': '0 2px 8px -2px rgb(var(--shadow-color) / 0.08)',
        dropdown: '0 0 0 1px rgb(var(--line)), 0 8px 24px -6px rgb(var(--shadow-color) / 0.16)',
        sheet: '-12px 0 40px -12px rgb(var(--shadow-color) / 0.25)',
      },
      borderRadius: {
        xl: '12px',
      },
    },
  },
  plugins: [],
};
