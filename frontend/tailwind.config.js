/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Cosmic Purple + Amber Design System ──────────────────────────
        // Deep space purple backgrounds
        space: {
          950: '#0A0620',
          900: '#130D2E',
          850: '#1a1040',
          800: '#1E1450',
          750: '#151038',
          700: '#1B1545',
          600: '#241D5C',
          500: '#2D2575',
        },
        // Electric purple — primary accent
        purple: {
          900: '#2E1065',
          800: '#3B0764',
          700: '#4C1D95',
          600: '#5B21B6',
          500: '#7C3AED',
          400: '#8B5CF6',
          300: '#A78BFA',
          200: '#C4B5FD',
          100: '#DDD6FE',
          50:  '#EDE9FE',
        },
        // Amber gold — hot accent for scores, alerts, highlights
        amber: {
          600: '#D97706',
          500: '#F59E0B',
          400: '#FBBF24',
          300: '#FCD34D',
          200: '#FDE68A',
          100: '#FEF3C7',
        },
        // Fuchsia — tertiary pop for special states
        fuchsia: {
          500: '#D946EF',
          400: '#E879F9',
          300: '#F0ABFC',
        },
        // Neutral text
        ink: {
          900: '#F5F3FF',
          800: '#DDD6FE',
          700: '#C4B5FD',
          600: '#A78BFA',
          500: '#7C3AED',
          400: '#6D28D9',
          muted: '#8B7CB8',
          dim:   '#5C4F8A',
        },
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        mono:    ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Inter', 'sans-serif'],
      },
      backgroundImage: {
        // Constellation grid — dots at intersections, references embedding space
        'constellation': `radial-gradient(circle, rgba(139,92,246,0.15) 1px, transparent 1px)`,
        'grid-purple': `
          linear-gradient(rgba(124,58,237,0.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(124,58,237,0.06) 1px, transparent 1px)
        `,
        // Hero gradients
        'hero-glow':     'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(124,58,237,0.35) 0%, transparent 70%)',
        'amber-glow':    'radial-gradient(ellipse 60% 40% at 80% 20%, rgba(245,158,11,0.12) 0%, transparent 60%)',
        'card-shine':    'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0) 60%)',
        'sidebar-grad':  'linear-gradient(180deg, #0B0820 0%, #07051A 100%)',
        // Score bar gradient — amber to purple
        'score-bar':     'linear-gradient(90deg, #F59E0B, #7C3AED)',
        // Shimmer
        'shimmer':       'linear-gradient(90deg, rgba(124,58,237,0.0) 0%, rgba(124,58,237,0.08) 50%, rgba(124,58,237,0.0) 100%)',
      },
      backgroundSize: {
        'constellation': '32px 32px',
        'grid': '40px 40px',
      },
      boxShadow: {
        'glow-purple': '0 0 24px rgba(124,58,237,0.3), 0 0 80px rgba(124,58,237,0.1)',
        'glow-amber':  '0 0 20px rgba(245,158,11,0.3), 0 0 60px rgba(245,158,11,0.08)',
        'glow-sm':     '0 0 12px rgba(124,58,237,0.2)',
        'card':        '0 4px 32px rgba(0,0,0,0.5), 0 1px 0 rgba(139,92,246,0.08) inset',
        'card-hover':  '0 8px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(139,92,246,0.2)',
        'metric':      '0 2px 16px rgba(124,58,237,0.2)',
        'amber-metric':'0 2px 16px rgba(245,158,11,0.2)',
      },
      animation: {
        // Motion system — deliberate, orchestrated
        'fade-up':      'fade-up 0.5s cubic-bezier(0.16,1,0.3,1)',
        'fade-in':      'fade-in 0.4s ease-out',
        'scale-in':     'scale-in 0.35s cubic-bezier(0.16,1,0.3,1)',
        'slide-right':  'slide-right 0.4s cubic-bezier(0.16,1,0.3,1)',
        'glow-pulse':   'glow-pulse 3s ease-in-out infinite',
        'amber-pulse':  'amber-pulse 2.5s ease-in-out infinite',
        'float':        'float 7s ease-in-out infinite',
        'shimmer':      'shimmer 2.5s linear infinite',
        'spin-slow':    'spin 8s linear infinite',
        'constellation':'constellation-drift 20s ease-in-out infinite',
        'score-fill':   'score-fill 1s cubic-bezier(0.16,1,0.3,1)',
        'node-ping':    'node-ping 1.5s ease-in-out infinite',
        'scan':         'scan 10s linear infinite',
        'orb-move':     'orb-move 12s ease-in-out infinite alternate',
      },
      keyframes: {
        'fade-up': {
          '0%':   { transform: 'translateY(24px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' }, '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%':   { transform: 'scale(0.92)', opacity: '0' },
          '100%': { transform: 'scale(1)',    opacity: '1' },
        },
        'slide-right': {
          '0%':   { transform: 'translateX(-16px)', opacity: '0' },
          '100%': { transform: 'translateX(0)',      opacity: '1' },
        },
        'glow-pulse': {
          '0%,100%': { boxShadow: '0 0 20px rgba(124,58,237,0.2)' },
          '50%':     { boxShadow: '0 0 48px rgba(124,58,237,0.55), 0 0 100px rgba(124,58,237,0.15)' },
        },
        'amber-pulse': {
          '0%,100%': { boxShadow: '0 0 16px rgba(245,158,11,0.2)' },
          '50%':     { boxShadow: '0 0 36px rgba(245,158,11,0.6), 0 0 80px rgba(245,158,11,0.12)' },
        },
        'float': {
          '0%,100%': { transform: 'translateY(0)' },
          '50%':     { transform: 'translateY(-10px)' },
        },
        'shimmer': {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'constellation-drift': {
          '0%,100%': { backgroundPosition: '0 0' },
          '50%':     { backgroundPosition: '16px 16px' },
        },
        'score-fill': {
          '0%':   { width: '0%' },
          '100%': { width: 'var(--score-width)' },
        },
        'node-ping': {
          '0%,100%': { transform: 'scale(1)',    opacity: '1' },
          '50%':     { transform: 'scale(1.15)', opacity: '0.8' },
        },
        'scan': {
          '0%':   { transform: 'translateY(-100vh)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'orb-move': {
          '0%':   { transform: 'translate(0, 0) scale(1)' },
          '100%': { transform: 'translate(40px, -30px) scale(1.1)' },
        },
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'bounce-out': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
    },
  },
  plugins: [],
};
