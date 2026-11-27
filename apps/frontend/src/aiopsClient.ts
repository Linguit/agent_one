import type { ActiveAlert, BackgroundJob, DiagnosticCase, DiagnosticEvidenceChain, DiagnosticInput, DiagnosticRecord, KnowledgeBase, KnowledgeDocument } from '@super-ai/api-contracts'
import type { useAuthStore } from './auth'

export function createAiopsClient(auth: Pick<ReturnType<typeof useAuthStore>, 'request' | 'stream'>) {
  const path = (id: string) => '/aiops/diagnostics/' + encodeURIComponent(id)
  const post = (body: object) => ({ method: 'POST', body: JSON.stringify(body) })
  return {
    history: () => auth.request<DiagnosticRecord[]>('/aiops/diagnostics'),
    alerts: () => auth.request<{ items: ActiveAlert[] }>('/aiops/alerts/active'),
    cases: () => auth.request<DiagnosticCase[]>('/aiops/diagnostic-cases'),
    case: (id: string) => auth.request<DiagnosticCase>('/aiops/diagnostic-cases/' + encodeURIComponent(id)),
    create: (body: DiagnosticInput) => auth.request<DiagnosticRecord>('/aiops/diagnostics', post(body)),
    detail: (id: string) => auth.request<DiagnosticRecord>(path(id)),
    chain: (id: string) => auth.request<DiagnosticEvidenceChain>(path(id) + '/evidence-chain'),
    stream: (id: string, jobId: string, signal: AbortSignal) => auth.stream(path(id) + ':stream', { ...post({ jobId }), signal }),
    cancel: (jobId: string) => auth.request<BackgroundJob>('/background-jobs/' + encodeURIComponent(jobId) + ':cancel', post({})),
    bases: () => auth.request<KnowledgeBase[]>('/knowledge-bases'),
    documents: (kb: string) => auth.request<KnowledgeDocument[]>('/knowledge-bases/' + encodeURIComponent(kb) + '/documents'),
  }
}
