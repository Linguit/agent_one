import { describe, expect, expectTypeOf, it } from 'vitest'
import {
  BACKGROUND_JOB_PATHS,
  DOCUMENT_INDEX_PATHS,
  DOCUMENT_CHUNKING_DEFAULTS,
  DOCUMENT_PREVIEW_LIMITS,
  DOCUMENT_UPLOAD_POLICY,
  ERROR_CATALOG,
  KNOWLEDGE_PATHS,
  OPENAPI_PATHS,
} from '../src/index'
import type { BackgroundJob, BackgroundJobResponse, HealthResponse } from '../src/index'

it('登记文档端点、上传政策和错误码', () => {
  expect(KNOWLEDGE_PATHS).toEqual([
    '/knowledge-bases',
    '/knowledge-bases/{kb}/documents',
    '/knowledge-bases/{kb}/documents/{document}',
    '/knowledge-bases/{kb}/documents/{document}/chunk-preview',
  ])
  expect(DOCUMENT_UPLOAD_POLICY).toEqual({
    maxBytes: 10485760,
    mimeTypes: { '.md': ['text/markdown', 'text/plain'], '.pdf': ['application/pdf'] },
  })
  expect(DOCUMENT_CHUNKING_DEFAULTS).toEqual({ maxCharacters: 1200, overlap: 200 })
  expect(DOCUMENT_PREVIEW_LIMITS).toEqual({ maxChunks: 12, maxExcerptCharacters: 400 })
  expect(ERROR_CATALOG.AUTH_FORBIDDEN.httpStatus).toBe(403)
  expect(ERROR_CATALOG.BUSINESS_CONFLICT.httpStatus).toBe(409)
})

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
    expect(OPENAPI_PATHS).toEqual([
      '/health', ...BACKGROUND_JOB_PATHS, ...KNOWLEDGE_PATHS, ...DOCUMENT_INDEX_PATHS,
    ])
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
