<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import type {
  DocumentIndexStatus, DocumentIndexTask, KnowledgeBase, KnowledgeDocument,
} from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { documentPath, uploadAndIndex } from './knowledgeIndex'

const auth = useAuthStore()
const controller = new AbortController()
const kb = ref('')
const documents = ref<KnowledgeDocument[]>([])
const tasks = ref<Record<string, DocumentIndexTask | null>>({})
const file = ref<File>()
const busy = ref(false)
const error = ref('')
const labels: Record<DocumentIndexStatus, string> = {
  pending: '等待索引', running: '索引中', succeeded: '索引完成', failed: '索引失败', cancelled: '已取消',
}

async function refresh() {
  const { signal } = controller
  if (!kb.value) {
    const bases = await auth.request<KnowledgeBase[]>('/knowledge-bases', { signal })
    kb.value = bases[0]?.id ?? ''
  }
  if (!kb.value) return
  const items = await auth.request<KnowledgeDocument[]>(
    `/knowledge-bases/${encodeURIComponent(kb.value)}/documents`, { signal },
  )
  const current = await Promise.all(items.map(async doc => [
    doc.id,
    await auth.request<DocumentIndexTask | null>(`${documentPath(kb.value, doc.id)}/index-tasks`, { signal }),
  ] as const))
  documents.value = items
  tasks.value = Object.fromEntries(current)
}

async function perform(action: () => Promise<unknown>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (cause) {
    if (!controller.signal.aborted) error.value = cause instanceof Error ? cause.message : '请求失败。'
  } finally {
    busy.value = false
  }
}

function upload(event: Event) {
  const selected = file.value
  const form = event.currentTarget
  if (!selected || !kb.value) return
  void perform(async () => {
    await uploadAndIndex(auth.request, kb.value, selected, document => {
      documents.value = [document, ...documents.value]
      file.value = undefined
      if (form instanceof HTMLFormElement) form.reset()
    }, controller.signal)
    await refresh()
  })
}

function changeTask(doc: KnowledgeDocument, cancel: boolean) {
  const task = tasks.value[doc.id]
  const path = `${documentPath(kb.value, doc.id)}/index-tasks`
  void perform(async () => {
    await auth.request<DocumentIndexTask>(
      task ? `${path}/${encodeURIComponent(task.id)}:${cancel ? 'cancel' : 'retry'}` : path,
      { method: 'POST', signal: controller.signal },
    )
    await refresh()
  })
}

function active(task: DocumentIndexTask | null | undefined) {
  return task?.status === 'pending' || task?.status === 'running'
}

onMounted(() => { void perform(refresh) })
onUnmounted(() => controller.abort())
</script>

<template>
  <section class="index-view">
    <header>
      <button type="button" :disabled="busy" @click="perform(refresh)">刷新状态</button>
    </header>
    <form @submit.prevent="upload">
      <label>文档 <input type="file" accept=".md,.pdf" @change="file = ($event.target as HTMLInputElement).files?.[0]" /></label>
      <button :disabled="!kb || !file || busy">上传并索引</button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!busy && !documents.length">暂无文档</p>
    <ul v-else class="index-documents">
      <li v-for="doc in documents" :key="doc.id">
        <strong>{{ doc.filename }}</strong>
        <span>{{ tasks[doc.id] ? labels[tasks[doc.id]!.status] : '未提交索引' }}</span>
        <span v-if="tasks[doc.id]?.failureReason">{{ tasks[doc.id]?.failureReason }}</span>
        <button v-if="active(tasks[doc.id])" :disabled="busy" @click="changeTask(doc, true)">取消</button>
        <button v-else :disabled="busy" @click="changeTask(doc, false)">
          {{ tasks[doc.id]?.status === 'succeeded' ? '重建索引' : tasks[doc.id] ? '重试' : '开始索引' }}
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.index-view { display: grid; gap: 1rem; }
header, form, li { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
header { justify-content: space-between; }
.index-documents { display: grid; gap: 0.75rem; list-style: none; padding: 0; }
li { padding: 0.75rem 0; border-top: 1px solid #8091a340; overflow-wrap: anywhere; }
</style>
