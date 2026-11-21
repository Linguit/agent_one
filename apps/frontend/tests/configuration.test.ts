import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ChatConfiguration } from '@super-ai/api-contracts'
import { useAuthStore } from '../src/auth'
import { useConfigurationStore } from '../src/configurationStore'
import { createConfigurationClient } from '../src/configurationClient'

const empty = (): ChatConfiguration => ({
  selectedPromptId: null, selectedSkillIds: [], prompts: [], skills: [],
})

beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().user = { id: 'alice', email: 'alice@test' }
})

it('manages editable assets, selections and deletion fallback using server configuration', async () => {
  let config = empty()
  const calls: string[] = []
  const request = vi.spyOn(useAuthStore(), 'request').mockImplementation(async (path, options) => {
    const method = options?.method ?? 'GET'
    calls.push(`${method} ${path}`)
    if (path === '/chat/configuration') {
      if (method === 'PUT') config = { ...config, ...JSON.parse(String(options?.body)) }
      return structuredClone(config)
    }
    if (path.startsWith('/chat/prompts')) {
      if (method === 'DELETE') { config.prompts = []; config.selectedPromptId = null }
      else config.prompts = [{ id: 'prompt', ...JSON.parse(String(options?.body)) }]
      return config.prompts[0] ?? { deleted: true }
    }
    if (method === 'POST') {
      expect(options?.body).toBeInstanceOf(FormData)
      expect((options?.body as FormData).get('file')).toBeInstanceOf(File)
      config.skills = [{
        id: 'skill', filename: 'SKILL.md', name: 'test', description: 'description',
        summary: 'description', content: 'body', metadata: { name: 'test' },
      }]
      return config.skills[0]
    }
    config.skills = []; config.selectedSkillIds = []
    return { deleted: true }
  })
  const store = useConfigurationStore()
  await store.refresh()
  await store.createPrompt({ label: '中文', content: '以中文回答' })
  await store.updatePrompt('prompt', { label: '编辑后', content: '新的正文' })
  expect(store.prompts[0]?.content).toBe('新的正文')
  await store.uploadSkill(new File(['body'], 'SKILL.md'))
  expect(store.skills[0]?.filename).toBe('SKILL.md')
  await store.saveSelection({ selectedPromptId: 'prompt', selectedSkillIds: ['skill'] })
  expect(store.selectedPromptId).toBe('prompt')
  expect(store.selectedSkillIds).toEqual(['skill'])
  await store.deletePrompt('prompt')
  expect(store.selectedPromptId).toBeNull()
  expect(store.selectedSkillIds).toEqual(['skill'])
  await store.deleteSkill('skill')
  expect(store.configuration).toEqual(empty())
  expect(request).toHaveBeenCalledTimes(12)
  expect(calls).toContain('PUT /chat/prompts/prompt')
})

it('clears state, discards old responses and prevents queued writes after an account switch', async () => {
  const auth = useAuthStore()
  const request = vi.spyOn(auth, 'request').mockResolvedValue(empty())
  const store = useConfigurationStore()
  await store.refresh()
  let finish!: (value: ChatConfiguration) => void
  request.mockReturnValueOnce(new Promise<ChatConfiguration>(resolve => { finish = resolve }))
  const refresh = store.refresh()
  const queued = store.createPrompt({ label: '旧用户', content: '旧用户资产' })
  await Promise.resolve()
  auth.user = { id: 'bob', email: 'bob@test' }
  finish({ ...empty(), prompts: [{ id: 'alice', label: 'Alice', content: 'secret' }] })
  await Promise.all([refresh, queued])
  expect(store.configuration).toBeNull()
  expect(request).toHaveBeenCalledTimes(2)
  await store.refresh()
  expect(store.configuration).toEqual(empty())
  auth.user = null
  expect(store.configuration).toBeNull()
})

it('does not perform reconciliation for a mutation completed after logout and recovers after failure', async () => {
  const auth = useAuthStore()
  const request = vi.spyOn(auth, 'request')
  let finish!: (value: unknown) => void
  request.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  const store = useConfigurationStore()
  const mutation = store.deleteSkill('old')
  await Promise.resolve()
  auth.user = null
  finish({ deleted: true })
  await mutation
  expect(request).toHaveBeenCalledTimes(1)
  request.mockRejectedValueOnce(new Error('network'))
  await expect(store.refresh()).rejects.toThrow('network')
  request.mockResolvedValueOnce(empty())
  await store.refresh()
  expect(store.configuration).toEqual(empty())
})

it('encodes asset ids and leaves multipart Content-Type to the transport', async () => {
  const request = vi.spyOn(useAuthStore(), 'request').mockResolvedValue({})
  const client = createConfigurationClient(useAuthStore())
  await client.deletePrompt('a/b')
  expect(request).toHaveBeenLastCalledWith('/chat/prompts/a%2Fb', { method: 'DELETE' })
  await client.uploadSkill(new File(['text'], 'SKILL.md'))
  expect(request).toHaveBeenLastCalledWith('/chat/skills', {
    method: 'POST', body: expect.any(FormData),
  })
})
