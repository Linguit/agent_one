import { Marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatReference } from '@super-ai/api-contracts'

const markdown = new Marked({ renderer: { html: () => '' } })
export function safeMarkdown(text: string) {
  return DOMPurify.sanitize(markdown.parse(text, { async: false }), {
    USE_PROFILES: { html: true }, FORBID_TAGS: ['img', 'style', 'input', 'form'],
  })
}

export function rankedReferences(items: unknown): ChatReference[] {
  if (!Array.isArray(items)) return []
  return items.filter((item): item is ChatReference => !!item && typeof item === 'object'
    && typeof item.title === 'string' && typeof item.uri === 'string')
    .sort((a, b) => (a.rerankRank ?? Infinity) - (b.rerankRank ?? Infinity)
      || (b.score ?? -Infinity) - (a.score ?? -Infinity)).slice(0, 5)
}

export function stage(rank: unknown, score: unknown) {
  return typeof score !== 'number' ? '未命中'
    : `${typeof rank === 'number' ? `排名 ${rank} · ` : ''}分数 ${score.toFixed(5)}`
}
