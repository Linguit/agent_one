import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import type { DiagnosticRecord, DiagnosticCase, SseEvent } from '@super-ai/api-contracts'
import { useAuthStore } from '../src/auth'
import { useAiopsStore } from '../src/aiopsStore'
import AiopsView from '../src/AiopsView.vue'
import { reportHtml, summary, eventSummary } from '../src/aiopsPresentation'

const job = { id: 'job-one', status: 'queued', cancelRequestedAt: null } as DiagnosticRecord['backgroundJob']
const record: DiagnosticRecord = { id: 'task-one', status: 'accepted', input: { query: '服务故障' }, createdAt: '', backgroundJob: job, report: null }
const savedCase = { id: 'case-one', taskId: record.id, documentId: 'doc-one', rootCause: '证据不足', remediation: '人工核验', summary: '案例摘要', evidenceIds: ['e1'], keywords: ['服务'] } as DiagnosticCase
const chain = { steps: [{ id: 's1', purpose: '查询日志', tool_name: 'SearchLog', status: 'failed', audit_id: 'audit-one' }], evidence: [{ id: 'e1', source: 'SearchLog', kind: 'log', content: { message: '真实返回摘要', private: 'hidden-json' } }], reports: [], links: [{ id: 'l1', evidence_id: 'e1', claim: '待核验', report_id: 'r1' }], checkpoints: [], toolCalls: [{ id: 'audit-one', tool_name: 'SearchLog', status: 'failed', error_message: '工具失败' }] }
let persisted: DiagnosticRecord
beforeEach(() => {
  setActivePinia(createPinia()); persisted = structuredClone(record)
  const auth = useAuthStore(); auth.user = { id: 'one', email: 'one@test.test' }
  vi.spyOn(auth, 'request').mockImplementation(async (path, options) => {
    if (path === '/aiops/alerts/active') return { items: [{ alertname: 'CPUHigh', service: 'api', severity: 'critical', status: 'firing', source: 'Alertmanager', startsAt: '', annotations: { summary: 'CPU 升高' } }] }
    if (path === '/aiops/diagnostics') return options?.method === 'POST' ? persisted : [persisted]
    if (path.endsWith('/evidence-chain')) return chain
    if (path === '/aiops/diagnostics/task-one') return persisted
    if (path === '/aiops/diagnostic-cases') return [savedCase]
    if (path === '/aiops/diagnostic-cases/case-one') return savedCase
    if (path === '/knowledge-bases') return [{ id: 'kb', name: '默认知识库' }]
    if (path === '/knowledge-bases/kb/documents') return [{ id: 'doc-one' }]
    if (path.endsWith(':cancel')) { persisted.status = 'cancelled'; persisted.backgroundJob.status = 'cancelled'; return persisted.backgroundJob }
    throw new Error('unexpected path: ' + path)
  })
})
it('prefills real alert, creates only query/alertNames, consumes SSE then restores persistent failure and evidence/cases', async () => {
  const auth = useAuthStore()
  vi.spyOn(auth, 'stream').mockImplementation(async function* (): AsyncGenerator<SseEvent> {
    yield { id: 'j:1', channel: 'aiops', timestamp: '', type: 'task.status', data: { status: 'running', task: { message: 'Planner：计划 v1', progress: .1 } } }
    yield { id: 'j:2', channel: 'aiops', timestamp: '', type: 'tool.call', data: { toolId: 'audit-one', toolName: 'SearchLog', status: 'failed' } }
    persisted.status = 'failed'; persisted.backgroundJob.status = 'failed'
    throw new Error('network disconnected')
  })
  const view = mount(AiopsView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  await view.get('.aiops-alert').trigger('click')
  expect((view.get('textarea').element as HTMLTextAreaElement).value).toContain('CPUHigh')
  await view.get('form').trigger('submit'); await flushPromises()
  const call = vi.mocked(auth.request).mock.calls.find(([path, options]) => path === '/aiops/diagnostics' && options?.method === 'POST')
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ query: '请诊断告警「CPUHigh」，服务：api。CPU 升高', alertNames: ['CPUHigh'] })
  const store = useAiopsStore()
  expect(store.activeTask?.status).toBe('failed'); expect(store.history[0]?.status).toBe('failed')
  expect(store.evidenceChain).toEqual(chain); expect(store.cases).toEqual([savedCase])
  expect(auth.stream).toHaveBeenCalledTimes(1)
  expect(view.text()).toContain('诊断：失败'); expect(view.text()).toContain('后台任务：失败')
  expect(view.text()).toContain('未自动重新订阅'); expect(view.text()).toContain('Planner：计划 v1')
  expect(view.text()).toContain('待核验'); expect(view.text()).not.toContain('hidden-json')
  expect(view.get('.aiops-provenance details').attributes('open')).toBeUndefined()
  view.unmount()
})
it('cancels using background job id and selects persisted history without subscribing', async () => {
  const store = useAiopsStore(); const auth = useAuthStore(); const stream = vi.spyOn(auth, 'stream')
  await store.select(record.id); expect(store.cancellable).toBe(true)
  await store.cancel()
  expect(auth.request).toHaveBeenCalledWith('/background-jobs/job-one:cancel', expect.anything())
  expect(store.activeTask?.status).toBe('cancelled'); expect(stream).not.toHaveBeenCalled()
})
it('opens structured case and resolves its owner knowledge document', async () => {
  const store = useAiopsStore(); await store.inspectCase('case-one')
  expect(store.selectedCase).toEqual(savedCase)
  expect(store.documentTarget).toEqual({ path: '/knowledge', query: { kb: 'kb', document: 'doc-one' } })
})
it('renders safe readable report, fallback and provenance without raw JSON', async () => {
  persisted.report = { mode: 'fallback', content: '# 告警分析报告\n## 风险评估\n证据不足（证据：e1）\n```json\n{"secret":"hidden-json"}\n```\n<script>alert(1)</script>' }
  const view = mount(AiopsView, { global: { stubs: ['RouterLink'] } }); await flushPromises()
  await useAiopsStore().select(record.id); await flushPromises()
  expect(view.text()).toContain('保守 fallback'); expect(view.text()).toContain('证据不足（证据：e1）')
  expect(view.find('script').exists()).toBe(false); expect(view.text()).not.toContain('hidden-json')
  expect(summary({ message: '{"x":1}' })).not.toContain('{')
  expect(reportHtml('[bad](javascript:alert(1))')).not.toContain('href="javascript:')
  expect(eventSummary({ id: '', timestamp: '', channel: 'aiops', type: 'tool.call', data: { toolId: 't', status: 'failed' } })).toContain('失败')
  view.unmount()
})
it('ignores late reads after owner change', async () => {
  const auth = useAuthStore(); const store = useAiopsStore()
  let release!: (value: unknown) => void
  vi.mocked(auth.request).mockImplementation(() => new Promise(resolve => { release = resolve }))
  const loading = store.refreshAlerts(); auth.user = { id: 'two', email: 'two@test.test' }; release({ items: [{ alertname: 'old' }] })
  await loading; expect(store.activeAlerts).toEqual([])
})
it('manual query completes from persistent success and does not invent a live success state', async () => {
  const auth = useAuthStore(); const store = useAiopsStore()
  vi.spyOn(auth, 'stream').mockImplementation(async function* (): AsyncGenerator<SseEvent> {
    expect(store.activeTask?.status).toBe('accepted')
    persisted.status = 'succeeded'; persisted.backgroundJob.status = 'succeeded'
    persisted.report = { mode: 'fallback', content: '# 告警分析报告\n证据不足' }
    yield { id: 'j:end', channel: 'aiops', timestamp: '', type: 'complete', data: {} }
  })
  await store.create({ query: '手工诊断' })
  expect(store.activeTask?.status).toBe('succeeded'); expect(store.activeTask?.report?.mode).toBe('fallback')
  expect(auth.stream).toHaveBeenCalledTimes(1)
  expect(store.busy).toBe(false)
})
it('reports unavailable alerts and creation errors without fabricating history', async () => {
  const auth = useAuthStore(); const store = useAiopsStore()
  vi.mocked(auth.request).mockRejectedValue(new Error('unavailable'))
  const stream = vi.spyOn(auth, 'stream')
  await store.refreshAlerts(); await store.create({ query: '手工诊断' })
  expect(store.alertsError).toContain('不可用'); expect(store.error).toBeTruthy()
  expect(store.history).toEqual([]); expect(store.activeTask).toBeNull(); expect(stream).not.toHaveBeenCalled()
})
