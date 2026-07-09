/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Industrial Blueprint design system — canvas white + ink + 2 accents ──
        bg: {
          950: '#fafafa', // canvas white (page background)
          900: '#fafafa',
          850: '#FFFFFF', // card surface
          800: '#F5F5F5', // hover lift
          700: '#EDEDED', // secondary button bg
        },
        border: {
          hairline: '#000000',
          DEFAULT:  '#000000',
          strong:   '#000000',
        },
        // Two accents — orange for data/emphasis, yellow for primary actions. No others.
        accent: {
          900: '#7a2000',
          700: '#b33d16',
          600: '#e04a1f',
          500: '#ff5b29', // Action Orange
          400: '#ff7d54',
          300: '#ffa382',
          yellow: '#f5ff80', // Highlight Yellow — primary buttons/CTAs only
        },
        // Text hierarchy
        text: {
          primary:   '#000000', // midnight ink — headings, body
          secondary: '#6c6c6c', // shadow gray — descriptions, labels
          muted:     '#b3b3b3', // silverline — captions/decorative only
          disabled:  '#d4d4d4',
        },
        // Status — reserved for pass/fail/degraded states only
        status: {
          success: '#10B981',
          error:   '#EF4444',
          warning: '#F59E0B',
        },
      },
      fontFamily: {
        sans:    ['Geist', 'Inter', 'system-ui', 'sans-serif'],
        mono:    ['Geist Mono', 'JetBrains Mono', 'IBM Plex Mono', 'monospace'],
        display: ['Geist', 'Inter', 'sans-serif'],
      },
      fontSize: {
        caption:    ['14px', { lineHeight: '1.5',  letterSpacing: '-0.42px' }],
        body:       ['16px', { lineHeight: '1.5',  letterSpacing: '-0.48px' }],
        subheading: ['24px', { lineHeight: '1.33', letterSpacing: '-0.48px' }],
        heading:    ['52px', { lineHeight: '1.1',  letterSpacing: '-1.04px' }],
        display:    ['80px', { lineHeight: '1.1',  letterSpacing: '-2.4px' }],
      },
      borderRadius: {
        DEFAULT: '4px',  // buttons/inputs
        sm: '4px',       // buttons/inputs
        md: '8px',       // links
        lg: '12px',      // cards
        full: '9999px',  // tags/pills
      },
      spacing: {
        section: '40px',
        card: '16px',
      },
      maxWidth: {
        'container': '1400px',
      },
      boxShadow: {
        // Signature element: hard offset shadow, no blur, no gradients
        'offset':      '5px 5px 0px 0px rgb(0,0,0)',
        'offset-sm':   '3px 3px 0px 0px rgb(0,0,0)',
        'offset-hover':'rgba(0,0,0,0.6) 0px 3px 4px 0px',
      },
      animation: {
        'fade-up':      'fade-up 0.4s cubic-bezier(0.16,1,0.3,1)',
        'fade-in':      'fade-in 0.3s ease-out',
        'node-active':  'node-active 1.2s ease-in-out infinite',
      },
      keyframes: {
        'fade-up': {
          '0%':   { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' }, '100%': { opacity: '1' },
        },
        'node-active': {
          '0%,100%': { opacity: '1' },
          '50%':     { opacity: '0.6' },
        },
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};
