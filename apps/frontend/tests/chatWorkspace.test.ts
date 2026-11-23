import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ChatSession, SseEvent } from '@super-ai/api-contracts'
import ChatView from '../src/ChatView.vue'
import ChatReferences from '../src/components/ChatReferences.vue'
import ChatConfiguration from '../src/components/ChatConfiguration.vue'
import ChatSessions from '../src/components/ChatSessions.vue'
import { useAuthStore } from '../src/auth'
import { useChatStore } from '../src/chatStore'
import { useConfigurationStore } from '../src/configurationStore'
import { safeMarkdown, rankedReferences, stage } from '../src/chatPresentation'
const routing = vi.hoisted(() => ({ query: {} as Record<string, string> }))
vi.mock('vue-router', async importOriginal => ({
  ...await importOriginal<typeof import('vue-router')>(),
  useRoute: () => ({ name: 'chat', query: routing.query }),
  useRouter: () => ({ replace: vi.fn().mockResolvedValue(undefined) }),
}))

const session: ChatSession = { id: 'one', title: '测试会话', createdAt: '', updatedAt: '',
  memoryMode: 'manual', memorySummary: '', contextTokens: 10, contextWindowTokens: 100,
  contextUsagePercent: 10, compactedMessageCount: 0, lastCompactedAt: null, canCompact: true }
beforeEach(() => {
  routing.query = {}
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = { id: 'user', email: 'test@example.test' }
  vi.spyOn(auth, 'request').mockImplementation(async path => {
    if (path.endsWith('/configuration')) return { prompts: [], skills: [], selectedPromptId: null, selectedSkillIds: [] }
    if (path.endsWith('/tool-call-audits')) return []
    if (path.endsWith('/sessions')) return [session]
    return { session, messages: [] }
  })
})
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

it('waits 28ms per Unicode character before reading subsequent events and reconciles complete', async () => {
  vi.useFakeTimers()
  const store = useChatStore()
  let reachedComplete = false
  vi.spyOn(useAuthStore(), 'stream').mockImplementation(async function* (): AsyncGenerator<SseEvent> {
    const base = { id: '1', channel: 'chat', timestamp: '' } as const
    yield { ...base, type: 'content.delta', data: { text: '你😀' } } satisfies SseEvent
    reachedComplete = true
    yield { ...base, type: 'complete', data: {} } satisfies SseEvent
  })
  const sending = store.send('one', { content: '问' })
  await vi.advanceTimersByTimeAsync(0)
  expect(store.liveTurn?.content).toBe('你')
  await vi.advanceTimersByTimeAsync(27)
  expect(store.liveTurn?.content).toBe('你')
  await vi.advanceTimersByTimeAsync(1)
  expect(store.liveTurn?.content).toBe('你😀')
  expect(reachedComplete).toBe(false)
  await vi.advanceTimersByTimeAsync(28)
  await sending
  expect(reachedComplete).toBe(true)
  expect(store.liveTurn).toBeNull()
  expect(store.detail).toEqual({ session, messages: [] })
})

it('keeps transcript blank, respects IME and Shift+Enter, sends Enter and keeps failed draft recoverable', async () => {
  const store = useChatStore()
  store.detail = { session, messages: [] }
  const send = vi.spyOn(store, 'send').mockRejectedValueOnce(new Error('流失败'))
  const view = mount(ChatView)
  await flushPromises()
  expect(view.get('[role=log]').text()).toBe('')
  const input = view.get('textarea[aria-label=消息]')
  await input.setValue('你好')
  await input.trigger('compositionstart')
  await input.trigger('keydown', { key: 'Enter', isComposing: true })
  await input.trigger('compositionend')
  await input.trigger('keydown', { key: 'Enter', shiftKey: true })
  expect(send).not.toHaveBeenCalled()
  await input.trigger('keydown', { key: 'Enter' })
  await flushPromises()
  expect(send).toHaveBeenCalledWith('one', { content: '你好' })
  expect((input.element as HTMLTextAreaElement).value).toBe('你好')
  expect(view.get('[role=alert]').text()).toContain('流失败')
  view.unmount()
})

