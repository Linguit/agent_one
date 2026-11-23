<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { MemoryMode } from '@super-ai/api-contracts'
import { useChatStore } from './chatStore'
import { useConfigurationStore } from './configurationStore'
import { safeMarkdown } from './chatPresentation'
import ChatReferences from './components/ChatReferences.vue'
import ChatConfiguration from './components/ChatConfiguration.vue'

const store = useChatStore()
const configuration = useConfigurationStore()
const route = useRoute()
const router = useRouter()
const draft = ref('')
const busy = ref(false)
const error = ref('')
const composing = ref(false)
const transcript = ref<HTMLElement>()
const configurationOpen = ref(true)
const liveTools = computed(() => store.liveToolCalls)
async function run(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '请求失败，请重试。' }
  finally { busy.value = false }
}
async function load() {
  const target = route.query.session
  await run(async () => {
    await Promise.all([store.refresh(), configuration.refresh()])
    if (typeof target === 'string') await store.select(target)
    syncSessionUrl(store.active?.id)
  })
}
onMounted(load)
function syncSessionUrl(id: string | undefined) {
  if (route.name !== 'chat' || route.query.session === id) return
  void router.replace({ name: 'chat', query: id ? { session: id } : {} })
}
watch(() => store.active?.id, syncSessionUrl)
async function send() {
  const content = draft.value.trim()
  if (!content || busy.value || composing.value) return
  await run(async () => {
    if (!store.active) await store.create()
    const id = store.active?.id
    if (!id) throw new Error('无法创建会话，请重试。')
    draft.value = ''
    try { await store.send(id, { content }) }
    catch (cause) { if (!draft.value) draft.value = content; throw cause }
  })
}
function keydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || composing.value || event.keyCode === 229) return
  event.preventDefault()
  void send()
}
watch(() => [store.liveTurn?.content, store.liveTurn?.reasoning, store.messages.length, store.active?.id], async () => {
  const element = transcript.value
  const follow = !element || element.scrollHeight - element.scrollTop - element.clientHeight < 100
  await nextTick()
  if (follow && transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight
})
function memory(event: Event) {
  if (store.active) void run(() => store.updateMemory(store.active!.id,
    (event.target as HTMLSelectElement).value as MemoryMode))
}
</script>

<template>
  <section class="chat-workspace" :class="{ 'configuration-closed': !configurationOpen }" aria-label="聊天工作区">
    <div class="chat-conversation">
      <header class="chat-toolbar">
        <span>{{ store.active?.title ?? '新会话' }}</span>
        <button :aria-expanded="configurationOpen" @click="configurationOpen = !configurationOpen">Prompt 与 Skill</button>
      </header>
      <div ref="transcript" class="chat-transcript" role="log" aria-label="聊天消息" tabindex="0">
        <article v-for="message in store.messages.filter(item => item.role === 'user' || item.role === 'assistant')"
          :key="message.id" class="chat-message" :class="message.role">
          <small>{{ message.role === 'user' ? '你' : '助手' }}</small>
          <div class="chat-bubble markdown" v-html="safeMarkdown(message.content)" />
          <ChatReferences v-if="message.role === 'assistant'" :references="message.metadata.references" />
          <details v-if="message.metadata.toolCallIds.length" class="chat-tools"><summary>工具调用</summary>
            <article v-for="audit in store.toolAudits.filter(item => message.metadata.toolCallIds.includes(item.id))" :key="audit.id">
              <span>{{ audit.toolName }} · {{ audit.status }} · {{ audit.durationMs ?? '—' }} ms</span>
              <details><summary>工具输出摘要</summary><p>{{ audit.resultSummary ?? audit.errorMessage ?? '等待结果' }}</p></details>
            </article>
          </details>
        </article>
        <template v-if="store.liveTurn">
          <article class="chat-message user"><small>你</small><div class="chat-bubble markdown" v-html="safeMarkdown(store.liveTurn.input)" /></article>
          <article class="chat-message assistant"><small>助手 · 正在回答</small>
            <details v-if="store.liveTurn.reasoning"><summary>推理过程</summary><div class="markdown" v-html="safeMarkdown(store.liveTurn.reasoning)" /></details>
            <details v-if="liveTools.length" class="chat-tools"><summary>工具调用（{{ liveTools.length }}）</summary>
              <p v-for="tool in liveTools" :key="tool.toolId">{{ tool.toolName ?? '工具' }} · {{ tool.status }}</p>
            </details>
            <div v-if="store.liveTurn.content" class="chat-bubble markdown" v-html="safeMarkdown(store.liveTurn.content)" />
            <ChatReferences :references="store.liveTurn.references" />
          </article>
        </template>
      </div>
      <div class="chat-composer-area">
        <div v-if="error" class="chat-error" role="alert">{{ error }} <button :disabled="busy" @click="load">重新加载</button></div>
        <div v-if="store.active" class="chat-memory">
          <label>记忆模式 <select :value="store.active.memoryMode" :disabled="busy" @change="memory">
            <option value="every_30_turns">每 30 轮压缩</option><option value="context_70_percent">上下文 70% 压缩</option><option value="manual">手动压缩</option>
          </select></label>
          <span>上下文 {{ store.active.contextUsagePercent.toFixed(1) }}% · {{ store.active.contextTokens }} / {{ store.active.contextWindowTokens }}</span>
          <button :disabled="busy || !store.active.canCompact" @click="run(() => store.compactMemory(store.active!.id))">压缩记忆</button>
        </div>
        <form class="chat-composer" aria-label="发送消息" @submit.prevent="send">
          <textarea v-model="draft" aria-label="消息" rows="3" placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            @keydown="keydown" @compositionstart="composing = true" @compositionend="composing = false" />
          <button class="primary-button" :disabled="busy || !draft.trim() || composing">{{ busy ? '处理中…' : '发送' }}</button>
        </form>
      </div>
    </div>
    <ChatConfiguration v-if="configurationOpen" />
  </section>
</template>
