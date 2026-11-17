import { DOCUMENT_UPLOAD_POLICY } from '@super-ai/api-contracts'
import type { DocumentIndexTask, KnowledgeDocument } from '@super-ai/api-contracts'
import type { RequestOptions } from './transport'

type Request = <T>(path: string, options?: RequestOptions) => Promise<T>

export function documentPath(kb: string, document: string) {
  return `/knowledge-bases/${encodeURIComponent(kb)}/documents/${encodeURIComponent(document)}`
}

export async function uploadAndIndex(
  request: Request,
  kb: string,
  file: File,
  onUploaded: (document: KnowledgeDocument) => void,
  signal: AbortSignal,
) {
  const body = new FormData()
  const suffix = file.name.toLowerCase().match(/\.(md|pdf)$/)?.[0]
  const type = suffix === '.md' || suffix === '.pdf'
    ? DOCUMENT_UPLOAD_POLICY.mimeTypes[suffix][0]
    : file.type
  const normalized = file.type && file.type !== 'application/octet-stream'
    ? file : new File([file], file.name, { type })
  body.set('file', normalized)
  const document = await request<KnowledgeDocument>(
    `/knowledge-bases/${encodeURIComponent(kb)}/documents`,
    { method: 'POST', body, signal },
  )
  onUploaded(document)
  return request<DocumentIndexTask>(`${documentPath(kb, document.id)}/index-tasks`, {
    method: 'POST', signal,
  })
}