it('sanitizes Markdown and disables raw HTML', () => {
  const html = safeMarkdown('**正文**<img src=x onerror=alert(1)><script>alert(1)</script>\n\n[危险](javascript:alert(1))')
  expect(html).toContain('<strong>正文</strong>')
  expect(html).not.toMatch(/<script|<img|javascript:|onerror=/)
})

it('ranks at most five references, shows missing stages and owner document navigation', () => {
  const references = Array.from({ length: 7 }, (_, index) => ({ title: `资料${index}`, uri: '/source',
    documentId: 'doc', knowledgeBaseId: 'kb', chunkId: `${index}`, rerankRank: 7 - index,
    score: index, excerpt: '证据', vectorRank: null, vectorScore: null, bm25Rank: 2, bm25Score: .2,
    metadata: { filename: '资料.md' } }))
  expect(rankedReferences(references).map(item => item.rerankRank)).toEqual([1, 2, 3, 4, 5])
  expect(stage(null, null)).toBe('未命中')
  const wrapper = mount(ChatReferences, { props: { references }, global: { stubs: { RouterLink: true } } })
  expect(wrapper.findAll('article')).toHaveLength(5)
  expect(wrapper.text()).toContain('未命中')
  expect(wrapper.find('router-link-stub').attributes('to')).toBeDefined()
})

it('manages sessions in the global sidebar component', async () => {
  const store = useChatStore()
  store.sessions = [session]
  const select = vi.spyOn(store, 'select').mockResolvedValue()
  const remove = vi.spyOn(store, 'remove').mockResolvedValue()
  const create = vi.spyOn(store, 'create').mockResolvedValue()
  const wrapper = mount(ChatSessions)
  await wrapper.get('button').trigger('click'); await flushPromises()
  await wrapper.get('.chat-session-list button').trigger('click'); await flushPromises()
  await wrapper.get('button[aria-label="删除会话 测试会话"]').trigger('click'); await flushPromises()
  expect(create).toHaveBeenCalledOnce(); expect(select).toHaveBeenCalledWith('one'); expect(remove).toHaveBeenCalledWith('one')
})

it('supports prompt CRUD, skill selection/upload/delete and recovery', async () => {
  const store = useConfigurationStore()
  store.configuration = { prompts: [{ id: 'p', label: '提示', content: '正文' }],
    skills: [{ id: 's', filename: 'SKILL.md', name: '技能', description: '描述', summary: '摘要', content: '', metadata: {} }],
    selectedPromptId: null, selectedSkillIds: [] }
  const selection = vi.spyOn(store, 'saveSelection').mockResolvedValue()
  const create = vi.spyOn(store, 'createPrompt').mockRejectedValueOnce(new Error('保存失败')).mockResolvedValue()
  const update = vi.spyOn(store, 'updatePrompt').mockResolvedValue()
  const remove = vi.spyOn(store, 'deletePrompt').mockResolvedValue()
  const upload = vi.spyOn(store, 'uploadSkill').mockResolvedValue()
  const deleteSkill = vi.spyOn(store, 'deleteSkill').mockResolvedValue()
  const wrapper = mount(ChatConfiguration)
  await wrapper.findAll('input[type=radio]')[1]!.setValue(true); await flushPromises()
  expect(selection).toHaveBeenLastCalledWith({ selectedPromptId: 'p', selectedSkillIds: [] })
  await wrapper.get('input[type=checkbox]').setValue(true); await flushPromises()
  expect(selection).toHaveBeenLastCalledWith({ selectedPromptId: null, selectedSkillIds: ['s'] })
  await wrapper.get('form input').setValue('新增')
  await wrapper.get('form textarea').setValue('内容')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('[role=alert]').text()).toBe('保存失败')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(create).toHaveBeenCalledTimes(2)
  const button = (text: string) => wrapper.findAll('button').find(item => item.text() === text)!
  await button('编辑').trigger('click')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(update).toHaveBeenCalledWith('p', { label: '提示', content: '正文' })
  await button('删除').trigger('click'); await flushPromises(); expect(remove).toHaveBeenCalledWith('p')
  const file = new File(['技能'], 'SKILL.md', { type: 'text/markdown' })
  Object.defineProperty(wrapper.get('input[type=file]').element, 'files', { value: [file] })
  await wrapper.get('input[type=file]').trigger('change'); await flushPromises(); expect(upload).toHaveBeenCalledWith(file)
  await button('删除技能').trigger('click'); await flushPromises(); expect(deleteSkill).toHaveBeenCalledWith('s')
})

