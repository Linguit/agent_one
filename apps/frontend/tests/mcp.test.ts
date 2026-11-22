import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { McpConnection, McpConnectionInput } from '@super-ai/api-contracts'
import { useAuthStore } from '../src/auth'
import { useMcpStore } from '../src/mcpStore'
import { createMcpClient } from '../src/mcpClient'
import { ApiRequestError } from '../src/transport/clients'

it('shows a clear duplicate connection message for server conflicts', async () => {
  vi.spyOn(useAuthStore(), 'request').mockRejectedValueOnce(new ApiRequestError(409))
  const store = useMcpStore()
  await expect(store.save(input)).rejects.toThrow()
  expect(store.error).toBe('已存在相同传输方式和 URL 的 MCP 连接，请编辑已有连接。')
  expect(store.connections).toEqual([])
  expect(store.busy).toBe(false)
})

const input: McpConnectionInput = {
  name: 'CLS', transport: 'sse', url: 'http://localhost/sse', enabled: true,
  timeoutSeconds: 30, retries: 2,
}
const row = (): McpConnection => ({
  ...input, id: 'connection', owner: 'alice', lastCheck: null, lastError: null,
  discoveredTools: [], createdAt: '2026-11-21T00:00:00Z', updatedAt: '2026-11-21T00:00:00Z',
})
beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  useAuthStore().user = { id: 'alice', email: 'alice@test' }
})

it('reconciles CRUD, toggle and real check state from the server list', async () => {
  let rows: McpConnection[] = []
  const request = vi.spyOn(useAuthStore(), 'request').mockImplementation(async (path, options) => {
    const method = options?.method ?? 'GET'
    if (method === 'GET') return structuredClone(rows)
    if (method === 'DELETE') rows = []
    else if (path.endsWith(':check')) rows = rows.map(item => ({
      ...item, lastCheck: '2026-11-21T01:00:00Z', discoveredTools: [{
        name: 'actual_server_tool', description: 'actual description', inputSchema: {},
      }],
    }))
    else rows = [{ ...row(), ...JSON.parse(String(options?.body)) }]
    return rows[0] ?? { deleted: true }
  })
  const store = useMcpStore()
  await store.refresh()
  await store.save(input)
  expect(store.connections[0]?.name).toBe('CLS')
  await store.save({ ...input, name: 'changed', transport: 'streamable_http' }, 'connection')
  expect(store.connections[0]?.transport).toBe('streamable_http')
  await store.check('connection')
  expect(store.connections[0]?.discoveredTools[0]?.name).toBe('actual_server_tool')
  await store.toggle(store.connections[0]!)
  expect(store.connections[0]?.enabled).toBe(false)
  await store.remove('connection')
  expect(store.connections).toEqual([])
  expect(request).toHaveBeenCalledTimes(11)
  expect(store.busy).toBe(false)
})

it('discards late data and cancels queued operations on account change', async () => {
  const auth = useAuthStore()
  let finish!: (value: McpConnection[]) => void
  const request = vi.spyOn(auth, 'request').mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const store = useMcpStore()
  const first = store.refresh()
  const queued = store.save(input)
  await Promise.resolve()
  auth.user = { id: 'bob', email: 'bob@test' }
  finish([row()])
  await Promise.all([first, queued])
  expect(store.connections).toEqual([])
  expect(request).toHaveBeenCalledTimes(1)
  expect(store.busy).toBe(false)
})

it('reports a safe error and supports retry; late writes do not refresh after logout', async () => {
  const auth = useAuthStore()
  const request = vi.spyOn(auth, 'request').mockRejectedValueOnce(new Error('URL-secret'))
  const store = useMcpStore()
  await expect(store.refresh()).rejects.toThrow()
  expect(store.error).toBeTruthy()
  expect(store.error).not.toContain('secret')
  expect(store.busy).toBe(false)
  request.mockResolvedValueOnce([row()])
  await store.refresh()
  expect(store.error).toBe('')
  let finish!: (value: unknown) => void
  request.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const write = store.check('connection')
  await Promise.resolve()
  auth.user = null
  finish(row())
  await write
  expect(store.connections).toEqual([])
  expect(request).toHaveBeenCalledTimes(3)
})

it('encodes identifiers for mutations and checks', async () => {
  const request = vi.spyOn(useAuthStore(), 'request').mockResolvedValue({})
  const client = createMcpClient(useAuthStore())
  await client.check('a/b')
  expect(request).toHaveBeenLastCalledWith('/mcp/connections/a%2Fb:check', { method: 'POST' })
  await client.remove('a/b')
  expect(request).toHaveBeenLastCalledWith('/mcp/connections/a%2Fb', { method: 'DELETE' })
})
