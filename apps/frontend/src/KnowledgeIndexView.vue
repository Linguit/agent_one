<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { DOCUMENT_CHUNKING_DEFAULTS } from '@super-ai/api-contracts'
import type { ChunkingConfig, DocumentIndexStatus } from '@super-ai/api-contracts'
import { uploadIssue } from './knowledgeIndex'
import { activeIndex, useKnowledgeStore } from './knowledgeStore'

const store = useKnowledgeStore()
const route = useRoute()
const file = ref<File>()
const input = ref<HTMLInputElement>()
const strategy = ref<ChunkingConfig['strategy']>('fixed-character')
const maxCharacters = ref<number>(DOCUMENT_CHUNKING_DEFAULTS.maxCharacters)
const overlap = ref<number>(DOCUMENT_CHUNKING_DEFAULTS.overlap)
const issue = computed(() => file.value ? uploadIssue(file.value) : '')
const labels: Record<DocumentIndexStatus, string> = {
  pending: '等待索引', running: '索引中', succeeded: '索引完成', failed: '索引失败', cancelled: '已取消',
}
const strategies: Record<ChunkingConfig['strategy'], string> = {
  'fixed-character': '固定字符', 'markdown-heading': 'Markdown 标题', paragraph: '段落',
}

async function upload() {
  if (!file.value || issue.value) return
  const config: ChunkingConfig = strategy.value === 'fixed-character'
    ? { strategy: strategy.value, maxCharacters: maxCharacters.value, overlap: overlap.value }
    : { strategy: strategy.value }
  await store.upload(file.value, config)
  if (!store.error && !store.overwrite) clearFile()
}

function clearFile() {
  file.value = undefined
  if (input.value) input.value.value = ''
}

async function confirmOverwrite() {
  await store.confirmOverwrite()
  if (!store.error && !store.overwrite) clearFile()
}

onMounted(async () => {
  await store.load()
  if (typeof route.query.kb === 'string') await store.choose(route.query.kb)
  if (typeof route.query.document === 'string') await store.inspect(route.query.document)
})
onUnmounted(store.reset)
</script>

