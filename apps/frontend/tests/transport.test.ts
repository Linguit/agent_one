import { describe, expect, it } from 'vitest'
import { parseSseFrames } from '../src/transport/clients'

describe('SSE parser', () => {
  it('joins frames split across chunks', () => {
    const events = parseSseFrames(['event: content.delta\ndata: {"id":"1","channel":"chat","timestamp":"x","data":{"text":"hi"', '}}\n\n'])
    expect(events[0]?.type).toBe('content.delta')
  })
})
