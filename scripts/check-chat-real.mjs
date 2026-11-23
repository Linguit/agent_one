// --normal 使用正常 5173/8000 服务及本机配置；默认连接隔离验收服务 18019。
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { chromium, expect } from '@playwright/test'
import { createServer } from 'vite'
import { repositoryRoot } from './temporary-project.mjs'

const normal = process.argv.includes('--normal')
const outputName = normal ? 'chat-normal-smoke' : 'chat-real-smoke'
const server = normal ? null : await createServer({ root: join(repositoryRoot, 'apps/frontend'),
  configFile: join(repositoryRoot, 'apps/frontend/vite.config.ts'),
  define: { __PUBLIC_CONFIG__: JSON.stringify({ title: 'Super AI 工程基础', apiBaseUrl: '/api' }) },
  server: { host: '127.0.0.1', port: 0, open: false,
    proxy: { '/api': { target: 'http://127.0.0.1:18019', rewrite: path => path.replace(/^\/api/, '') } } },
  logLevel: 'error' })
let browser
let page
const report = { mode: normal ? 'normal-local-config' : 'isolated', ordinary: false, knowledge: false, mcp: false, referenceIsolation: false, layout: false, errors: [], streamTypes: [], toolNames: [] }
try {
  let frontendUrl = 'http://127.0.0.1:5173'
  if (server) {
    await server.listen()
    const address = server.httpServer.address()
    assert.ok(address && typeof address !== 'string')
    frontendUrl = `http://127.0.0.1:${address.port}`
  }
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.on('pageerror', error => report.errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()) })
  const email = `chat-p19-${randomUUID()}@example.test`
  const password = randomUUID() + 'Aa1!'
  await page.goto(`${frontendUrl}/register`)
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '注册', exact: true }).click()
  await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/chat$/, { timeout: 15000 })
  await expect(page.getByRole('log')).toBeEmpty()
  await page.getByRole('button', { name: '＋ 新建会话' }).click()
  await expect(page.getByLabel('记忆模式')).toBeVisible()
  async function turn(question) {
    const response = page.waitForResponse(value => value.url().endsWith('/messages:stream'), { timeout: 180000 })
    await page.getByLabel('消息', { exact: true }).fill(question)
    await page.getByRole('button', { name: '发送', exact: true }).click()
    const stream = await response
    assert.equal(stream.status(), 200)
    const frames = (await stream.text()).split(/\r?\n/).filter(line => line.startsWith('data:'))
      .map(line => JSON.parse(line.slice(5)))
    report.streamTypes.push([...new Set(frames.map(event => event.type))])
    assert.equal(frames.at(-1)?.type, 'complete', frames.at(-1)?.type === 'error' ? '真实 SSE 返回错误' : 'SSE 未完成')
    await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible({ timeout: 180000 })
    assert.ok(await page.getByRole('log').locator('.assistant .chat-bubble').count())
    return frames
  }
  await turn('你好，请只用一句话解释什么是 HTTP。不要调用工具。')
  report.ordinary = true
  await page.getByRole('navigation').getByRole('link', { name: '知识库', exact: true }).click()
  await page.getByLabel('文档', { exact: true }).setInputFiles({ name: 'p19-workspace-smoke.md', mimeType: 'text/markdown',
    buffer: Buffer.from('# P19 验收资料\n青岚服务的故障恢复口令是蓝鲸七号，恢复步骤是先检查连接池，再重新启动只读探针。') })
  await page.getByRole('button', { name: '上传并索引' }).click()
  await expect(page.getByText('索引完成', { exact: true })).toBeVisible({ timeout: 180000 })
  await page.getByRole('navigation').getByRole('link', { name: '对话', exact: true }).click()
  const frames = await turn('请检索我上传的知识库资料，告诉我青岚服务的故障恢复口令和恢复步骤。请给出简短回答。')
  report.toolNames = [...new Set(frames.filter(event => event.type === 'tool.call').map(event => event.data.toolName))]
  assert.ok(report.toolNames.includes('knowledge_retrieval'), '模型没有调用真实知识检索工具')
  assert.ok(frames.some(event => event.type === 'tool.call' && event.data.status === 'completed'))
  assert.ok(frames.some(event => event.type === 'reference.source' && event.data.excerpt && event.data.rerankRank))
  report.knowledge = true
  await expect(page.getByRole('log').locator('.assistant')).toHaveCount(2)
  await expect(page.getByRole('region', { name: '回答引用' })).toHaveCount(1)
  await turn('谢谢，请只回答“不客气”，不要检索或调用任何工具。')
  await expect(page.getByRole('log').locator('.assistant')).toHaveCount(3)
  await expect(page.getByRole('log').locator('.assistant').last().locator('.chat-references')).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('log').locator('.assistant')).toHaveCount(3)
  await expect(page.getByRole('region', { name: '回答引用' })).toHaveCount(1)
  await expect(page.getByRole('log').locator('.assistant').last().locator('.chat-references')).toHaveCount(0)
  report.referenceIsolation = true
  await page.getByRole('navigation').getByRole('link', { name: 'MCP', exact: true }).click()
  await page.getByLabel('名称', { exact: true }).fill('P19 官方 CLS')
  await page.getByLabel('服务器 URL').fill('http://127.0.0.1:3000/sse')
  await page.getByLabel('传输方式').selectOption('sse')
  await page.getByRole('button', { name: '保存连接', exact: true }).click()
  await page.getByRole('button', { name: '检查连接', exact: true }).click()
  await expect(page.getByText(/发现 \d+ 个工具/)).toBeVisible({ timeout: 30000 })
  await page.getByRole('navigation').getByRole('link', { name: '对话', exact: true }).click()
  const mcpFrames = await turn('请自主选择可用的 CLS MCP 工具，实际查询广州对应的地域编码，不要凭记忆回答。请只用一句话回答查询结果。')
  const mcpNames = [...new Set(mcpFrames.filter(event => event.type === 'tool.call').map(event => event.data.toolName))]
  report.toolNames.push(...mcpNames)
  assert.ok(mcpNames.includes('GetRegionCodeByName'))
  assert.ok(mcpFrames.some(event => event.type === 'tool.call' && event.data.status === 'completed'))
  report.mcp = true
  await page.getByLabel('记忆模式').selectOption('manual')
  await expect(page.getByLabel('记忆模式')).toHaveValue('manual')
  const composer = await page.getByRole('form', { name: '发送消息' }).boundingBox()
  assert.ok(composer && composer.y + composer.height <= 900)
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight))
  report.layout = true
  mkdirSync(join(repositoryRoot, '.cache'), { recursive: true })
  await page.screenshot({ path: join(repositoryRoot, `.cache/${outputName}.png`) })
  assert.deepEqual(report.errors, [])
  console.log('真实桌面 smoke：普通模型问答、自主知识检索/引用、官方 CLS MCP 工具、重载与逐轮隔离、记忆模式、1440×900 固定布局通过。')
} finally {
  mkdirSync(join(repositoryRoot, '.cache'), { recursive: true })
  if (page && !page.isClosed()) await page.screenshot({ path: join(repositoryRoot, `.cache/${outputName}.png`) })
  writeFileSync(join(repositoryRoot, `.cache/${outputName}.json`), JSON.stringify(report, null, 2))
  await browser?.close()
  await server?.close()
}
