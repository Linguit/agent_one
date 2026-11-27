import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import type { ActiveAlert, DiagnosticCase, DiagnosticEvidenceChain, DiagnosticInput, DiagnosticRecord, SseEvent } from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { createAiopsClient } from './aiopsClient'

export const useAiopsStore = defineStore('aiops', () => {
  const auth = useAuthStore()
  const client = createAiopsClient(auth)
  const history = ref<DiagnosticRecord[]>([])
  const activeAlerts = ref<ActiveAlert[]>([])
  const cases = ref<DiagnosticCase[]>([])
  const activeTask = ref<DiagnosticRecord | null>(null)
  const liveEvents = ref<SseEvent[]>([])
  const evidenceChain = ref<DiagnosticEvidenceChain | null>(null)
  const selectedCase = ref<DiagnosticCase | null>(null)
  const documentTarget = ref<{ path: string; query: { kb: string; document: string } } | null>(null)
  const busy = ref(false)
  const error = ref('')
  const alertsError = ref('')
  const connection = ref('尚未订阅')
  let epoch = 0
  let controller: AbortController | undefined
  const cancellable = computed(() => ['queued', 'running'].includes(activeTask.value?.backgroundJob.status ?? ''))
  function stop() { epoch++; controller?.abort(); controller = undefined; busy.value = false }
  function reset() {
    stop(); history.value = []; activeAlerts.value = []; cases.value = []; activeTask.value = null
    liveEvents.value = []; evidenceChain.value = null; selectedCase.value = null; documentTarget.value = null
    error.value = ''; alertsError.value = ''; connection.value = '尚未订阅'
  }
  watch(() => auth.user?.id, reset, { flush: 'sync' })
  async function recover(id: string | undefined, token: number) {
    const [list, savedCases, task, chain] = await Promise.all([
      client.history(), client.cases(), id ? client.detail(id) : null, id ? client.chain(id) : null,
    ])
    if (token !== epoch) return
    history.value = list; cases.value = savedCases; activeTask.value = task; evidenceChain.value = chain
  }
  async function refresh() {
    const token = epoch
    error.value = ''
    try { await recover(activeTask.value?.id, token) }
    catch { if (token === epoch) error.value = '持久状态读取失败，请刷新重试。' }
  }
  async function refreshAlerts() {
    const token = epoch
    alertsError.value = ''
    try { const result = await client.alerts(); if (token === epoch) activeAlerts.value = result.items }
    catch { if (token === epoch) { activeAlerts.value = []; alertsError.value = '真实告警源不可用，请检查服务后重试。' } }
  }
  async function select(id: string) {
    stop(); const token = epoch
    error.value = ''; liveEvents.value = []; evidenceChain.value = null; activeTask.value = null
    connection.value = '历史记录（持久状态）'
    try { await recover(id, token) } catch { if (token === epoch) error.value = '历史诊断读取失败。' }
  }
  async function create(body: DiagnosticInput) {
    if (busy.value || !body.query.trim()) return
    stop(); const token = epoch
    busy.value = true; error.value = ''; liveEvents.value = []; evidenceChain.value = null
    const abort = new AbortController(); controller = abort
    let id: string | undefined
    let terminal = false
    try {
      const task = await client.create(body)
      if (token !== epoch) return
      id = task.id; activeTask.value = task
      await recover(id, token)
      if (token !== epoch) return
      connection.value = '实时连接中'
      for await (const event of client.stream(id, task.backgroundJob.id, abort.signal)) {
        if (token !== epoch) return
        if (!liveEvents.value.some(item => item.id === event.id)) liveEvents.value.push(event)
        if (event.type === 'complete' || event.type === 'error') terminal = true
        if (['tool.call', 'reference.source', 'task.status', 'report'].includes(event.type)) {
          try {
            const chain = await client.chain(id)
            if (token === epoch) evidenceChain.value = chain
            if (event.type === 'report') await recover(id, token)
          } catch { if (token === epoch) error.value = '实时证据读取失败，可刷新持久状态。' }
        }
      }
      if (token === epoch) connection.value = terminal ? '实时流已结束，已读取持久状态' : '连接已断开，已读取持久状态；可手动刷新'
    } catch {
      if (token === epoch) {
        connection.value = '连接已断开；未自动重新订阅'
        error.value = id ? '实时连接中断，正在恢复持久状态。' : '创建诊断失败，请检查服务后重试。'
      }
    } finally {
      if (token === epoch) {
        try { await recover(id ?? activeTask.value?.id, token) }
        catch { if (token === epoch) error.value = '持久状态恢复失败，请手动刷新。' }
        if (token === epoch) { busy.value = false; controller = undefined }
      }
    }
  }
  async function cancel() {
    const task = activeTask.value
    if (!task || !cancellable.value) return
    const token = epoch
    try { await client.cancel(task.backgroundJob.id); await recover(task.id, token) }
    catch { if (token === epoch) error.value = '取消请求失败，请刷新确认后台任务状态。' }
  }
  async function inspectCase(id: string) {
    const token = epoch
    selectedCase.value = null; documentTarget.value = null
    try {
      const item = await client.case(id)
      if (token !== epoch) return
      selectedCase.value = item
      const bases = await client.bases()
      for (const base of bases) {
        const docs = await client.documents(base.id)
        if (token !== epoch) return
        if (docs.some(doc => doc.id === item.documentId)) {
          documentTarget.value = { path: '/knowledge', query: { kb: base.id, document: item.documentId } }; return
        }
      }
      if (token === epoch) error.value = '案例文档暂不可用。'
    } catch { if (token === epoch) error.value = '案例或所属知识文档读取失败。' }
  }
  return { history, activeAlerts, cases, activeTask, liveEvents, evidenceChain, selectedCase, documentTarget,
    busy, error, alertsError, connection, cancellable, refresh, refreshAlerts, select, create, cancel, inspectCase, reset }
})
