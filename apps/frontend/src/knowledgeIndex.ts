import { DOCUMENT_UPLOAD_POLICY } from '@super-ai/api-contracts'
import type {
  ChunkingConfig, DocumentChunkPreview, DocumentIndexTask, KnowledgeBase, KnowledgeDocument,
} from '@super-ai/api-contracts'
import type { RequestOptions } from './transport'

type Request = <T>(path: string, options?: RequestOptions) => Promise<T>

function extension(file: File) {
  const name = file.name.toLowerCase()
  return name.endsWith('.md') ? '.md' : name.endsWith('.pdf') ? '.pdf' : null
}

export function uploadIssue(file: File): string {
  const suffix = extension(file)
  if (!suffix) return '仅支持 .md 和 .pdf 文件。'
  if (!file.size) return '文件为空。'
  if (file.size > DOCUMENT_UPLOAD_POLICY.maxBytes) return '文件大小不能超过 10 MiB。'
  const types: readonly string[] = DOCUMENT_UPLOAD_POLICY.mimeTypes[suffix]
  return file.type && file.type !== 'application/octet-stream' && !types.includes(file.type)
    ? '文件类型与扩展名不匹配。' : ''
}

export function knowledgeClient(request: Request) {
  const documents = (kb: string) => '/knowledge-bases/' + encodeURIComponent(kb) + '/documents'
  const document = (kb: string, id: string) => documents(kb) + '/' + encodeURIComponent(id)
  const task = (kb: string, id: string) => document(kb, id) + '/index-tasks'
  return {
    bases: (signal: AbortSignal) => request<KnowledgeBase[]>('/knowledge-bases', { signal }),
    list: (kb: string, signal: AbortSignal) =>
      request<KnowledgeDocument[]>(documents(kb), { signal }),
    detail: (kb: string, id: string, signal: AbortSignal) =>
      request<KnowledgeDocument>(document(kb, id), { signal }),
    preview: (kb: string, id: string, signal: AbortSignal) =>
      request<DocumentChunkPreview>(document(kb, id) + '/chunk-preview', { signal }),
    latestTask: (kb: string, id: string, signal: AbortSignal) =>
      request<DocumentIndexTask | null>(task(kb, id), { signal }),
    schedule: (kb: string, id: string, previous: DocumentIndexTask | null, signal: AbortSignal) =>
      request<DocumentIndexTask>(
        previous ? task(kb, id) + '/' + encodeURIComponent(previous.id) + ':retry' : task(kb, id),
        { method: 'POST', signal },
      ),
    remove: (kb: string, id: string, signal: AbortSignal) =>
      request<{ deleted: true }>(document(kb, id), { method: 'DELETE', signal }),
    upload(kb: string, file: File, config: ChunkingConfig, overwrite: boolean, signal: AbortSignal) {
      const suffix = extension(file)
      if (!suffix) throw new Error('仅支持 .md 和 .pdf 文件。')
      const mime = DOCUMENT_UPLOAD_POLICY.mimeTypes[suffix][0]
      const normalized = file.type && file.type !== 'application/octet-stream'
        ? file : new File([file], file.name, { type: mime })
      const body = new FormData()
      body.set('file', normalized)
      body.set('strategy', config.strategy)
      if (config.strategy === 'fixed-character') {
        body.set('maxCharacters', String(config.maxCharacters))
        body.set('overlap', String(config.overlap))
      }
      if (overwrite) body.set('overwrite', 'true')
      return request<KnowledgeDocument>(documents(kb), { method: 'POST', body, signal })
    },
  }
}
