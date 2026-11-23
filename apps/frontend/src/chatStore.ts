import { defineStore } from 'pinia'
import { computed, ref, shallowRef, watch } from 'vue'
import type { ChatAppend, ChatDetail, ChatList, ChatStreamInput, MemoryMode, SseEvent } from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { createChatClient } from './chatClient'
import { ApiRequestError } from './transport'
import type { ToolCallAudit } from '@super-ai/api-contracts'

interface LiveTurn {
  sessionId: string
  content: string
  input: string
  reasoning: string
  references: Extract<SseEvent, { type: 'reference.source' }>['data'][]
  tools: Extract<SseEvent, { type: 'tool.call' }>['data'][]
}

export const useChatStore = defineStore('chat', () => {
  const auth = useAuthStore()
  const client = createChatClient(auth)
  const sessions = ref<ChatList>([])
  const detail = shallowRef<ChatDetail | null>(null)
  const liveTurn = ref<LiveTurn | null>(null)
  const toolAudits = shallowRef<ToolCallAudit[]>([])
  const active = computed(() => detail.value?.session ?? null)
  const messages = computed(() => detail.value?.messages ?? [])
  const references = computed(() => liveTurn.value?.references ?? [])
  const liveToolCalls = computed(() => liveTurn.value?.tools ?? [])
  let abort: AbortController | undefined
  let generation = 0
  let pending = Promise.resolve()

  watch(() => auth.user?.id, () => {
    generation++
    pending = Promise.resolve()
    sessions.value = []
    detail.value = null
    liveTurn.value = null
    toolAudits.value = []
    abort?.abort()
    abort = undefined
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
      if (!current()) return
      detail.value = selected
      toolAudits.value = []
      const audits = await client.toolCallAudits(id)
      if (current()) toolAudits.value = audits
    })
  }

  function create() {
    return enqueue(async current => {
      const session = await client.create()
      await reconcile(session.id, current)
      if (current()) toolAudits.value = []
    })
  }

  function append(id: string, body: ChatAppend) {
    return enqueue(async current => {
      await client.append(id, body)
      await reconcile(detail.value?.session.id ?? id, current)
    })
  }

  function send(id: string, body: ChatStreamInput) {
    return enqueue(async current => {
      const controller = new AbortController()
      abort = controller
      liveTurn.value = { sessionId: id, input: body.content, content: '', reasoning: '', references: [], tools: [] }
      try {
        for await (const event of client.stream(id, body, controller.signal)) {
          const turn: LiveTurn | null = liveTurn.value
          if (!current() || !turn) return
          switch (event.type) {
            case 'content.delta':
              for (const character of event.data.text) {
                if (!current() || controller.signal.aborted) return
                turn.content += character
                await new Promise(resolve => setTimeout(resolve, 28))
              }
              break
            case 'reasoning.delta': turn.reasoning += event.data.text; break
            case 'reference.source': turn.references.push(event.data); break
            case 'tool.call': {
              const previous = turn.tools.findIndex(tool => tool.toolId === event.data.toolId)
              if (previous < 0) turn.tools.push(event.data)
              else turn.tools[previous] = { ...turn.tools[previous], ...event.data }
              break
            }
            case 'error': throw new ApiRequestError(event.data.error.httpStatus, event.data.error)
            case 'complete': return
          }
        }
        throw new Error('消息流意外断开。')
      } finally {
        if (current()) {
          try {
            await reconcile(id, current)
            const audits = await client.toolCallAudits(id)
            if (current()) toolAudits.value = audits
          } finally {
            if (current()) {
              liveTurn.value = null
              abort = undefined
            }
          }
        }
      }
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
      if (current() && !detail.value) toolAudits.value = []
    })
  }

  function updateMemory(id: string, memoryMode: MemoryMode) {
    return enqueue(async current => {
      await client.updateMemory(id, { memoryMode })
      await reconcile(detail.value?.session.id ?? id, current)
    })
  }

  function compactMemory(id: string) {
    return enqueue(async current => {
      await client.compactMemory(id)
      await reconcile(detail.value?.session.id ?? id, current)
    })
  }

  return { sessions, detail, active, messages, references, liveToolCalls, toolAudits, liveTurn, refresh, select, create, append, send, clear, remove,
    updateMemory, compactMemory }
})
