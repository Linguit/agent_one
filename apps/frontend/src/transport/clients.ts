import type { ApiEnvelope, FailureEnvelope, SuccessEnvelope, SseEvent } from '@super-ai/api-contracts'

export type RequestOptions = { requestId?: string; bearer?: string }
export async function apiClient<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers()
  if (options.requestId) headers.set('X-Request-ID', options.requestId)
  if (options.bearer) headers.set('Authorization', `Bearer ${options.bearer}`)
  const response = await fetch(url, { headers })
  const envelope = (await response.json()) as ApiEnvelope<T>
  if (!response.ok || !envelope.ok) throw new Error((envelope as FailureEnvelope).error.message)
  return (envelope as SuccessEnvelope<T>).data
}

export function parseSseFrames(chunks: Iterable<string>): SseEvent[] {
  let buffer = ''
  const events: SseEvent[] = []
  for (const chunk of chunks) {
    buffer += chunk
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const event = parseFrame(frame)
      if (event) events.push(event)
    }
  }
  return events
}

function parseFrame(frame: string): SseEvent | undefined {
  const type = frame.match(/^event:\s*(.+)$/m)?.[1] as SseEvent['type'] | undefined
  const data = frame.match(/^data:\s*(.+)$/m)?.[1]
  if (!type || !data) return undefined
  return { ...JSON.parse(data), type } as SseEvent
}
