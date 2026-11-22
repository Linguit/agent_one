export interface McpConnectionInput {
  name: string
  transport: 'sse' | 'streamable_http'
  url: string
  enabled: boolean
  timeoutSeconds: number
  retries: number
}

export interface McpDiscoveredTool {
  name: string
  description: string
  inputSchema: Record<string, unknown>
}

export interface McpConnection extends McpConnectionInput {
  id: string
  owner: string
  lastCheck: string | null
  lastError: string | null
  discoveredTools: McpDiscoveredTool[]
  createdAt: string
  updatedAt: string
}
