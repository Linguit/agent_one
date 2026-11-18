import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import { defineStore } from 'pinia'
import type {
  ChunkingConfig, DocumentChunkPreview, DocumentIndexTask, KnowledgeBase, KnowledgeDocument,
} from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { knowledgeClient, uploadIssue } from './knowledgeIndex'
import { ApiRequestError } from './transport/clients'

export function activeIndex(task: DocumentIndexTask | null | undefined) {
  return task?.status === 'pending' || task?.status === 'running'
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  const auth = useAuthStore()
  const client = knowledgeClient(auth.request)
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const documents = ref<KnowledgeDocument[]>([])
  const kb = ref('')
  const tasks = ref<Record<string, DocumentIndexTask | null>>({})
  const selected = ref('')
  const detail = ref<KnowledgeDocument | null>(null)
  const preview = ref<DocumentChunkPreview | null>(null)
  const detailLoading = ref(false)
  const detailError = ref('')
  const busy = ref(false)
  const error = ref('')
  const overwrite = shallowRef<{ file: File; config: ChunkingConfig } | null>(null)
  const deletion = ref<KnowledgeDocument | null>(null)
  const active = computed(() => Object.values(tasks.value).some(activeIndex))
  let controller = new AbortController()
  let detailController: AbortController | undefined
  let timer: ReturnType<typeof setTimeout> | undefined

  function closeDetail() {
    detailController?.abort()
    selected.value = ''
    detail.value = null
    preview.value = null
    detailError.value = ''
    detailLoading.value = false
  }

  function reset() {
    controller.abort()
    controller = new AbortController()
    clearTimeout(timer)
    closeDetail()
    knowledgeBases.value = []
    documents.value = []
    kb.value = ''
    tasks.value = {}
    busy.value = false
    error.value = ''
    overwrite.value = null
    deletion.value = null
  }

  watch(() => auth.user?.id, reset, { flush: 'sync' })
  onScopeDispose(reset)

  async function refresh(signal: AbortSignal) {
    const target = kb.value
    if (!target) return
    const items = await client.list(target, signal)
    if (signal.aborted) return
    documents.value = items
    if (selected.value && !items.some(doc => doc.id === selected.value)) closeDetail()
    const entries = await Promise.all(items.map(async doc =>
      [doc.id, await client.latestTask(target, doc.id, signal)] as const))
    if (!signal.aborted) tasks.value = Object.fromEntries(entries)
  }

  function queuePoll() {
    clearTimeout(timer)
    if (active.value) timer = setTimeout(() => { void run(refresh, true) }, 2000)
  }

  async function run(action: (signal: AbortSignal) => Promise<void>, polling = false) {
    if (!auth.user || busy.value) return
    const { signal } = controller
    clearTimeout(timer)
    busy.value = true
    if (!polling) error.value = ''
    try {
      await action(signal)
    } catch (cause) {
      if (!signal.aborted) error.value = cause instanceof Error ? cause.message : '请求失败。'
    } finally {
      if (!signal.aborted) {
        busy.value = false
        queuePoll()
      }
    }
  }

  async function load() {
    await run(async signal => {
      const bases = await client.bases(signal)
      if (signal.aborted) return
      knowledgeBases.value = bases
      kb.value = bases.find(base => base.id === kb.value)?.id ?? bases[0]?.id ?? ''
      await refresh(signal)
    })
  }

  async function choose(target: string) {
    await run(async signal => {
      if (!knowledgeBases.value.some(base => base.id === target)) return
      closeDetail()
      documents.value = []
      tasks.value = {}
      overwrite.value = null
      deletion.value = null
      kb.value = target
      await refresh(signal)
    })
  }

  async function inspect(id: string) {
    const previous = selected.value
    closeDetail()
    if (previous === id || !kb.value) return
    const target = kb.value
    detailController = new AbortController()
    const { signal } = detailController
    selected.value = id
    detailLoading.value = true
    try {
      const [document, chunks] = await Promise.all([
        client.detail(target, id, signal), client.preview(target, id, signal),
      ])
      if (!signal.aborted) {
        detail.value = document
        preview.value = chunks
      }
    } catch (cause) {
      if (!signal.aborted) detailError.value = cause instanceof Error ? cause.message : '详情加载失败。'
    } finally {
      if (!signal.aborted) detailLoading.value = false
    }
  }

  async function upload(file: File, config: ChunkingConfig, confirmed = false) {
    await run(async signal => {
      if (!kb.value) return
      const issue = uploadIssue(file)
      if (issue) throw new Error(issue)
      overwrite.value = null
      let doc: KnowledgeDocument
      try {
        doc = await client.upload(kb.value, file, config, confirmed, signal)
      } catch (cause) {
        if (!signal.aborted && cause instanceof ApiRequestError &&
            cause.status === 409 && cause.detail?.code === 'BUSINESS_CONFLICT') {
          overwrite.value = { file, config }
          return
        }
        throw cause
      }
      if (signal.aborted) return
      try {
        const task = await client.schedule(kb.value, doc.id, null, signal)
        if (!signal.aborted) tasks.value[doc.id] = task
      } finally {
        if (!signal.aborted) await refresh(signal)
      }
    })
  }

  function confirmOverwrite() {
    const pending = overwrite.value
    if (pending) return upload(pending.file, pending.config, true)
  }

  function index(id: string) {
    return run(async signal => {
      const task = await client.schedule(kb.value, id, tasks.value[id] ?? null, signal)
      if (!signal.aborted) tasks.value[id] = task
    })
  }

  function confirmDelete() {
    const doc = deletion.value
    if (!doc) return
    return run(async signal => {
      await client.remove(kb.value, doc.id, signal)
      if (signal.aborted) return
      deletion.value = null
      if (selected.value === doc.id) closeDetail()
      await refresh(signal)
    })
  }

  return {
    knowledgeBases, documents, kb, tasks, selected, detail, preview, detailLoading, detailError,
    busy, error, overwrite, deletion, load, choose, inspect, upload, confirmOverwrite, index,
    confirmDelete, reset, refresh: () => run(refresh),
  }
})
