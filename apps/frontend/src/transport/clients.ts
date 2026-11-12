import type { ApiEnvelope, ApiError, SseEvent } from '@super-ai/api-contracts'

export type RequestOptions = RequestInit & {
  requestId?: string
  bearer?: string
  onUnauthorized?: () => void
}

export class ApiRequestError extends Error {
  constructor(readonly status: number, readonly detail?: ApiError) {
    super(detail?.message ?? '请求失败，请稍后重试。')
  }
}

async function request(url: string, options: RequestOptions): Promise<Response> {
  const { requestId, bearer, onUnauthorized, ...init } = options
  const headers = new Headers(init.headers)
  if (requestId) headers.set('X-Request-ID', requestId)
  if (bearer) headers.set('Authorization', `Bearer ${bearer}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(url, { ...init, headers })
  if (response.status === 401) onUnauthorized?.()
  return response
}

export async function apiClient<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const response = await request(url, options)
  const envelope = await response.json().catch(() => null) as ApiEnvelope<T> | null
  if (!response.ok || envelope?.ok !== true) {
    throw new ApiRequestError(response.status, envelope?.ok === false ? envelope.error : undefined)
  }
  return envelope.data
}

class SseParser {
  private buffer = ''

  push(chunk: string): SseEvent[] {
    this.buffer += chunk
    const frames = this.buffer.split(/\r?\n\r?\n/)
    this.buffer = frames.pop() ?? ''
    return frames.flatMap(frame => {
      const lines = frame.split(/\r?\n/)
      const type = lines.find(line => line.startsWith('event:'))?.slice(6).trim()
      const data = lines.filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).replace(/^ /, '')).join('\n')
      return type && data ? [{ ...JSON.parse(data), type } as SseEvent] : []
    })
  }
}

export function parseSseFrames(chunks: Iterable<string>): SseEvent[] {
  const parser = new SseParser()
  return Array.from(chunks).flatMap(chunk => parser.push(chunk))
}

export async function* sseClient(url: string, options: RequestOptions = {}): AsyncGenerator<SseEvent> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'text/event-stream')
  const response = await request(url, { ...options, headers })
  if (!response.ok || !response.body) throw new ApiRequestError(response.status)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = new SseParser()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      yield* parser.push(decoder.decode(value, { stream: true }))
    }
    yield* parser.push(decoder.decode())
  } finally {
    try {
      await reader.cancel()
    } finally {
      reader.releaseLock()
    }
  }
}
