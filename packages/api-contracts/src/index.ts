export type RequestMeta = { requestId: string }
export type SuccessEnvelope<T> = { ok: true; data: T; meta: RequestMeta }
export type ErrorCategory = 'AUTH' | 'BUSINESS' | 'VALIDATION' | 'SYSTEM'
export type ErrorCode = 'AUTH_UNAUTHORIZED' | 'AUTH_INVALID_CREDENTIALS' | 'BUSINESS_NOT_FOUND' | 'VALIDATION_INVALID_REQUEST' | 'SYSTEM_INTERNAL_ERROR'
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
  AUTH_INVALID_CREDENTIALS: { category: 'AUTH', httpStatus: 401, message: '邮箱或密码错误。' },
  BUSINESS_NOT_FOUND: { category: 'BUSINESS', httpStatus: 404, message: '请求的资源不存在。' },
  VALIDATION_INVALID_REQUEST: { category: 'VALIDATION', httpStatus: 422, message: '请求参数无效。' },
  SYSTEM_INTERNAL_ERROR: { category: 'SYSTEM', httpStatus: 500, message: '服务暂时不可用。' },
} as const
export const OPENAPI_PATHS = ['/health'] as const

export interface HealthResponse { status: 'ok' }
