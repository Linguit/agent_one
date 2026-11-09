import assert from 'node:assert/strict'
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'vite'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const cache = join(root, '.cache')
mkdirSync(cache, { recursive: true })
const temporary = mkdtempSync(join(cache, 'public-config-'))
const child = relative(cache, temporary)
assert.ok(child && !child.startsWith('..') && !child.includes(sep), '临时目录必须在本项目缓存内')

try {
  const frontend = join(temporary, 'apps/frontend')
  mkdirSync(frontend, { recursive: true })
  for (const name of ['src', 'build', 'index.html', 'vite.config.ts', 'package.json']) {
    cpSync(join(root, 'apps/frontend', name), join(frontend, name), { recursive: true })
  }
  symlinkSync(join(root, 'node_modules'), join(temporary, 'node_modules'), 'junction')
  const configDir = join(temporary, 'config')
  mkdirSync(configDir)
  const secrets = ['LLM', 'CLS', 'MCP', 'MINIO', 'FRONTEND', 'ANALYTICS_PRIVATE', 'OVERRIDE']
    .map((name) => `PRIVATE_SENTINEL_${name}_P01_9e41`)
  const [llm, cls, mcp, minio, frontendSecret, analyticsPrivate, override] = secrets
  writeFileSync(join(configDir, 'project.json'), JSON.stringify({
    frontend: { title: 'PUBLIC_TITLE_P01', apiBaseUrl: '/PUBLIC_API_P01', secret: frontendSecret },
    analytics: { public: false, key: analyticsPrivate },
    llm: { apiKey: llm }, cls: { secretKey: cls },
    mcp: { password: mcp }, minio: { secretKey: minio },
  }))
  const files = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    return entry.isDirectory() ? files(path) : [path]
  })
  for (const isPublic of [false, true]) {
    writeFileSync(join(configDir, 'user.project.json'), JSON.stringify({
      frontend: { title: 'PUBLIC_OVERRIDE_TITLE_P01' },
      llm: { apiKey: override },
      analytics: { public: isPublic, key: isPublic ? 'PUBLIC_ANALYTICS_P01' : analyticsPrivate },
    }))
    const outDir = join(temporary, isPublic ? 'dist-public' : 'dist-private')
    await build({ root: frontend, configFile: join(frontend, 'vite.config.ts'),
      build: { outDir, emptyOutDir: true }, logLevel: 'warn' })
    const outputs = files(outDir)
    assert.ok(outputs.length > 0)
    const all = Buffer.concat(outputs.map((path) => readFileSync(path)))
    for (const secret of secrets) assert.ok(!all.includes(Buffer.from(secret)), '私密哨兵泄漏')
    assert.ok(all.includes(Buffer.from('PUBLIC_OVERRIDE_TITLE_P01')), '覆盖标题未进入产物')
    assert.ok(all.includes(Buffer.from('/PUBLIC_API_P01')), '基础 URL 未被保留')
    assert.equal(all.includes(Buffer.from('PUBLIC_ANALYTICS_P01')), isPublic)
    console.log(`公开 analytics=${isPublic}：${outputs.length} 个产物，7 个私密哨兵均未出现`)
  }
} finally {
  // 上方已验证绝对目标严格位于本项目 .cache 内；junction 不递归跟随。
  rmSync(temporary, { recursive: true, force: true })
}
