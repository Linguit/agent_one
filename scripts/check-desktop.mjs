import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium, expect } from '@playwright/test'
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
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  const user = { id: 'desktop', email: 'desktop@example.test' }
  let registered = false
  let session = false
  let uploaded = false
  let indexTask = false
  let mcpConnections = []
  const document = { id: 'desktop-document', filename: 'desktop.md', indexStatus: 'pending' }
  await page.route('**/api/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const validSession = session && request.headers().authorization === 'Bearer desktop-token'
    if (path === '/api/auth/register') {
      assert.equal(request.method(), 'POST')
      assert.deepEqual(request.postDataJSON(), { email: user.email, password: 'desktop-test-password' })
      registered = true
      return route.fulfill({ json: { ok: true, data: user } })
    }
    if (path === '/api/auth/login') {
      assert.ok(registered)
      assert.equal(request.method(), 'POST')
      assert.deepEqual(request.postDataJSON(), { email: user.email, password: 'desktop-test-password' })
      session = true
      return route.fulfill({ json: { ok: true, data: { token: 'desktop-token', user } } })
    }
    if (path === '/api/auth/me' && validSession) return route.fulfill({ json: { ok: true, data: user } })
    if (path === '/api/auth/logout' && validSession) {
      assert.equal(request.method(), 'POST')
      session = false
      return route.fulfill({ json: { ok: true, data: { loggedOut: true } } })
    }
    if (path === '/api/health') return route.fulfill({ json: { ok: true, data: { status: 'ok' } } })
    // Browser-only API fixture; this is not a real MCP smoke test.
    if (path.startsWith('/api/mcp/connections') && validSession) {
      const method = request.method()
      if (method === 'POST' && path.endsWith(':check')) {
        mcpConnections = mcpConnections.map(row => ({ ...row,
          lastCheck: '2026-11-21T01:00:00Z', lastError: null,
          discoveredTools: [{ name: 'browser_fixture_tool', description: '浏览器测试夹具工具', inputSchema: { type: 'object' } }],
        }))
      } else if (method === 'DELETE') mcpConnections = []
      else if (method !== 'GET') {
        mcpConnections = [{ ...request.postDataJSON(), id: 'desktop-mcp', owner: user.id,
          lastCheck: null, lastError: null, discoveredTools: [],
          createdAt: '2026-11-21T00:00:00Z', updatedAt: '2026-11-21T00:00:00Z' }]
      }
      return route.fulfill({ json: { ok: true, data: method === 'GET' ? mcpConnections
        : method === 'DELETE' ? { deleted: true } : mcpConnections[0] } })
    }
    if (path === '/api/knowledge-bases' && validSession) {
      return route.fulfill({ json: { ok: true, data: [{ id: 'desktop-kb', name: '默认知识库' }] } })
    }
    if (path === '/api/knowledge-bases/desktop-kb/documents' && validSession) {
      if (request.method() === 'POST') {
        assert.match(request.headers()['content-type'], /^multipart\/form-data; boundary=/)
        assert.match(request.postData(), /filename="desktop\.md"/)
        uploaded = true
        return route.fulfill({ json: { ok: true, data: document } })
      }
      return route.fulfill({ json: { ok: true, data: uploaded ? [document] : [] } })
    }
    if (path === '/api/knowledge-bases/desktop-kb/documents/desktop-document/index-tasks' && validSession) {
      assert.ok(uploaded)
      if (request.method() === 'POST') indexTask = true
      return route.fulfill({ json: { ok: true, data: indexTask ? {
        id: 'desktop-task', documentId: document.id, status: 'pending', failureReason: null,
      } : null } })
    }
    await route.fulfill({ status: 401, json: { ok: false, error: { message: '需要认证' } } })
  })
  const response = await page.goto(`http://127.0.0.1:${address.port}/knowledge`)
  assert.equal(response.status(), 200)
  await expect(page).toHaveURL(/\/login\?redirect=\/knowledge$/)
  await expect(page).toHaveTitle('Super AI 工程基础')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('登录工作台')
  await page.getByRole('link', { name: /注册/ }).click()
  await page.getByLabel('邮箱').fill(user.email)
  await page.getByLabel('密码').fill('desktop-test-password')
  await page.getByRole('button', { name: '注册' }).click()
  await expect(page.getByText('注册成功，请登录。')).toBeVisible()
  await page.getByLabel('邮箱').fill(user.email)
  await page.getByLabel('密码').fill('desktop-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/knowledge$/)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('知识库')
  await expect(page.getByText('服务可用')).toBeVisible()
  const nav = page.getByRole('navigation', { name: '业务导航' })
  for (const title of ['对话', 'AIOps', 'MCP', '知识库']) {
    await nav.getByRole('link', { name: title, exact: true }).click()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
    await expect(page.getByRole('region', { name: '会话' })).toHaveCount(title === '对话' ? 1 : 0)
    if (!['知识库', 'MCP'].includes(title)) await expect(page.getByText('功能待接入')).toBeVisible()
  }
  await nav.getByRole('link', { name: 'MCP', exact: true }).click()
  await page.getByLabel('名称', { exact: true }).fill('桌面 CLS 测试连接')
  await page.getByLabel('服务器 URL').fill('http://localhost:9000/mcp')
  await page.getByLabel('传输方式').selectOption('streamable_http')
  await page.getByRole('button', { name: '保存连接' }).click()
  await expect(page.getByRole('heading', { name: '桌面 CLS 测试连接' })).toBeVisible()
  await page.getByRole('button', { name: '检查连接', exact: true }).click()
  await expect(page.getByText('发现 1 个工具')).toBeVisible()
  await page.getByText('已发现工具', { exact: true }).click()
  await expect(page.getByRole('heading', { name: 'browser_fixture_tool' })).toBeVisible()
  await page.getByRole('button', { name: '禁用', exact: true }).click()
  await expect(page.getByText('Streamable HTTP · 已禁用')).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await page.getByLabel('名称', { exact: true }).fill('编辑后的 CLS')
  await page.getByRole('button', { name: '保存连接' }).click()
  await expect(page.getByRole('heading', { name: '编辑后的 CLS' })).toBeVisible()
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
  mkdirSync(join(repositoryRoot, '.cache'), { recursive: true })
  await page.screenshot({ path: join(repositoryRoot, '.cache/desktop-mcp.png'), fullPage: true })
  await page.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByText('暂无连接。添加真实服务器后检查以发现工具。')).toBeVisible()
  await nav.getByRole('link', { name: '知识库', exact: true }).click()
  await page.getByLabel('文档', { exact: true }).setInputFiles({
    name: 'desktop.md', mimeType: 'text/markdown', buffer: Buffer.from('desktop smoke'),
  })
  await page.getByRole('button', { name: '上传并索引' }).click()
  await expect(page.getByText('desktop.md', { exact: true })).toBeVisible()
  await expect(page.getByText('等待索引', { exact: true })).toBeVisible()
  assert.ok(indexTask)
  const canvas = await page.getByRole('main').boundingBox()
  assert.ok(canvas && canvas.x > 0 && canvas.y > 0)
  assert.equal(canvas.x + canvas.width, 1440)
  assert.equal(canvas.y + canvas.height, 900)
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
  mkdirSync(join(repositoryRoot, '.cache'), { recursive: true })
  await page.screenshot({ path: join(repositoryRoot, '.cache/desktop-foundation.png'), fullPage: true })
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('登录工作台')
  assert.equal(session, false)
  for (const name of ['project.json', 'user.project.json']) {
    const configPath = join(root, 'config', name).replaceAll('\\', '/')
    const denied = await page.request.get(`http://127.0.0.1:${address.port}/@fs/${configPath}`)
    assert.equal(denied.status(), 403)
  }
  assert.deepEqual(errors, [])
  console.log('桌面 1440×900：认证、MCP CRUD/启停/检查/工具展示、索引、布局及配置访问通过（浏览器接口夹具，不代表真实 MCP 验收）')
} finally {
  await browser?.close()
  await server.close()
  fixture.cleanup()
}
