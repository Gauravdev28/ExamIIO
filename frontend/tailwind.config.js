/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ExamIIO Primary Brand (Blue)
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb', // Primary brand action
          700: '#1d4ed8', // Hover / Dark action
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        // Warm Canvas & Surface System (Anti-plain-white)
        canvas: {
          DEFAULT: '#FAF8F2', // Primary warm ivory/cream application canvas
          subtle: '#F4F1EA',  // Secondary section / deeper warm canvas
          card: '#FFFDF8',    // Warm off-white card surface
          cardHover: '#F7F4EC', // Hover state for warm cards
          elevated: '#FFFFFF', // High-contrast elevated surface
          tinted: '#F0F6FF',  // Soft blue-tinted highlighted surface
          dark: '#102A56',    // Deep navy inverse canvas
        },
        // Deep Navy Typography & Contrast Gradients
        navy: {
          950: '#0A1B36', // Ultra deep headings
          900: '#102A56', // Primary deep text
          800: '#1E293B', // Secondary text
          700: '#334155', // Subheadings & strong labels
          600: '#475569', // Body text
          500: '#64748B', // Muted metadata & placeholders
          400: '#94A3B8', // Icons & subtle borders
          300: '#CBD5E1', // Hairline dividers
          200: '#E2E8F0',
          100: '#F1F5F9',
          50: '#F8FAFC',
        },
        // Warm Borders & Dividers
        borderWarm: {
          DEFAULT: '#E5E0D8', // Standard warm card border
          subtle: '#EDE8DF',  // Subtle table row border
          strong: '#DCD6CB',  // Focused/active border
        },
        // Semantic Accents (Meaningful hierarchy)
        accent: {
          blue: '#2563EB',    // Primary / Action
          cyan: '#06B6D4',    // Information / Guidance
          violet: '#7C3AED',  // Analytics / Special Features
          emerald: '#059669', // Success / Completed / Healthy
          amber: '#D97706',   // Attention / Upcoming
          orange: '#EA580C',  // Scheduled / Important Alert
          coral: '#DC2626',   // Danger / Violation / Critical
        },
        // Backward-compatibility aliases for legacy examinex classes
        examinex: {
          page: '#FAF8F2',
          section: '#F4F1EA',
          card: '#FFFDF8',
          text: '#102A56',
          muted: '#64748B',
          blue: '#2563EB',
          'blue-hover': '#1D4ED8',
          'blue-highlight': '#3B82F6',
          'blue-soft': '#EFF6FF',
          teal: '#06B6D4',
          'teal-soft': '#ECFEFF',
          border: '#E5E0D8',
          'border-warm': '#EDE8DF',
          footer: '#F4F1EA',
          success: '#059669',
          warning: '#D97706',
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Outfit', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'warm-xs': '0 1px 2px 0 rgba(16, 42, 86, 0.04)',
        'warm-sm': '0 1px 3px 0 rgba(16, 42, 86, 0.06), 0 1px 2px -1px rgba(16, 42, 86, 0.04)',
        'warm-md': '0 4px 6px -1px rgba(16, 42, 86, 0.07), 0 2px 4px -2px rgba(16, 42, 86, 0.04)',
        'warm-lg': '0 10px 15px -3px rgba(16, 42, 86, 0.08), 0 4px 6px -4px rgba(16, 42, 86, 0.04)',
        'warm-xl': '0 20px 25px -5px rgba(16, 42, 86, 0.10), 0 8px 10px -6px rgba(16, 42, 86, 0.04)',
        'glow-brand': '0 0 0 3px rgba(37, 99, 235, 0.18)',
        'glow-emerald': '0 0 0 3px rgba(5, 150, 105, 0.18)',
        'glow-amber': '0 0 0 3px rgba(217, 119, 6, 0.18)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
        'slide-down': 'slideDown 0.2s ease-out',
        'pulse-subtle': 'pulseSubtle 2s infinite ease-in-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
}
