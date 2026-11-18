import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '../src/auth'
import KnowledgeIndexView from '../src/KnowledgeIndexView.vue'
import { useKnowledgeStore } from '../src/knowledgeStore'

const doc = {
  id: 'doc', knowledgeBaseId: 'kb', filename: 'sample.md', size: 8,
  mimeType: 'text/markdown', uploadedAt: '2026-11-17', sha256: 'abc',
  indexStatus: 'pending', chunking: { strategy: 'paragraph' },
}
const path = '/knowledge-bases/kb/documents'
const preview = { documentId: 'doc', chunking: doc.chunking,
  chunks: [{ index: 0, start: 0, end: 8, excerpt: '实际片段' }] }
const fixed = { strategy: 'fixed-character', maxCharacters: 20, overlap: 3 } as const

function fixture() {
  let listed = false
  let conflict = false
  let status = 'pending'
  const uploads: FormData[] = []
  const requests: string[] = []
  const response = (data: unknown) => new Response(JSON.stringify({ ok: true, data }))
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
    const target = new URL(url, 'http://localhost').pathname.replace(/^\/api/, '')
    const method = init.method ?? 'GET'
    requests.push(method + ' ' + target)
    if (target === '/auth/login') return response({ token: 'session', user: { id: 'owner', email: 'a@b.test' } })
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer session')
    if (target === '/knowledge-bases') return response([{ id: 'kb', name: '默认' }])
    if (target === path && method === 'POST') {
      expect(new Headers(init.headers).has('Content-Type')).toBe(false)
      const body = init.body as FormData
      uploads.push(body)
      if (conflict && !body.has('overwrite')) return new Response(JSON.stringify({
        ok: false, error: { code: 'BUSINESS_CONFLICT', message: '已有文档' },
      }), { status: 409 })
      listed = true
      return response(doc)
    }
    if (target === path) return response(listed ? [doc] : [])
    if (target === path + '/doc' && method === 'DELETE') {
      listed = false
      return response({ deleted: true })
    }
    if (target === path + '/doc') return response(doc)
    if (target.endsWith('/chunk-preview')) return response(preview)
    if (target.endsWith(':retry')) status = 'pending'
    if (target.includes('/index-tasks')) return response({
      id: 't1', status, failureReason: status === 'failed' ? '模型连接失败' : null,
    })
    throw new Error('意外的测试请求')
  }))
  return { uploads, requests, setConflict: () => { conflict = true },
    fail: () => { status = 'failed' } }
}

let pinia: ReturnType<typeof createPinia>
beforeEach(() => { pinia = createPinia(); setActivePinia(pinia); localStorage.clear() })
afterEach(() => {
  useKnowledgeStore().reset()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
async function login() {
  await useAuthStore().login({ email: 'a@b.test', password: 'password' })
}

it('使用认证信封与 multipart，显式覆盖、轮询失败、重试和确认删除', async () => {
  vi.useFakeTimers()
  const mock = fixture()
  await login()
  const store = useKnowledgeStore()
  await store.load()
  const file = new File(['# 示例'], 'sample.md')
  await store.upload(file, fixed)
  expect(mock.uploads[0]?.get('file')).toBeInstanceOf(File)
  expect(mock.uploads[0]?.get('maxCharacters')).toBe('20')
  expect(mock.uploads[0]?.get('overlap')).toBe('3')
  mock.fail()
  await vi.advanceTimersByTimeAsync(2000)
  expect(store.tasks.doc?.failureReason).toBe('模型连接失败')
  await store.index('doc')
  expect(mock.requests).toContain('POST ' + path + '/doc/index-tasks/t1:retry')
  mock.setConflict()
  await store.upload(file, { strategy: 'markdown-heading' })
  expect(store.overwrite?.file).toBe(file)
  expect(mock.uploads[1]?.has('overwrite')).toBe(false)
  await store.confirmOverwrite()
  expect(mock.uploads[2]?.get('overwrite')).toBe('true')
  expect(mock.uploads[2]?.get('strategy')).toBe('markdown-heading')
  expect(mock.uploads[2]?.has('maxCharacters')).toBe(false)
  expect(mock.uploads[2]?.has('overlap')).toBe(false)
  store.deletion = store.documents[0]!
  await store.confirmDelete()
  expect(store.documents).toEqual([])
  expect(mock.requests).toContain('DELETE ' + path + '/doc')
  await store.upload(file, { strategy: 'paragraph' })
  await store.inspect('doc')
  useAuthStore().user = { id: 'other', email: 'other@b.test' }
  expect(store.documents).toEqual([])
  expect(store.knowledgeBases).toEqual([])
  expect(store.tasks).toEqual({})
  expect(store.preview).toBeNull()
  expect(store.detail).toBeNull()
  expect(vi.getTimerCount()).toBe(0)
})

it('在文档行内展开服务端预览，并按策略切换上传字段', async () => {
  const mock = fixture()
  await login()
  const wrapper = mount(KnowledgeIndexView, { global: { plugins: [pinia] } })
  try {
    await flushPromises()
    expect(wrapper.findAll('select')).toHaveLength(1)
    await wrapper.get('select').setValue('paragraph')
    expect(wrapper.find('input[type=number]').exists()).toBe(false)
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['文本'], 'sample.md', { type: 'text/markdown' })],
    })
    await input.trigger('change')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mock.uploads[0]?.get('strategy')).toBe('paragraph')
    expect(wrapper.find('.document-details').exists()).toBe(false)
    await wrapper.get('[aria-expanded=false]').trigger('click')
    await flushPromises()
    expect(wrapper.get('.document-list li .metadata-scroll').text()).toContain('abc')
    expect(wrapper.get('.document-list li .preview-scroll').text()).toContain('实际片段')
    const css = readFileSync(process.cwd() + '/src/KnowledgeIndexView.vue', 'utf8')
    expect(css).toMatch(/\.document-list\s*\{[^}]*max-block-size:[^}]*overflow: auto/)
    expect(css).toMatch(/\.metadata-scroll, \.preview-scroll\s*\{[^}]*max-block-size:[^}]*overflow: auto/)
    expect(css).toMatch(/table\s*\{[^}]*min-width:/)
  } finally {
    wrapper.unmount()
  }
})
