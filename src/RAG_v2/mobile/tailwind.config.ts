import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx}', './App.tsx'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#3b82f6', foreground: '#ffffff' },
        secondary: { DEFAULT: '#f3f4f6', foreground: '#161a1f' },
        muted: { DEFAULT: '#f3f4f6', foreground: '#6b7280' },
        chat: {
          user: '#eff6ff',
          assistant: '#ffffff',
        },
      },
      fontFamily: { sans: ['Inter'] },
    },
  },
} satisfies Config;
