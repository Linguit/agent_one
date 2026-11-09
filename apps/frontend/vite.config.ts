import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
// @ts-ignore
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { loadPublicConfig } from './build/project-config'

// @ts-ignore
const frontendRoot = dirname(fileURLToPath(import.meta.url))
const root = resolve(frontendRoot, '../..')

export default defineConfig({
  plugins: [vue()],
  envDir: resolve(frontendRoot, '.no-project-env'),
  envPrefix: [],
  define: { __PUBLIC_CONFIG__: JSON.stringify(loadPublicConfig(resolve(root, 'config'))) },
  server: {
    host: '127.0.0.1',
    fs: {
      strict: true,
      allow: [frontendRoot, resolve(root, 'packages/api-contracts'), resolve(root, 'node_modules')],
      deny: ['**/config/**', '**/.env*', '**/*.pem', '**/.git/**'],
    },
  },
  preview: { host: '127.0.0.1' },
})
