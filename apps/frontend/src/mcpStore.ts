import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { McpConnection, McpConnectionInput } from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { createMcpClient } from './mcpClient'
import { ApiRequestError } from './transport/clients'

export const useMcpStore = defineStore('mcp', () => {
  const auth = useAuthStore()
  const client = createMcpClient(auth)
  const connections = ref<McpConnection[]>([])
  const busy = ref(false)
  const error = ref('')
  let generation = 0
  let pending = Promise.resolve()
  let count = 0

  watch(() => auth.user?.id, () => {
    generation++
    connections.value = []
    error.value = ''
    count = 0
    busy.value = false
    pending = Promise.resolve()
  }, { flush: 'sync' })

  function enqueue(action?: () => Promise<unknown>) {
    const owner = generation
    const current = () => owner === generation
    count++
    busy.value = true
    const result = pending.then(async () => {
      if (!current()) return
      error.value = ''
      try {
        if (action) await action()
        if (!current()) return
        const rows = await client.list()
        if (current()) connections.value = rows
      } catch (cause) {
        if (current()) error.value = cause instanceof ApiRequestError && cause.status === 409
          ? '已存在相同传输方式和 URL 的 MCP 连接，请编辑已有连接。'
          : '操作失败，请检查连接配置、登录状态或网络后重试。'
        throw cause
      } finally {
        if (current()) { count--; busy.value = count > 0 }
      }
    })
    pending = result.catch(() => {})
    return result
  }

  const refresh = () => enqueue()
  const save = (body: McpConnectionInput, id?: string) => {
    const input = { ...body }
    return enqueue(() => id ? client.update(id, input) : client.create(input))
  }
  const remove = (id: string) => enqueue(() => client.remove(id))
  const check = (id: string) => enqueue(() => client.check(id))
  const toggle = (row: McpConnection) => save({
    name: row.name, url: row.url, transport: row.transport, enabled: !row.enabled,
    timeoutSeconds: row.timeoutSeconds, retries: row.retries,
  }, row.id)
  return { connections, busy, error, refresh, save, remove, check, toggle }
})
