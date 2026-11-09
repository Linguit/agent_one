import assert from 'node:assert/strict'
import { join } from 'node:path'
import { chromium } from '@playwright/test'
import { createServer } from 'vitepress'
import { temporaryProject } from './temporary-project.mjs'

const fixture = temporaryProject('docs')
let server
let browser
try {
  server = await createServer(join(fixture.root, 'docs'), { host: '127.0.0.1', port: 0 })
  await server.listen()
  const address = server.httpServer.address()
  assert.ok(address && typeof address !== 'string')
  const origin = `http://127.0.0.1:${address.port}`
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(origin, { waitUntil: 'networkidle' })
  const home = await fetch(origin, { signal: AbortSignal.timeout(10000) })
  await home.arrayBuffer()
  console.log(`临时文档首页状态：${home.status}`)
  assert.equal(home.status, 200)
  for (const name of ['project.json', 'user.project.json']) {
    const path = join(fixture.root, 'config', name).replaceAll('\\', '/')
    const response = await fetch(`${origin}/@fs/${path}`, { signal: AbortSignal.timeout(10000) })
    await response.arrayBuffer()
    console.log(`临时文档 ${name} 状态：${response.status}`)
    assert.equal(response.status, 403, `文档服务器必须拒绝 ${name}`)
  }
  console.log('文档临时副本：首页 200，两份本地 JSON 请求均为 403')
} finally {
  await browser?.close()
  server?.httpServer?.closeAllConnections()
  await server?.close()
  fixture.cleanup()
}
