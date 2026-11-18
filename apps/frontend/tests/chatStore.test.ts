import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ChatDetail, ChatSession } from '@super-ai/api-contracts'
import { useAuthStore } from '../src/auth'
import { useChatStore } from '../src/chatStore'

const user = { id: 'alice', email: 'alice@example.test' }
const original: ChatSession = {
  id: 'first', title: '新会话', createdAt: '2026-11-18T00:00:00Z', updatedAt: '2026-11-18T00:00:00Z',
}

beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().user = user
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
  })
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
  expect(request).toHaveBeenCalledTimes(2)
})
