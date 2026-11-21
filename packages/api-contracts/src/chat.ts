export type ChatRole = 'user' | 'assistant' | 'system' | 'tool'

type ChatJson = null | boolean | number | string | ChatJson[] | { [key: string]: ChatJson }

export interface ChatMetadata extends Record<string, ChatJson> {
  references: Record<string, ChatJson>[]
  toolCallIds: string[]
}

export type ChatCreate = Record<string, never>
export interface ChatStreamInput {
  content: string
  metadata?: Partial<ChatMetadata>
}

export interface ChatAppend extends ChatStreamInput {
  role: ChatRole
}

type ToolAuditParent =
  | { chatSessionId: string; diagnosticTaskId: null }
  | { chatSessionId: null; diagnosticTaskId: string }

export type ToolCallAudit = ToolAuditParent & {
  id: string
  ownerUserId: string
  toolName: string
  arguments: Record<string, ChatJson>
  status: 'started' | 'completed' | 'failed'
  resultSummary: string | null
  errorMessage: string | null
  startedAt: string
  completedAt: string | null
  durationMs: number | null
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  memoryMode: MemoryMode
  memorySummary: string
  contextTokens: number
  contextWindowTokens: number
  contextUsagePercent: number
  compactedMessageCount: number
  lastCompactedAt: string | null
  canCompact: boolean
}

export type MemoryMode = 'every_30_turns' | 'context_70_percent' | 'manual'
export interface ChatMemoryUpdate { memoryMode: MemoryMode }

export interface ChatMessage extends ChatAppend {
  id: string
  sessionId: string
  sequence: number
  createdAt: string
  metadata: ChatMetadata
}

export type ChatList = ChatSession[]
export interface ChatDetail {
  session: ChatSession
  messages: ChatMessage[]
}
export interface ChatAppended {
  session: ChatSession
  message: ChatMessage
}
export type ChatCleared = ChatDetail
export interface ChatDeleted {
  deleted: true
}
