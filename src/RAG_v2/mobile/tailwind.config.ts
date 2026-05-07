import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx}', './App.tsx'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#6366f1', foreground: '#ffffff' },
        secondary: { DEFAULT: '#f1f5f9', foreground: '#334155' },
        muted: { DEFAULT: '#f1f5f9', foreground: '#64748b' },
        chat: {
          user: '#ede9fe',
          assistant: '#ffffff',
        },
      },
      fontFamily: { sans: ['Inter'] },
    },
  },
} satisfies Config;
