export type RequestMeta = { requestId: string }
export type SuccessEnvelope<T> = { ok: true; data: T; meta: RequestMeta }
export type ErrorCategory = 'AUTH' | 'BUSINESS' | 'VALIDATION' | 'SYSTEM'
export type ErrorCode = keyof typeof ERROR_CATALOG
export type User = { id: string; email: string }
export type AuthRequest = { email: string; password: string }
export type AuthLoginData = { token: string; user: User }
export type AuthMeData = User
export type ApiError = { code: ErrorCode; category: ErrorCategory; httpStatus: number; message: string; details?: unknown }
export type FailureEnvelope = { ok: false; error: ApiError; meta: RequestMeta }
export type ApiEnvelope<T> = SuccessEnvelope<T> | FailureEnvelope
export type Channel = 'chat' | 'aiops'
export type SseType = 'content.delta' | 'reasoning.delta' | 'tool.call' | 'reference.source' | 'task.status' | 'report' | 'complete' | 'error'
export type SseBase<T extends SseType, D> = { id: string; type: T; channel: Channel; timestamp: string; data: D }
export type ToolStatus = 'started' | 'delta' | 'completed' | 'failed'
export type SseEvent =
  | SseBase<'content.delta', { text: string }>
  | SseBase<'reasoning.delta', { text: string }>
  | SseBase<'tool.call', { toolId: string; status: ToolStatus; delta?: unknown }>
  | SseBase<'reference.source', { title: string; uri: string }>
  | SseBase<'task.status', { status: string }>
  | SseBase<'report', { content: unknown }>
  | SseBase<'complete', { result?: unknown }>
  | SseBase<'error', { error: ApiError; meta: RequestMeta }>
export const ERROR_CATALOG = {
  AUTH_UNAUTHORIZED: { category: 'AUTH', httpStatus: 401, message: '需要认证。' },
  AUTH_FORBIDDEN: { category: 'AUTH', httpStatus: 403, message: '无权访问该资源。' },
  AUTH_INVALID_CREDENTIALS: { category: 'AUTH', httpStatus: 401, message: '邮箱或密码错误。' },
  BUSINESS_NOT_FOUND: { category: 'BUSINESS', httpStatus: 404, message: '请求的资源不存在。' },
  BUSINESS_CONFLICT: { category: 'BUSINESS', httpStatus: 409, message: '资源冲突。' },
  VALIDATION_INVALID_REQUEST: { category: 'VALIDATION', httpStatus: 422, message: '请求参数无效。' },
  SYSTEM_INTERNAL_ERROR: { category: 'SYSTEM', httpStatus: 500, message: '服务暂时不可用。' },
} as const
export const BACKGROUND_JOB_PATHS = [
  '/background-jobs',
  '/background-jobs/{id}',
  '/background-jobs/{id}:cancel',
  '/background-jobs/{id}:retry',
] as const
export const KNOWLEDGE_PATHS = [
  '/knowledge-bases',
  '/knowledge-bases/{kb}/documents',
  '/knowledge-bases/{kb}/documents/{document}',
  '/knowledge-bases/{kb}/documents/{document}/chunk-preview',
] as const
export const DOCUMENT_INDEX_PATHS = [
  '/knowledge-bases/{kb}/documents/{document}/index-tasks',
  '/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}',
  '/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}:retry',
  '/knowledge-bases/{kb}/documents/{document}/index-tasks/{task}:cancel',
] as const
export const OPENAPI_PATHS = [
  '/health', ...BACKGROUND_JOB_PATHS, ...KNOWLEDGE_PATHS, ...DOCUMENT_INDEX_PATHS,
] as const
export type DocumentIndexStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type DocumentIndexTask = {
  id: string
  knowledgeBaseId: string
  documentId: string
  status: DocumentIndexStatus
  failureReason: string | null
  retryOfTaskId: string | null
  createdAt: string
  updatedAt: string
  startedAt: string | null
  completedAt: string | null
}
export type DocumentIndexTaskResponse = ApiEnvelope<DocumentIndexTask>
export type LatestDocumentIndexTaskResponse = ApiEnvelope<DocumentIndexTask | null>

export const DOCUMENT_UPLOAD_POLICY = {
  maxBytes: 10 * 1024 * 1024,
  mimeTypes: { '.md': ['text/markdown', 'text/plain'], '.pdf': ['application/pdf'] },
} as const
export const DOCUMENT_CHUNKING_DEFAULTS = { maxCharacters: 1200, overlap: 200 } as const
export const DOCUMENT_PREVIEW_LIMITS = { maxChunks: 12, maxExcerptCharacters: 400 } as const
export type ChunkingConfig =
  | { strategy: 'fixed-character'; maxCharacters: number; overlap: number }
  | { strategy: 'markdown-heading' | 'paragraph' }
export type DocumentUpload = { file: Blob; overwrite?: boolean } & (
  | { strategy?: 'fixed-character'; maxCharacters?: number; overlap?: number }
  | { strategy: 'markdown-heading' | 'paragraph'; maxCharacters?: never; overlap?: never }
)
export type KnowledgeBase = { id: string; name: string }
export type KnowledgeDocument = {
  id: string
  knowledgeBaseId: string
  filename: string
  size: number
  mimeType: 'text/markdown' | 'text/plain' | 'application/pdf'
  sha256: string
  uploadedAt: string
  indexStatus: DocumentIndexStatus
  chunking: ChunkingConfig
}
export type DocumentChunkPreview = {
  documentId: string
  chunking: ChunkingConfig
  chunks: { index: number; start: number; end: number; excerpt: string }[]
}
export type KnowledgeBaseListResponse = ApiEnvelope<KnowledgeBase[]>
export type KnowledgeDocumentListResponse = ApiEnvelope<KnowledgeDocument[]>
export type KnowledgeDocumentResponse = ApiEnvelope<KnowledgeDocument>
export type DocumentChunkPreviewResponse = ApiEnvelope<DocumentChunkPreview>
export type DocumentDeleteResponse = ApiEnvelope<{ deleted: true }>

export type BackgroundJobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type BackgroundJob = {
  id: string
  kind: string
  resourceType: string
  resourceId: string
  status: BackgroundJobStatus
  attempt: number
  maxAttempts: number
  timeoutSeconds: number
  availableAt: string
  leaseExpiresAt: string | null
  cancelRequestedAt: string | null
  retryOfJobId: string | null
  errorMessage: string | null
  createdAt: string
  updatedAt: string
  startedAt: string | null
  completedAt: string | null
}
export type BackgroundJobResponse = ApiEnvelope<BackgroundJob>
export type BackgroundJobListResponse = ApiEnvelope<BackgroundJob[]>

export interface HealthResponse { status: 'ok' }

export type KnowledgeRetrievalToolInput = {
  query: string
  topK?: number
  knowledgeBaseId?: string | null
  documentId?: string | null
}

export type KnowledgeRetrievalCitation = {
  chunkId: string
  documentId: string
  knowledgeBaseId: string
  source: string
  excerpt: string
  metadata: Record<string, unknown>
  vectorRank: number | null
  vectorScore: number | null
  bm25Rank: number | null
  bm25Score: number | null
  rrfScore: number
  rerankRank: number
  rerankScore: number
  score: number
}

export type KnowledgeRetrievalToolOutput = { results: KnowledgeRetrievalCitation[] }
