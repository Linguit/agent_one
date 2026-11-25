import type { ApiEnvelope, BackgroundJob, BackgroundJobStatus } from './index'

export type DiagnosticStatus = 'accepted' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type DiagnosticInput = { query: string; alertNames?: string[] }
export type DiagnosticRecord = {
  id: string
  status: DiagnosticStatus
  input: DiagnosticInput
  createdAt: string
  backgroundJob: BackgroundJob
  report: Record<string, unknown> | null
}
export type DiagnosticResponse = ApiEnvelope<DiagnosticRecord>
export type DiagnosticListResponse = ApiEnvelope<DiagnosticRecord[]>
export type DiagnosticEvidenceChain = {
  steps: Record<string, unknown>[]
  evidence: Record<string, unknown>[]
  reports: Record<string, unknown>[]
  links: Record<string, unknown>[]
  checkpoints: Record<string, unknown>[]
  toolCalls: Record<string, unknown>[]
}
export type DiagnosticStreamInput = { jobId?: string; afterSequence?: number }
export const DIAGNOSTIC_STATUS_MAP: Record<BackgroundJobStatus, DiagnosticStatus> = {
  queued: 'accepted', running: 'running', succeeded: 'succeeded', failed: 'failed', cancelled: 'cancelled',
}
export const DIAGNOSTIC_PATHS = [
  '/aiops/diagnostics', '/aiops/diagnostics/{id}',
  '/aiops/diagnostics/{id}/evidence-chain', '/aiops/diagnostics/{id}:stream',
] as const
