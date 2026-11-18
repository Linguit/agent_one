import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ChatAppend, ChatDetail, ChatList } from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { createChatClient } from './chatClient'

export const useChatStore = defineStore('chat', () => {
  const auth = useAuthStore()
  const client = createChatClient(auth)
  const sessions = ref<ChatList>([])
  const detail = ref<ChatDetail | null>(null)
  let generation = 0
  let pending = Promise.resolve()

  watch(() => auth.user?.id, () => {
    generation++
    pending = Promise.resolve()
    sessions.value = []
    detail.value = null
  }, { flush: 'sync' })

  function enqueue(action: (isCurrent: () => boolean) => Promise<void>) {
    const ownerGeneration = generation
    const isCurrent = () => generation === ownerGeneration
    const result = pending.then(async () => {
      if (isCurrent()) await action(isCurrent)
    })
    pending = result.catch(() => {})
    return result
  }

  async function reconcile(id: string | undefined, isCurrent: () => boolean) {
    if (!isCurrent()) return
    const list = await client.list()
    if (!isCurrent()) return
    const selected = id && list.some(session => session.id === id)
      ? await client.detail(id)
      : null
    if (!isCurrent()) return
    sessions.value = list
    detail.value = selected
  }

  function refresh() {
    return enqueue(current => reconcile(detail.value?.session.id, current))
  }

  function select(id: string) {
    return enqueue(async current => {
      const selected = await client.detail(id)
      if (current()) detail.value = selected
    })
  }

  function create() {
    return enqueue(async current => {
      const session = await client.create()
      await reconcile(session.id, current)
    })
  }

  function append(id: string, body: ChatAppend) {
    return enqueue(async current => {
      await client.append(id, body)
      await reconcile(detail.value?.session.id ?? id, current)
    })
  }

  function clear(id: string) {
    return enqueue(async current => {
      await client.clear(id)
      await reconcile(detail.value?.session.id ?? id, current)
    })
  }

  function remove(id: string) {
    return enqueue(async current => {
      await client.remove(id)
      await reconcile(detail.value?.session.id, current)
    })
  }

  return { sessions, detail, refresh, select, create, append, clear, remove }
})
