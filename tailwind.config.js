/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#9E1B32', dark: '#6E1223', soft: '#FBEFF1', mist: '#F7F3F3', line: '#E2B4BD' },
        ink: { DEFAULT: '#1C1B1F', 2: '#2E2D33', 3: '#4A4850' },
      },
      fontFamily: { sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'], mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'] },
      keyframes: {
        rise: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'none' } },
        flow: { to: { strokeDashoffset: '-20' } },
      },
      animation: { rise: 'rise .45s ease-out both', flow: 'flow 1s linear infinite' },
    },
  },
  plugins: [],
};