it('shows collapsible reasoning and tool lifecycle without raw arguments', async () => {
  const store = useChatStore()
  store.liveTurn = { sessionId: 'one', input: '问题', content: '回答', reasoning: '推理', references: [],
    tools: [{ toolId: 't', toolName: 'knowledge_retrieval', status: 'completed', delta: { secret: '不得显示' } }] }
  const wrapper = mount(ChatView)
  await flushPromises()
  expect(wrapper.text()).toContain('推理过程')
  expect(wrapper.text()).toContain('knowledge_retrieval · completed')
  expect(wrapper.text()).not.toContain('不得显示')
  expect(wrapper.findAll('details').filter(item => item.text().includes('推理过程'))[0]?.attributes('open')).toBeUndefined()
  wrapper.unmount()
})

it('operates memory mode and manual compaction and recovers from errors', async () => {
  const store = useChatStore()
  store.detail = { session, messages: [] }
  const update = vi.spyOn(store, 'updateMemory').mockResolvedValue()
  const compact = vi.spyOn(store, 'compactMemory').mockRejectedValueOnce(new Error('压缩失败')).mockResolvedValue()
  const wrapper = mount(ChatView)
  await flushPromises()
  await wrapper.get('select').setValue('context_70_percent'); await flushPromises()
  expect(update).toHaveBeenCalledWith('one', 'context_70_percent')
  const button = () => wrapper.findAll('button').find(item => item.text() === '压缩记忆')!
  await button().trigger('click'); await flushPromises()
  expect(wrapper.get('[role=alert]').text()).toContain('压缩失败')
  await button().trigger('click'); await flushPromises()
  expect(compact).toHaveBeenCalledTimes(2)
  expect(wrapper.find('[role=alert]').exists()).toBe(false)
  wrapper.unmount()
})

it('restores historical references and defaults safe tool output to collapsed', async () => {
  const store = useChatStore()
  const messages = [{ id: 'answer', sessionId: 'one', sequence: 1, role: 'assistant' as const,
    content: '有引用的回答', createdAt: '', metadata: { references: [{ title: '文档', uri: '/source' }], toolCallIds: ['t'] } },
  { id: 'next', sessionId: 'one', sequence: 2, role: 'assistant' as const,
    content: '无引用的回答', createdAt: '', metadata: { references: [], toolCallIds: [] } }]
  vi.spyOn(useAuthStore(), 'request').mockImplementation(async path => {
    if (path.endsWith('/sessions')) return [session]
    if (path.endsWith('/configuration')) return { prompts: [], skills: [], selectedPromptId: null, selectedSkillIds: [] }
    return { session, messages }
  })
  store.detail = { session, messages }
  store.toolAudits = [{ id: 't', ownerUserId: 'user', chatSessionId: 'one', diagnosticTaskId: null,
    toolName: 'Search', arguments: { raw: '不展示的参数' }, status: 'completed', resultSummary: '安全摘要',
    errorMessage: null, startedAt: '', completedAt: '', durationMs: 5 }]
  const wrapper = mount(ChatView, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  const answers = wrapper.findAll('.chat-message.assistant')
  expect(answers[0]!.findAll('.chat-references')).toHaveLength(1)
  expect(answers[1]!.findAll('.chat-references')).toHaveLength(0)
  expect(wrapper.text()).toContain('安全摘要')
  expect(wrapper.text()).not.toContain('不展示的参数')
  const output = wrapper.findAll('details').find(item => item.get('summary').text() === '工具输出摘要')!
  expect(output.attributes('open')).toBeUndefined()
  wrapper.unmount()
})

it('reloads the selected session from URL without persisting domain data locally', async () => {
  routing.query = { session: 'one' }
  const store = useChatStore()
  const selected = vi.spyOn(store, 'select')
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  const wrapper = mount(ChatView)
  await flushPromises()
  expect(selected).toHaveBeenCalledWith('one')
  expect(store.active?.id).toBe('one')
  expect(storage).not.toHaveBeenCalled()
  wrapper.unmount()
})
