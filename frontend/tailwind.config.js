/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
          950: '#022c22',
        },
        examinex: {
          page: '#F4F1EA',
          section: '#EDE9E1',
          card: '#FAF9F6',
          text: '#243247',
          muted: '#5E6B7D',
          blue: '#2878D8',
          'blue-hover': '#2065B8',
          'blue-highlight': '#4C8FE8',
          'blue-soft': '#EAF2FC',
          teal: '#38A6A0',
          'teal-soft': '#E8F5F3',
          border: '#D9DDE3',
          'border-warm': '#DDD8CE',
          footer: '#E8E4DC',
          success: '#2FA878',
          warning: '#C98A2E',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Outfit', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
