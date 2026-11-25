import { describe, expect, it } from 'vitest'
import { DIAGNOSTIC_PATHS, DIAGNOSTIC_STATUS_MAP, type SseEvent } from '../src'

describe('诊断与共享事件契约', () => {
  it('显式映射 accepted/queued，复用通用 cancel/retry', () => {
    expect(DIAGNOSTIC_STATUS_MAP).toEqual({ queued: 'accepted', running: 'running',
      succeeded: 'succeeded', failed: 'failed', cancelled: 'cancelled' })
    expect(DIAGNOSTIC_PATHS).toHaveLength(4)
    expect(DIAGNOSTIC_PATHS.some(path => /cancel|retry/.test(path))).toBe(false)
    const event: SseEvent = { id: 'job:1', type: 'task.status', channel: 'aiops', timestamp: '',
      data: { status: 'running', task: { message: 'Planner：检索 SOP', progress: 0.1 } } }
    expect(event.data.task.message).toContain('SOP')
  })
})
