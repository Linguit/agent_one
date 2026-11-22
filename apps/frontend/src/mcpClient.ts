import type { McpConnection, McpConnectionInput } from '@super-ai/api-contracts'
import type { useAuthStore } from './auth'

export function createMcpClient(auth: Pick<ReturnType<typeof useAuthStore>, 'request'>) {
  const path = (id: string) => `/mcp/connections/${encodeURIComponent(id)}`
  return {
    list: () => auth.request<McpConnection[]>('/mcp/connections'),
    create: (body: McpConnectionInput) => auth.request<McpConnection>('/mcp/connections', {
      method: 'POST', body: JSON.stringify(body),
    }),
    update: (id: string, body: McpConnectionInput) => auth.request<McpConnection>(path(id), {
      method: 'PUT', body: JSON.stringify(body),
    }),
    remove: (id: string) => auth.request<{ deleted: true }>(path(id), { method: 'DELETE' }),
    check: (id: string) => auth.request<McpConnection>(`${path(id)}:check`, { method: 'POST' }),
  }
}
