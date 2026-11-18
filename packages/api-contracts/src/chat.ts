export type ChatRole = 'user' | 'assistant' | 'system' | 'tool'

type ChatJson = null | boolean | number | string | ChatJson[] | { [key: string]: ChatJson }

export interface ChatMetadata extends Record<string, ChatJson> {
  references: Record<string, ChatJson>[]
  toolCallIds: string[]
}

export type ChatCreate = Record<string, never>
export interface ChatAppend {
  role: ChatRole
  content: string
  metadata?: Partial<ChatMetadata>
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

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
