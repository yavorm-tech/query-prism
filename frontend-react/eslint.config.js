import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // We intentionally co-locate context providers with their hooks/constants in one file.
      'react-refresh/only-export-components': 'off',
      // Async loaders kicked off in mount effects do not setState synchronously; rule is a false positive here.
      'react-hooks/set-state-in-effect': 'off',
      // `any` is permitted at unavoidable library boundaries (axios errors, SSE JSON) per project spec; keep visible as a warning.
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
])
