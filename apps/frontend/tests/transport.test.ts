import { afterEach, expect, it, vi } from 'vitest'
import { apiClient, parseSseFrames, sseClient } from '../src/transport'

afterEach(() => vi.unstubAllGlobals())

const frame = 'event: content.delta\r\ndata: {"id":"1","channel":"chat","timestamp":"x","data":{"text":"你好"}}\r\n\r\n'

it('拆分的 SSE 帧保留事件类型和内容', () => {
  expect(parseSseFrames([frame.slice(0, 30), frame.slice(30)])[0])
    .toMatchObject({ type: 'content.delta', data: { text: '你好' } })
})

it('HTTP 传递请求 ID、方法、JSON 和 Bearer，并解包成功数据', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ ok: true, data: { id: '1' } }))
  vi.stubGlobal('fetch', fetcher)
  await expect(apiClient<{ id: string }>('/resource', {
    requestId: 'req-1', bearer: 'session', method: 'POST', body: '{}',
  })).resolves.toEqual({ id: '1' })
  const init = fetcher.mock.calls[0]?.[1]
  expect(init.method).toBe('POST')
  expect(init.body).toBe('{}')
  expect(init.headers.get('X-Request-ID')).toBe('req-1')
  expect(init.headers.get('Authorization')).toBe('Bearer session')
  expect(init.headers.get('Content-Type')).toBe('application/json')
})

it('SSE 解码跨字节分块，并按 HTTP 401 通知会话失效', async () => {
  const bytes = new TextEncoder().encode(frame)
  const body = new ReadableStream({
    start(controller) {
      for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
      controller.close()
    },
  })
  const fetcher = vi.fn()
    .mockResolvedValueOnce(new Response(body))
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
  vi.stubGlobal('fetch', fetcher)
  const events = []
  for await (const event of sseClient('/stream')) events.push(event)
  expect(events[0]).toMatchObject({ type: 'content.delta', data: { text: '你好' } })
  expect(fetcher.mock.calls[0]?.[1].headers.get('Accept')).toBe('text/event-stream')
  const onUnauthorized = vi.fn()
  await expect(sseClient('/stream', { onUnauthorized }).next()).rejects.toMatchObject({ status: 401 })
  expect(onUnauthorized).toHaveBeenCalledOnce()
})
