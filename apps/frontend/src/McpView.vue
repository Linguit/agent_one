<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import type { McpConnection, McpConnectionInput } from '@super-ai/api-contracts'
import { useMcpStore } from './mcpStore'
import { useAuthStore } from './auth'

const store = useMcpStore()
const auth = useAuthStore()
const defaults = (): McpConnectionInput => ({
  name: '', url: '', transport: 'sse', enabled: true, timeoutSeconds: 30, retries: 0,
})
const form = reactive(defaults())
const editing = ref<string | undefined>()
const notice = ref('')
function reset() { Object.assign(form, defaults()); editing.value = undefined; notice.value = '' }
function edit(row: McpConnection) {
  Object.assign(form, {
    name: row.name, url: row.url, transport: row.transport, enabled: row.enabled,
    timeoutSeconds: row.timeoutSeconds, retries: row.retries,
  })
  editing.value = row.id
  notice.value = ''
}
async function run(action: () => Promise<void>) {
  notice.value = ''
  try { await action() } catch { /* store exposes a safe error message */ }
}
async function submit() {
  await run(async () => { await store.save(form, editing.value); reset(); notice.value = '连接已保存。' })
}
watch(() => auth.user?.id, reset, { flush: 'sync' })
onMounted(() => { void run(store.refresh) })
</script>

<template>
  <section class="mcp-page" aria-labelledby="mcp-title">
    <header class="mcp-heading"><h2 id="mcp-title">MCP 连接管理</h2>
      <button :disabled="store.busy" @click="run(store.refresh)">刷新连接</button>
    </header>
    <p>管理自己的真实 MCP Servers，供对话和后续 AIOps 使用。</p>
    <p class="mcp-warning">完整 URL（包括 query）会持久化并返回。禁止把 token/secret 放进 URL query。当前不支持自定义 headers。</p>
    <p v-if="store.error" role="alert">{{ store.error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <div class="mcp-columns">
      <form class="mcp-editor" @submit.prevent="submit">
        <h2>{{ editing ? '编辑连接' : '新增连接' }}</h2>
        <label>名称<input v-model="form.name" required maxlength="100" /></label>
        <label>传输方式<select v-model="form.transport"><option value="sse">SSE</option><option value="streamable_http">Streamable HTTP</option></select></label>
        <label>服务器 URL<input v-model="form.url" type="url" required maxlength="4096" placeholder="http://127.0.0.1:端口/sse" /></label>
        <label>超时（秒）<input v-model.number="form.timeoutSeconds" type="number" min="1" max="300" step="1" required /></label>
        <label>发现重试次数<input v-model.number="form.retries" type="number" min="0" max="5" step="1" required /></label>
        <label><input v-model="form.enabled" type="checkbox" />启用连接</label>
        <p>重试仅用于发现；工具调用失败后不会自动重试。</p>
        <div class="mcp-actions"><button :disabled="store.busy" type="submit">保存连接</button><button type="button" :disabled="store.busy" @click="reset">取消编辑</button></div>
      </form>
      <section class="mcp-list" aria-label="连接列表" :aria-busy="store.busy">
        <h2>连接列表</h2>
        <p v-if="!store.connections.length">暂无连接。添加真实服务器后检查以发现工具。</p>
        <article v-for="row in store.connections" :key="row.id" class="mcp-card">
          <h3>{{ row.name }}</h3>
          <p>{{ row.transport === 'sse' ? 'SSE' : 'Streamable HTTP' }} · {{ row.enabled ? '已启用' : '已禁用' }}</p>
          <p class="mcp-url">{{ row.url }}</p>
          <p>超时 {{ row.timeoutSeconds }} 秒 · 发现重试 {{ row.retries }} 次</p>
          <p>检查：{{ row.lastCheck ? new Date(row.lastCheck).toLocaleString() : '尚未检查' }}</p>
          <p v-if="row.lastError" role="status">检查失败：{{ row.lastError }}</p>
          <p v-else-if="row.lastCheck">发现 {{ row.discoveredTools.length }} 个工具</p>
          <div class="mcp-actions">
            <button :disabled="store.busy" @click="edit(row)">编辑</button>
            <button :disabled="store.busy" @click="run(() => store.toggle(row))">{{ row.enabled ? '禁用' : '启用' }}</button>
            <button :disabled="store.busy" @click="run(() => store.check(row.id))">检查连接</button>
            <button :disabled="store.busy" @click="run(() => store.remove(row.id))">删除</button>
          </div>
          <details v-if="row.discoveredTools.length"><summary>已发现工具</summary>
            <div v-for="item in row.discoveredTools" :key="item.name"><h4>{{ item.name }}</h4><p>{{ item.description }}</p><pre>{{ JSON.stringify(item.inputSchema, null, 2) }}</pre></div>
          </details>
        </article>
      </section>
    </div>
  </section>
</template>

<style scoped>
.mcp-page { height: 100%; overflow: auto; padding: 24px; box-sizing: border-box; min-height: 0; }
.mcp-heading, .mcp-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.mcp-heading { justify-content: space-between; }
.mcp-columns { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 24px; }
.mcp-editor, .mcp-card { border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.mcp-editor { align-self: start; display: grid; gap: 12px; }
label { display: grid; gap: 6px; }
input, select { max-width: 100%; min-width: 0; box-sizing: border-box; padding: 8px; }
input[type="checkbox"] { justify-self: start; }
.mcp-warning { padding: 12px; background: #fff7df; color: #5e4300; border-radius: 6px; }
.mcp-list, .mcp-card { min-width: 0; }
.mcp-url, p, h3, h4 { overflow-wrap: anywhere; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; }
button { padding: 8px 12px; cursor: pointer; }
@media (max-width: 900px) { .mcp-columns { grid-template-columns: 1fr; } }
</style>
