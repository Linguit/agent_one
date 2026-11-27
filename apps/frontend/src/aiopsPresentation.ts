import type { SseEvent } from '@super-ai/api-contracts'
import { safeMarkdown } from './chatPresentation'

export const text = (value: unknown): string => typeof value === 'string' ? value : typeof value === 'number' ? String(value) : ''
export const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
export function readable(value: unknown): string {
  const source = text(value).trim()
  if (/^[{[]/.test(source)) return '结构化内容已保存，请查看来源与引用。'
  return source.slice(0, 4000)
}
export function summary(value: unknown): string {
  const data = object(value)
  return ['summary', 'message', 'text', 'content', 'description', 'alertname', 'title', 'result_summary', 'error_message']
    .map(key => readable(data[key])).filter(Boolean).join(' · ') || '结构化证据已保存，来源与关联见下方。'
}
export function reportHtml(value: unknown) {
  const source = text(value).replace(/```(?:json)?\s*\n[\s\S]*?```/gi, '证据详情请查看右侧证据链。')
    .split('\n').map(line => /^\s*[{[]/.test(line) ? '结构化内容请查看右侧证据链。' : line).join('\n')
  return safeMarkdown(source)
}
export const statusLabels: Record<string, string> = {
  accepted: '已受理', queued: '排队中', running: '执行中', succeeded: '已完成', failed: '失败', cancelled: '已取消',
  pending: '待执行', started: '已开始', completed: '已完成', skipped: '已跳过', delta: '输出中',
}
export function eventSummary(event: SseEvent) {
  switch (event.type) {
    case 'task.status': return readable(event.data.task.message)
    case 'reasoning.delta': return readable(event.data.text)
    case 'tool.call': return `${event.data.toolName ?? '工具'} · ${statusLabels[event.data.status] ?? event.data.status}`
    case 'reference.source': return `证据 · ${event.data.title} · ${event.data.evidenceId ?? ''}`
    case 'report': return '报告已保存'
    case 'error': return event.data.error.message
    case 'complete': return '执行流结束；状态以持久任务为准'
    default: return '诊断进度更新'
  }
}
