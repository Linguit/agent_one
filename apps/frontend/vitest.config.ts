// @ts-ignore
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  define: { __PUBLIC_CONFIG__: JSON.stringify({ title: '测试骨架', apiBaseUrl: '/api' }) },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'] },
})
