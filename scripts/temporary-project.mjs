import assert from 'node:assert/strict'
import { cpSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')

export function temporaryProject(area) {
  assert.ok(['apps/frontend', 'docs'].includes(area))
  const cache = join(repositoryRoot, '.cache')
  mkdirSync(cache, { recursive: true })
  const root = mkdtempSync(join(cache, 'acceptance-'))
  const child = relative(cache, root)
  assert.ok(child && !child.startsWith('..') && !child.includes(sep))
  const source = join(repositoryRoot, area)
  cpSync(source, join(root, area), {
    recursive: true,
    filter: (path) => !relative(source, path).split(sep)
      .some((part) => ['node_modules', 'dist', 'cache', '.cache'].includes(part)),
  })
  writeFileSync(join(root, 'package.json'), JSON.stringify({
    private: true, type: 'module', workspaces: ['apps/frontend', 'docs'],
  }))
  symlinkSync(join(repositoryRoot, 'node_modules'), join(root, 'node_modules'), 'junction')
  mkdirSync(join(root, 'config'))
  writeFileSync(join(root, 'config/project.json'), JSON.stringify({
    frontend: { title: 'Super AI 工程基础', apiBaseUrl: '/api' },
    llm: { apiKey: 'PRIVATE_ACCEPTANCE_SENTINEL_P01' },
  }))
  writeFileSync(join(root, 'config/user.project.json'), '{}')
  return {
    root,
    cleanup() {
      // 绝对目标已检查为 repositoryRoot/.cache 的直接子目录。
      rmSync(root, { recursive: true, force: true })
    },
  }
}
