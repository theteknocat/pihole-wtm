import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import tsParser from '@typescript-eslint/parser'

export default [
  js.configs.recommended,

  // Vue correctness rules — flat/essential avoids opinionated formatting rules
  // that conflict with the project's existing style (indent, attribute ordering, etc.)
  ...pluginVue.configs['flat/essential'],

  // TypeScript rules for .ts files
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      // TypeScript handles type-level globals (RequestInfo, RequestInit, etc.)
      'no-undef': 'off',
    },
  },

  // TypeScript parser for <script> blocks inside .vue files
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tsParser },
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      // Variables used only in the template are invisible to ESLint's script
      // analysis, causing false positives for these two rules.
      'no-useless-assignment': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
    },
  },
]
