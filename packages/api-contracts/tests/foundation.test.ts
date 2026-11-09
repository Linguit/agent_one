import { describe, expect, expectTypeOf, it } from 'vitest'
import type { HealthResponse } from '../src/index'

describe('基础契约', () => {
  it('健康响应只允许 ok', () => {
    const response: HealthResponse = { status: 'ok' }
    expect(response).toEqual({ status: 'ok' })
    expectTypeOf(response.status).toEqualTypeOf<'ok'>()
    // @ts-expect-error 错误状态不满足健康响应契约
    const invalid: HealthResponse = { status: 'unknown' }
    void invalid
  })
})
