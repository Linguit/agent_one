import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ChatDetail, ChatSession, SseEvent } from '@super-ai/api-contracts'
import { useAuthStore } from '../src/auth'
import { useChatStore } from '../src/chatStore'

const user = { id: 'alice', email: 'alice@example.test' }
const original: ChatSession = {
  id: 'first', title: '新会话', createdAt: '2026-11-18T00:00:00Z', updatedAt: '2026-11-18T00:00:00Z',
  memoryMode: 'every_30_turns', memorySummary: '', contextTokens: 100, contextWindowTokens: 1000,
  contextUsagePercent: 10, compactedMessageCount: 0, lastCompactedAt: null, canCompact: false,
}

beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().user = user
})

it('updates and compacts memory then reconciles fresh server state', async () => {
  const auth = useAuthStore()
  let session = { ...original }
  const request = vi.spyOn(auth, 'request').mockImplementation(async (path, options) => {
    if (path.endsWith('/memory')) {
      expect(options?.method).toBe('PUT')
      expect(JSON.parse(options?.body as string)).toEqual({ memoryMode: 'manual' })
      session = { ...session, memoryMode: 'manual' }
      return session
    }
    if (path.endsWith('/memory:compact')) {
      expect(options?.method).toBe('POST')
      session = { ...session, memorySummary: '摘要', compactedMessageCount: 60,
        contextTokens: 20, contextUsagePercent: 2 }
      return session
    }
    return path.endsWith('/sessions') ? [session] : { session, messages: [] }
  })
  const store = useChatStore()
  await store.select(original.id)
  await store.updateMemory(original.id, 'manual')
  expect(store.detail?.session.memoryMode).toBe('manual')
  await store.compactMemory(original.id)
  expect(store.detail?.session).toEqual(session)
  expect(store.sessions).toEqual([session])
  request.mockRejectedValueOnce(new Error('压缩失败'))
  await expect(store.compactMemory(original.id)).rejects.toThrow('压缩失败')
  expect(store.detail?.session).toEqual(session)
})

it('discards an in-flight memory response after switching owner', async () => {
  const auth = useAuthStore()
  let finish!: (value: ChatSession) => void
  vi.spyOn(auth, 'request').mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const store = useChatStore()
  const update = store.updateMemory(original.id, 'manual')
  await Promise.resolve()
  auth.user = { id: 'bob', email: 'bob@example.test' }
  finish({ ...original, memoryMode: 'manual' })
  await update
  expect(store.sessions).toEqual([])
  expect(store.detail).toBeNull()
})

it('starts each live turn without references and reloads each answer from its own metadata', async () => {
  const auth = useAuthStore()
  const store = useChatStore()
  const reference = { title: '资料', uri: '/source' }
  const data: ChatDetail = { session: original, messages: [] }
  let count = 0
  vi.spyOn(auth, 'request').mockImplementation(async path =>
    path.endsWith('/sessions') ? [original] : data,
  )
  const stream = vi.spyOn(auth, 'stream').mockImplementation(async function* () {
    const base = { id: 'event', channel: 'chat', timestamp: original.createdAt } as const
    expect(store.liveTurn?.references).toEqual([])
    count++
    if (count === 1) {
      yield { ...base, type: 'reference.source', data: reference } satisfies SseEvent
      expect(store.liveTurn?.references).toEqual([reference])
    }
    data.messages.push({
      id: `message-${count}`, sessionId: original.id, sequence: count, role: 'assistant',
      content: '回答', createdAt: original.createdAt,
      metadata: { references: count === 1 ? [reference] : [], toolCallIds: [] },
    })
    yield { ...base, type: 'complete', data: {} } satisfies SseEvent
  })
  await store.send(original.id, { content: '查询资料' })
  await store.send(original.id, { content: '你好' })
  expect(stream).toHaveBeenCalledWith('/chat/sessions/first/messages:stream', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ content: '你好' }),
  }))
  await store.select(original.id)
  expect(store.liveTurn).toBeNull()
  const restored = store.detail as ChatDetail | null
  expect(restored?.messages.map(message => message.metadata.references)).toEqual([[reference], []])
})

it('reconciles each mutation with the list and selected detail on the server', async () => {
  let data: ChatDetail = { session: original, messages: [] }
  let exists = false
  const calls: string[] = []
  vi.spyOn(useAuthStore(), 'request').mockImplementation(async (path, options) => {
    const method = options?.method ?? 'GET'
    calls.push(`${method} ${path}`)
    if (path.endsWith('/sessions')) {
      if (method === 'POST') { exists = true; return original }
      return exists ? [data.session] : []
    }
    if (path.endsWith('/messages')) {
      const content = '服务端生成的标题'
      data = {
        session: { ...original, title: content },
        messages: [{
          id: 'message', sessionId: original.id, sequence: 1, role: 'user', content,
          createdAt: original.createdAt, metadata: { references: [], toolCallIds: [] },
        }],
      }
      return { session: data.session, message: data.messages[0] }
    }
    if (path.endsWith('/messages:clear')) {
      data = { session: original, messages: [] }
    }
    if (method === 'DELETE') { exists = false; return { deleted: true } }
    return data
  })
  const store = useChatStore()
  await store.create()
  expect(store.detail).toEqual(data)
  expect(store.sessions).toEqual([original])
  await store.append(original.id, { role: 'user', content: '输入' })
  expect(store.detail).toEqual(data)
  expect(store.sessions).toEqual([data.session])
  await store.clear(original.id)
  expect(store.detail).toEqual({ session: original, messages: [] })
  await store.remove(original.id)
  expect(store.sessions).toEqual([])
  expect(store.detail).toBeNull()
  const base = '/chat/sessions'
  expect(calls).toEqual([
    `POST ${base}`, `GET ${base}`, `GET ${base}/first`,
    `POST ${base}/first/messages`, `GET ${base}`, `GET ${base}/first`,
    `POST ${base}/first/messages:clear`, `GET ${base}`, `GET ${base}/first`,
    `DELETE ${base}/first`, `GET ${base}`,
  ])
})

it('clears prior detail and ignores an in-flight response after an account switch', async () => {
  const auth = useAuthStore()
  const request = vi.spyOn(auth, 'request').mockResolvedValueOnce({
    session: original, messages: [],
  }).mockResolvedValueOnce([])
  const store = useChatStore()
  await store.select(original.id)
  expect(store.detail?.session).toEqual(original)
  let resolveList!: (value: ChatSession[]) => void
  request.mockReturnValueOnce(new Promise<ChatSession[]>(resolve => { resolveList = resolve }))
  const refresh = store.refresh()
  await Promise.resolve()
  auth.user = { id: 'bob', email: 'bob@example.test' }
  resolveList([original])
  await refresh
  expect(store.detail).toBeNull()
  expect(store.sessions).toEqual([])
  expect(request).toHaveBeenCalledTimes(3)
})
