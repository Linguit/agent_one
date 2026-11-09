import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from '@playwright/test'
import { createServer } from 'vite'
import { repositoryRoot, temporaryProject } from './temporary-project.mjs'

const fixture = temporaryProject('apps/frontend')
const root = fixture.root
const frontend = join(root, 'apps/frontend')
const server = await createServer({ root: frontend, configFile: join(frontend, 'vite.config.ts'),
  server: { host: '127.0.0.1', port: 0, open: false }, logLevel: 'error' })
let browser
try {
  await server.listen()
  const address = server.httpServer.address()
  assert.ok(address && typeof address !== 'string')
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  const response = await page.goto(`http://127.0.0.1:${address.port}`, { waitUntil: 'networkidle' })
  assert.equal(response.status(), 200)
  await page.locator('h1').waitFor()
  assert.ok(await page.locator('h1').textContent())
  assert.equal(await page.title(), await page.locator('h1').textContent())
  assert.equal(await page.locator('article').count(), 3)
  assert.ok((await page.locator('footer').textContent()).includes('当前不包含认证'))
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
  // 开发服务器也不得允许直接读取仓库本机配置。
  for (const name of ['project.json', 'user.project.json']) {
    const configPath = join(root, 'config', name).replaceAll('\\', '/')
    const denied = await page.request.get(`http://127.0.0.1:${address.port}/@fs/${configPath}`)
    assert.equal(denied.status(), 403)
  }
  assert.deepEqual(errors, [])
  mkdirSync(join(repositoryRoot, '.cache'), { recursive: true })
  await page.screenshot({ path: join(repositoryRoot, '.cache/desktop-foundation.png'), fullPage: true })
  console.log('桌面 1440x900：标题、三张卡片、范围说明、无横向溢出、控制台无错误、配置请求 403')
} finally {
  await browser?.close()
  await server.close()
  fixture.cleanup()
}
