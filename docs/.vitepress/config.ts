import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'

// @ts-ignore
const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = resolve(docsRoot, '..')

export default defineConfig({
  lang: 'zh-CN',
  title: 'Super AI 工程基础',
  description: '安全单仓库骨架与质量基线',
  srcExclude: ['README.md'],
  vite: {
    server: {
      host: '127.0.0.1',
      fs: {
        strict: true,
        allow: [docsRoot, resolve(root, 'node_modules')],
        deny: ['**/config/**', '**/.env*', '**/*.pem', '**/.git/**'],
      },
    },
    preview: { host: '127.0.0.1' },
  },
})
