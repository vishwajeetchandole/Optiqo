/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // ── Page / shell
        page:    '#BDB4FE',  // lavender page bg
        // ── Surfaces
        surface: {
          DEFAULT: '#FFFFFF',
          sidebar: '#F6F3FF',
          tint:    '#EFEBFF',
        },
        // ── Primary
        primary: {
          DEFAULT: '#7B68F5',
          lilac:   '#B5AAF9',
        },
        // ── Ink / text
        ink: {
          DEFAULT: '#14121F',
          muted:   '#8E8BA0',
        },
        // ── Border
        border: '#E4E0F0',
        // ── Status
        success: {
          bg:   '#E3F6EA',
          text: '#1E9E57',
        },
        danger: {
          bg:   '#FDE6E6',
          text: '#E04848',
        },
        warning: {
          bg:   '#FFF1D6',
          text: '#B7791F',
        },
        // ── Chart palette (referenced via CSS vars in components)
        chart: {
          violet: '#7B68F5',
          lilac:  '#B5AAF9',
          dark:   '#3B3A45',
          grey1:  '#8C8A96',
          grey2:  '#C9C7D1',
        },
        // ── Dark-mode surfaces (applied via CSS vars; kept here for IDE hints)
        dark: {
          surface: '#1C1A2B',
          sidebar: '#17152A',
          border:  '#2C2942',
          ink:     '#EAE8FF',
          muted:   '#6B6880',
        },
      },
      borderRadius: {
        'pill':  '9999px',
        'card':  '28px',
        'shell': '32px',
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(20,18,31,0.04)',
        'none': 'none',
      },
      // Map CSS vars so Tailwind utilities read from the token layer
      backgroundColor: ({ theme }) => ({
        ...theme('colors'),
        'token-page':    'var(--color-page)',
        'token-surface': 'var(--color-surface)',
        'token-sidebar': 'var(--color-sidebar)',
        'token-tint':    'var(--color-tint)',
        'token-primary': 'var(--color-primary)',
        'token-border':  'var(--color-border)',
      }),
      textColor: ({ theme }) => ({
        ...theme('colors'),
        'token-ink':     'var(--color-ink)',
        'token-muted':   'var(--color-muted)',
        'token-primary': 'var(--color-primary)',
      }),
      borderColor: ({ theme }) => ({
        ...theme('colors'),
        'token':         'var(--color-border)',
      }),
    },
  },
  plugins: [
    require('@tailwindcss/forms')({ strategy: 'class' }),
  ],
}
