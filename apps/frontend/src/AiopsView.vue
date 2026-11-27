<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { ActiveAlert } from '@super-ai/api-contracts'
import { useAiopsStore } from './aiopsStore'
import { eventSummary, object, readable, reportHtml, statusLabels, summary, text } from './aiopsPresentation'

const store = useAiopsStore()
const query = ref('')
const alertName = ref('')
const report = computed(() => store.activeTask?.report)
function prefill(alert: ActiveAlert) {
  alertName.value = alert.alertname
  query.value = `请诊断告警「${alert.alertname}」${alert.service ? `，服务：${alert.service}` : ''}。${readable(alert.annotations.summary)}`
}
function submit() {
  void store.create({ query: query.value.trim(), alertNames: alertName.value ? [alertName.value] : [] })
}
onMounted(() => { void store.refresh(); void store.refreshAlerts() })
onUnmounted(store.reset)
</script>

<template>
  <section class="aiops-workspace" aria-label="AIOps 诊断控制台">
    <aside class="aiops-column aiops-input" aria-label="诊断输入与历史">
      <div class="aiops-heading"><span class="aiops-eyebrow">诊断工作台</span><h2>从问题开始</h2><p>以真实告警和已存证据追踪问题。</p></div>
      <form @submit.prevent="submit">
        <label for="diagnosis-query">诊断问题</label>
        <textarea id="diagnosis-query" v-model="query" required maxlength="8000" rows="5" placeholder="描述服务、现象和时间范围…" />
        <label for="diagnosis-alert">关联告警（可选）</label>
        <select id="diagnosis-alert" v-model="alertName"><option value="">不指定告警</option><option v-for="name in [...new Set(store.activeAlerts.map(a => a.alertname))]" :key="name">{{ name }}</option></select>
        <button class="primary-button" :disabled="store.busy || !query.trim()">{{ store.busy ? '诊断进行中…' : '创建诊断' }}</button>
      </form>
      <section><div class="aiops-section-heading"><h3>活跃告警 <small>{{ store.activeAlerts.length }}</small></h3><button @click="store.refreshAlerts">刷新告警</button></div>
        <p v-if="store.alertsError" role="alert" class="aiops-error">{{ store.alertsError }}</p>
        <p v-else-if="!store.activeAlerts.length" class="aiops-muted">当前没有活跃告警。</p>
        <button v-for="(alert, i) in store.activeAlerts" :key="alert.source + alert.alertname + i" class="aiops-card aiops-alert" :aria-pressed="alertName === alert.alertname" @click="prefill(alert)">
          <strong>{{ alert.alertname }}</strong><span>{{ alert.service || '未标注服务' }} · {{ alert.severity || '未标注级别' }} · {{ alert.status }}</span><small>来源 {{ alert.source }} · {{ alert.startsAt }}</small><span>{{ readable(alert.annotations.summary) }}</span>
        </button>
      </section>
      <section><div class="aiops-section-heading"><h3>诊断历史</h3><button @click="store.refresh">刷新状态</button></div>
        <p v-if="!store.history.length" class="aiops-muted">暂无持久诊断记录。</p>
        <button v-for="task in store.history" :key="task.id" class="aiops-card" :aria-current="store.activeTask?.id === task.id" @click="store.select(task.id)"><strong>{{ task.input.query }}</strong><span>{{ statusLabels[task.status] }} · {{ task.createdAt }}</span></button>
      </section>
      <RouterLink to="/mcp">管理 MCP 连接</RouterLink>
    </aside>
    <section class="aiops-center" aria-label="诊断报告与实时过程">
      <header class="aiops-task-header"><div><span class="aiops-eyebrow">当前诊断</span><h2>{{ store.activeTask?.input.query || '等待创建或选择诊断' }}</h2></div>
        <div v-if="store.activeTask" class="aiops-status-row"><span :data-status="store.activeTask.status">诊断：{{ statusLabels[store.activeTask.status] }}</span><span :data-status="store.activeTask.backgroundJob.status">后台任务：{{ statusLabels[store.activeTask.backgroundJob.status] }}</span><button v-if="store.cancellable" @click="store.cancel">取消后台任务</button><small v-if="store.activeTask.backgroundJob.cancelRequestedAt">取消已请求，等待服务器确认</small></div>
        <small>{{ store.connection }}</small><p v-if="store.activeTask?.backgroundJob.errorMessage" class="aiops-error">{{ readable(store.activeTask.backgroundJob.errorMessage) }}</p><p v-if="store.error" role="alert" class="aiops-error">{{ store.error }}</p>
      </header>
      <section class="aiops-report" aria-label="当前报告" tabindex="0">
        <div class="aiops-section-heading"><h3>诊断报告</h3><span v-if="report">{{ report.mode === 'fallback' ? '保守 fallback · 证据不足' : '基于持久证据' }}</span></div>
        <p v-if="!report" class="aiops-muted">报告尚未生成。可在下方查看真实执行过程与右侧证据。</p>
        <div v-else class="markdown" v-html="reportHtml(report.content)" />
      </section>
      <section class="aiops-timeline" aria-label="实时 timeline" role="log" tabindex="0"><h3>诊断过程</h3><p class="aiops-muted">Planner / Replanner 为执行阶段；任务状态以服务器记录为准。</p>
        <p v-if="!store.liveEvents.length && !store.evidenceChain?.checkpoints.length" class="aiops-muted">暂无过程记录。</p>
        <ol><li v-for="event in store.liveEvents" :key="event.id"><small>{{ event.timestamp }}</small><p>{{ eventSummary(event) }}</p></li></ol>
        <details v-if="store.evidenceChain?.checkpoints.length"><summary>持久计划与重规划</summary><article v-for="checkpoint in store.evidenceChain.checkpoints" :key="text(checkpoint.id)"><strong>计划 v{{ checkpoint.plan_version }} · {{ checkpoint.next_node }}</strong><p v-if="object(checkpoint.state).replanReason">调整原因：{{ readable(object(checkpoint.state).replanReason) }}</p><p v-for="(step, i) in (Array.isArray(object(object(checkpoint.state).plan).steps) ? object(object(checkpoint.state).plan).steps as unknown[] : [])" :key="i">{{ i + 1 }}. {{ readable(object(step).purpose) }} · {{ text(object(step).tool) }}</p></article></details>
      </section>
    </section>
    <aside class="aiops-column aiops-provenance" aria-label="证据执行链与案例库">
      <div class="aiops-heading"><span class="aiops-eyebrow">PROVENANCE</span><h2>证据与执行链</h2><p>保留来源、审计与结论的关联。</p></div>
      <section><h3>执行步骤</h3><p v-if="!store.evidenceChain?.steps.length" class="aiops-muted">暂无持久步骤。</p><article v-for="step in store.evidenceChain?.steps" :key="text(step.id)" class="aiops-card"><strong>{{ step.ordinal }} · {{ readable(step.purpose) }}</strong><span>{{ text(step.tool_name) }} · {{ statusLabels[text(step.status)] || text(step.status) }}</span><small>计划 v{{ step.plan_version }} · 审计 {{ step.audit_id || '未开始' }}</small><p v-if="step.error_code" class="aiops-error">{{ text(step.error_code) }}</p></article></section>
      <section><h3>工具审计</h3><details v-for="tool in store.evidenceChain?.toolCalls" :key="text(tool.id)" class="aiops-card"><summary>{{ text(tool.tool_name) }} · {{ tool.error_message ? '失败' : statusLabels[text(tool.status)] || text(tool.status) }}</summary><p>{{ summary(tool) }}</p><small>审计 {{ tool.id }} · {{ tool.duration_ms }} ms</small></details></section>
      <section><h3>证据来源</h3><p v-if="!store.evidenceChain?.evidence.length" class="aiops-muted">暂无已保存证据。</p><article v-for="evidence in store.evidenceChain?.evidence" :id="'evidence-' + text(evidence.id)" :key="text(evidence.id)" class="aiops-card"><strong>{{ text(evidence.kind) }} · {{ text(evidence.source) }}</strong><p>{{ summary(evidence.content) }}</p><small>证据 {{ evidence.id }}<br>步骤 {{ evidence.step_id || '初始输入' }}</small><p v-for="link in store.evidenceChain?.links.filter(l => l.evidence_id === evidence.id)" :key="text(link.id)">引用：{{ readable(link.claim) }}<small>报告 {{ link.report_id }}</small></p></article></section>
      <section><h3>案例库</h3><p v-if="!store.cases.length" class="aiops-muted">暂无已沉淀案例。</p><button v-for="item in store.cases" :key="item.id" class="aiops-card" @click="store.inspectCase(item.id)"><strong>{{ item.alertName || item.service || '查询诊断案例' }}</strong><span>{{ item.summary }}</span></button>
        <article v-if="store.selectedCase" class="aiops-card"><h4>{{ store.selectedCase.alertName || '诊断案例' }}</h4><dl><dt>服务</dt><dd>{{ store.selectedCase.service }}</dd><dt>摘要</dt><dd>{{ store.selectedCase.summary }}</dd><dt>根因</dt><dd>{{ store.selectedCase.rootCause }}</dd><dt>处理建议</dt><dd>{{ store.selectedCase.remediation }}</dd><dt>关键词</dt><dd>{{ store.selectedCase.keywords.join('、') }}</dd><dt>证据引用</dt><dd>{{ store.selectedCase.evidenceIds.join('、') }}</dd><dt>来源诊断</dt><dd>{{ store.selectedCase.taskId }}</dd><dt>报告</dt><dd>{{ store.selectedCase.reportId }}</dd></dl><RouterLink v-if="store.documentTarget" :to="store.documentTarget">打开知识文档</RouterLink></article>
      </section>
    </aside>
  </section>
</template>
