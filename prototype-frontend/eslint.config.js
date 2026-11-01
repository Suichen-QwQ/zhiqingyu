import vue from 'eslint-plugin-vue'
import tsParser from '@typescript-eslint/parser'

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  ...vue.configs['flat/essential'],
  {
    files: ['**/*.{ts,vue}'],
    languageOptions: { parserOptions: { parser: tsParser, sourceType: 'module' } },
    rules: { 'vue/multi-word-component-names': 'off', 'no-unreachable': 'error', 'no-dupe-keys': 'error', 'no-dupe-args': 'error' },
  },
  { files: ['**/*.ts'], languageOptions: { parser: tsParser } },
]