<template>
  <section class="knowledge-view" aria-label="知识库工作区">
    <label v-if="store.knowledgeBases.length > 1">
      知识库
      <select :value="store.kb" :disabled="store.busy"
        @change="store.choose(($event.target as HTMLSelectElement).value)">
        <option v-for="base in store.knowledgeBases" :key="base.id" :value="base.id">{{ base.name }}</option>
      </select>
    </label>
    <form class="upload-form" aria-label="上传文档" @submit.prevent="upload">
      <label>文档 <input ref="input" type="file" accept=".md,.pdf" :disabled="store.busy"
        @change="file = ($event.target as HTMLInputElement).files?.[0]" /></label>
      <label>分块策略
        <select v-model="strategy" :disabled="store.busy">
          <option v-for="(label, value) in strategies" :key="value" :value="value">{{ label }}</option>
        </select>
      </label>
      <template v-if="strategy === 'fixed-character'">
        <label>块长度 <input v-model.number="maxCharacters" required min="1" type="number" /></label>
        <label>重叠字符 <input v-model.number="overlap" required min="0" :max="maxCharacters - 1" type="number" /></label>
      </template>
      <button :disabled="!store.kb || !file || !!issue || store.busy || !!store.overwrite">上传并索引</button>
    </form>
    <p v-if="issue" role="alert">{{ issue }}</p>
    <div v-if="store.overwrite" role="group" aria-label="覆盖确认" class="confirmation">
      <p role="alert">「{{ store.overwrite.file.name }}」与已有文档的内容摘要相同。覆盖将替换原文档并重新索引。</p>
      <button type="button" :disabled="store.busy" @click="confirmOverwrite">确认覆盖</button>
      <button type="button" @click="store.overwrite = null">保留原文档</button>
    </div>
    <div v-if="store.deletion" role="group" aria-label="删除确认" class="confirmation">
      <p>确定删除「{{ store.deletion.filename }}」及其索引吗？</p>
      <button type="button" :disabled="store.busy" @click="store.confirmDelete">确认删除</button>
      <button type="button" @click="store.deletion = null">保留文档</button>
    </div>
    <p v-if="store.error" role="alert">{{ store.error }}</p>
    <header class="document-header">
      <h2>文档</h2>
      <button type="button" :disabled="store.busy" @click="store.load">刷新状态</button>
    </header>
    <p v-if="store.busy && !store.documents.length" role="status">正在加载知识库或处理文档…</p>
    <p v-else-if="!store.documents.length && !store.error">{{ store.kb ? '暂无文档' : '暂无可用知识库' }}</p>
    <ul v-else class="document-list" aria-label="文档列表" tabindex="0">
      <li v-for="doc in store.documents" :key="doc.id">
        <div class="document-row">
          <strong>{{ doc.filename }}</strong>
          <span role="status">{{ store.tasks[doc.id] ? labels[store.tasks[doc.id]!.status] : '未提交索引' }}</span>
          <span v-if="store.tasks[doc.id]?.failureReason">失败原因：{{ store.tasks[doc.id]?.failureReason }}</span>
          <button type="button" :aria-expanded="store.selected === doc.id" @click="store.inspect(doc.id)">
            {{ store.selected === doc.id ? '收起详情' : '查看详情' }}
          </button>
          <button v-if="!activeIndex(store.tasks[doc.id])" type="button" :disabled="store.busy"
            @click="store.index(doc.id)">
            {{ store.tasks[doc.id]?.status === 'succeeded' ? '重建索引' : store.tasks[doc.id] ? '重试' : '开始索引' }}
          </button>
          <button type="button" :disabled="store.busy" @click="store.deletion = doc">删除</button>
        </div>
        <div v-if="store.selected === doc.id" class="document-details">
          <p v-if="store.detailLoading" role="status">正在加载详情和分块预览…</p>
          <p v-if="store.detailError" role="alert">{{ store.detailError }}</p>
          <section v-if="store.detail" class="metadata-scroll" aria-label="文档元数据" tabindex="0">
            <h3>文档元数据</h3>
            <dl>
              <dt>文件类型</dt><dd>{{ store.detail.mimeType }}</dd>
              <dt>文件大小</dt><dd>{{ store.detail.size }} 字节</dd>
              <dt>上传时间</dt><dd>{{ store.detail.uploadedAt }}</dd>
              <dt>内容摘要</dt><dd>{{ store.detail.sha256 }}</dd>
              <dt>分块策略</dt><dd>{{ strategies[store.detail.chunking.strategy] }}</dd>
              <template v-if="store.detail.chunking.strategy === 'fixed-character'">
                <dt>块长度</dt><dd>{{ store.detail.chunking.maxCharacters }}</dd>
                <dt>重叠字符</dt><dd>{{ store.detail.chunking.overlap }}</dd>
              </template>
            </dl>
          </section>
          <section v-if="store.preview" class="preview-scroll" aria-label="分块预览" tabindex="0">
            <h3>分块预览</h3>
            <p v-if="!store.preview.chunks.length">暂无分块</p>
            <table v-else>
              <thead><tr><th scope="col">序号</th><th scope="col">起点</th><th scope="col">终点</th><th scope="col">文本摘录</th></tr></thead>
              <tbody>
                <tr v-for="chunk in store.preview.chunks" :key="chunk.index">
                  <td>{{ chunk.index }}</td><td>{{ chunk.start }}</td><td>{{ chunk.end }}</td><td>{{ chunk.excerpt }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.knowledge-view { display: grid; gap: 0.75rem; min-width: 0; }
.upload-form, .document-row, .document-header {
  display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;
}
.upload-form input[type="number"] { width: 6rem; }
.document-header { justify-content: space-between; }
.document-header h2, h3, p { margin: 0; }
.document-list {
  max-block-size: min(55vh, 36rem); overflow: auto; min-width: 0;
  margin: 0; padding: 0; list-style: none;
}
.document-list li, .confirmation {
  padding: 0.75rem; border: 1px solid #8091a350; overflow-wrap: anywhere;
}
.document-row strong { flex: 1 1 12rem; min-width: 0; }
.document-details { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0.75rem; margin-top: 0.75rem; }
.metadata-scroll, .preview-scroll { max-block-size: 12rem; min-width: 0; overflow: auto; padding: 0.625rem; }
dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.25rem 0.75rem; }
dd { margin: 0; overflow-wrap: anywhere; }
table { width: 100%; min-width: 34rem; border-collapse: collapse; }
th, td { text-align: left; padding: 0.35rem 0.625rem; border-bottom: 1px solid #8091a350; }
td:last-child { white-space: pre-wrap; overflow-wrap: anywhere; }
.confirmation button { margin: 0.5rem 0.5rem 0 0; }
</style>
