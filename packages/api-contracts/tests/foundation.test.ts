import { describe, expect, expectTypeOf, it } from 'vitest'
import { BACKGROUND_JOB_PATHS, OPENAPI_PATHS } from '../src/index'
import type { BackgroundJob, BackgroundJobResponse, HealthResponse } from '../src/index'

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

describe('后台任务契约', () => {
  it('公开四个管理路径及任务状态', () => {
    expect(OPENAPI_PATHS).toEqual(['/health', ...BACKGROUND_JOB_PATHS])
    expect(BACKGROUND_JOB_PATHS).toEqual([
      '/background-jobs',
      '/background-jobs/{id}',
      '/background-jobs/{id}:cancel',
      '/background-jobs/{id}:retry',
    ])
    expectTypeOf<Extract<BackgroundJobResponse, { ok: true }>['data']>()
      .toEqualTypeOf<BackgroundJob>()
    expectTypeOf<BackgroundJob['status']>()
      .toEqualTypeOf<'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'>()
    expectTypeOf<'payload'>().not.toExtend<keyof BackgroundJob>()
  })
})
