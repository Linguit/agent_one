import { expect, it } from 'vitest'
import { DIAGNOSTIC_CASE_PATHS, type DiagnosticCase, type SavedDiagnosisKnowledge } from '../src'

it('案例与 legacy 保存保持独立契约，允许空证据', () => {
  const value: DiagnosticCase = {
    id: 'case', ownerUserId: 'owner', taskId: 'task', reportId: 'report',
    documentId: 'document', indexTaskId: 'index', alertName: '', service: '',
    keywords: [], rootCause: '无法确认', remediation: '人工核验', summary: '证据不足',
    evidenceIds: [], createdAt: '',
  }
  const saved: SavedDiagnosisKnowledge = { documentId: 'doc', indexTaskId: 'index', knowledgeBaseId: 'kb' }
  expect(value.evidenceIds).toEqual([])
  expect(saved).not.toHaveProperty('caseId')
  expect(DIAGNOSTIC_CASE_PATHS).toContain('/aiops/diagnostics/{id}:save-to-knowledge')
})
