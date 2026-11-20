import type {
  ChatAppend, ChatAppended, ChatCleared, ChatCreate, ChatDeleted, ChatDetail, ChatList, ChatSession,
  ChatStreamInput, ToolCallAudit,
} from '@super-ai/api-contracts'
import { useAuthStore } from './auth'

const base = '/chat/sessions'
const sessionPath = (id: string) => `${base}/${encodeURIComponent(id)}`
const post = (body: ChatCreate | ChatStreamInput) => ({ method: 'POST', body: JSON.stringify(body) })

export function createChatClient(auth: Pick<ReturnType<typeof useAuthStore>, 'request' | 'stream'>) {
  return {
    list: () => auth.request<ChatList>(base),
    detail: (id: string) => auth.request<ChatDetail>(sessionPath(id)),
    create: () => auth.request<ChatSession>(base, post({})),
    append: (id: string, body: ChatAppend) =>
      auth.request<ChatAppended>(`${sessionPath(id)}/messages`, post(body)),
    stream: (id: string, body: ChatStreamInput, signal: AbortSignal) =>
      auth.stream(`${sessionPath(id)}/messages:stream`, { ...post(body), signal }),
    toolCallAudits: (id: string) =>
      auth.request<ToolCallAudit[]>(`${sessionPath(id)}/tool-call-audits`),
    clear: (id: string) =>
      auth.request<ChatCleared>(`${sessionPath(id)}/messages:clear`, { method: 'POST' }),
    remove: (id: string) => auth.request<ChatDeleted>(sessionPath(id), { method: 'DELETE' }),
  }
}
