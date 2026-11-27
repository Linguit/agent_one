import assert from 'node:assert/strict'
import { join } from 'node:path'
import { mkdirSync } from 'node:fs'
import { chromium, expect } from '@playwright/test'
import { createServer } from 'vite'
import { temporaryProject, repositoryRoot } from './temporary-project.mjs'

// 仅为浏览器布局/交互夹具，不代表真实告警、LLM 或 MCP 验收。
const fixture = temporaryProject('apps/frontend')
const frontend = join(fixture.root, 'apps/frontend')
const server = await createServer({ root: frontend, configFile: join(frontend, 'vite.config.ts'), server: { host: '127.0.0.1', port: 0 }, logLevel: 'error' })
let browser
try {
  await server.listen()
  const address = server.httpServer.address()
  assert.ok(address && typeof address !== 'string')
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', e => { if (e.type() === 'error') errors.push(e.text()) })
  const task = { id: 'layout-task', input: { query: '浏览器夹具诊断' }, status: 'accepted', createdAt: '', backgroundJob: { id: 'layout-job', status: 'queued', cancelRequestedAt: null }, report: null }
  const savedCase = { id: 'c1', taskId: task.id, reportId: 'r1', documentId: 'd1', alertName: '布局测试告警', service: 'fixture', summary: '测试案例', rootCause: '证据不足', remediation: '人工核验', keywords: ['测试'], evidenceIds: ['e1'] }
  const chain = { steps: [{ id: 's1', ordinal: 1, tool_name: 'SearchLog', purpose: '读取真实来源', status: 'completed', audit_id: 'a1' }], evidence: Array.from({ length: 30 }, (_, i) => ({ id: `e${i+1}`, source: 'SearchLog', kind: 'log', content: { message: '浏览器布局测试摘要'.repeat(12), raw: { rawMarker: true } } })), links: [{ id: 'l1', report_id: 'r1', evidence_id: 'e1', claim: '因果未确认' }], checkpoints: [{ id: 'p1', plan_version: 1, next_node: 'replanner', state: { plan: { steps: [{ purpose: '读取日志', tool: 'SearchLog' }] } } }], reports: [], toolCalls: [{ id: 'a1', tool_name: 'SearchLog', status: 'completed', result_summary: '工具安全摘要' }] }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data
    if (path === '/api/auth/me') data = { id: 'layout-user', email: 'layout@test.test' }
    else if (path === '/api/health') data = { status: 'ok' }
    else if (path === '/api/aiops/alerts/active') data = { items: [{ alertname: '布局测试告警', service: 'fixture', severity: 'warning', status: 'firing', source: 'browser-fixture', startsAt: '', annotations: { summary: '测试症状' } }] }
    else if (path.endsWith(':stream')) {
      task.status = 'succeeded'; task.backgroundJob.status = 'succeeded'
      task.report = { mode: 'fallback', content: '# 告警分析报告\n\n' + '## 风险评估\n\n证据不足，人工核验（证据：e1）。\n\n'.repeat(100) + '```json\n{"rawMarker":true}\n```' }
      return route.fulfill({ contentType: 'text/event-stream', body: Array.from({ length: 30 }, (_, i) => `event: task.status\ndata: ${JSON.stringify({ id: `j:${i}`, channel: 'aiops', timestamp: '', type: 'task.status', data: { status: 'running', task: { message: `Planner / Replanner 阶段 ${i}`, progress: .5 } } })}\n\n`).join('') + `event: complete\ndata: ${JSON.stringify({ id: 'j:31', type: 'complete', channel: 'aiops', timestamp: '', data: {} })}\n\n` })
    }
    else if (path === '/api/aiops/diagnostics') data = route.request().method() === 'POST' ? task : [task, ...Array.from({ length: 25 }, (_, i) => ({ ...task, id: 'history-' + i, input: { query: '长历史布局测试' } }))]
    else if (path.endsWith('/evidence-chain')) data = chain
    else if (path === '/api/aiops/diagnostics/layout-task') data = task
    else if (path === '/api/aiops/diagnostic-cases') data = task.report ? [savedCase] : []
    else if (path.endsWith('/diagnostic-cases/c1')) data = savedCase
    else if (path === '/api/knowledge-bases') data = [{ id: 'kb', name: '默认知识库' }]
    else if (path === '/api/knowledge-bases/kb/documents') data = [{ id: 'd1' }]
    else throw new Error('未处理测试请求 ' + path)
    return route.fulfill({ json: { ok: true, data, meta: { requestId: 'layout' } } })
  })
  await page.addInitScript(() => localStorage.setItem('super-ai.auth.token', 'layout-token'))
  await page.goto(`http://127.0.0.1:${address.port}/aiops`)
  await page.getByRole('button', { name: /布局测试告警.*fixture/ }).click()
  await expect(page.getByLabel('诊断问题', { exact: true })).toHaveValue(/布局测试告警/)
  await page.getByRole('button', { name: '创建诊断', exact: true }).click()
  await expect(page.getByText('诊断：已完成', { exact: true })).toBeVisible()
  await expect(page.getByText('保守 fallback · 证据不足')).toBeVisible()
  for (const selector of ['.aiops-input', '.aiops-report', '.aiops-timeline', '.aiops-provenance']) {
    assert.ok(await page.locator(selector).evaluate(el => el.scrollHeight > el.clientHeight), `${selector} 必须内滚`)
  }
  assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight))
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  assert.equal(await page.locator('.aiops-provenance details[open]').count(), 0)
  assert.equal(await page.getByText('rawMarker', { exact: false }).count(), 0)
  await page.getByRole('button', { name: '布局测试告警 测试案例', exact: true }).click()
  await expect(page.getByRole('link', { name: '打开知识文档' })).toHaveAttribute('href', '/knowledge?kb=kb&document=d1')
  mkdirSync(join(repositoryRoot, '.cache'), { recursive: true })
  await page.locator('.aiops-provenance').evaluate(el => { el.scrollTop = 0 })
  await page.screenshot({ path: join(repositoryRoot, '.cache/desktop-aiops-long.png') })
  assert.deepEqual(errors, [])
  console.log('AIOps 1440×900 浏览器夹具：预填/创建/SSE/报告/证据/案例/内滚/无 raw JSON/控制台通过；不代表真实服务 smoke。')
} finally { await browser?.close(); await server.close(); fixture.cleanup() }
