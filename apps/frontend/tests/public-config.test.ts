import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { deepMerge, loadPublicConfig, projectPublicConfig } from '../build/project-config'

describe('公开配置边界', () => {
  it('对象递归，数组和 null 替换，且不修改输入或污染原型', () => {
    const base = { nested: { keep: 1, replace: 2 }, items: [1], value: 1 }
    const before = JSON.stringify(base)
    expect(deepMerge(base, { nested: { replace: 3 }, items: [2], value: null }))
      .toEqual({ nested: { keep: 1, replace: 3 }, items: [2], value: null })
    expect(JSON.stringify(base)).toBe(before)
    const malicious: Record<string, unknown> = JSON.parse('{"__proto__":{"polluted":true}}')
    deepMerge({}, malicious)
    expect({}).not.toHaveProperty('polluted')
  })
  it('逐项投影且要求 public 严格为 true', () => {
    const input = {
      frontend: { title: '基础', apiBaseUrl: '/api', secret: 'PRIVATE' },
      analytics: { public: true, key: 'PUBLIC', secret: 'PRIVATE' },
      llm: { key: 'PRIVATE' }, cls: { secret: 'PRIVATE' },
      mcp: { password: 'PRIVATE' }, minio: { secret: 'PRIVATE' },
    }
    expect(projectPublicConfig(input)).toEqual({
      title: '基础', apiBaseUrl: '/api', analyticsKey: 'PUBLIC',
    })
    expect(projectPublicConfig({ ...input, analytics: { public: false, key: 'PRIVATE' } }))
      .toEqual({ title: '基础', apiBaseUrl: '/api' })
    expect(projectPublicConfig({ ...input, analytics: { public: 'true', key: 'PRIVATE' } }))
      .not.toHaveProperty('analyticsKey')
  })

  it('拒绝不符合公开字段类型的配置', () => {
    expect(() => projectPublicConfig({ frontend: { title: 123, apiBaseUrl: '/' } })).toThrow()
    expect(() => projectPublicConfig({ frontend: { title: 'a', apiBaseUrl: {} } })).toThrow()
  })

  it('从临时双文件递归合并，用户文件可缺省', () => {
    const dir = mkdtempSync(join(tmpdir(), 'foundation-config-'))
    try {
      expect(() => loadPublicConfig(dir)).toThrow()
      writeFileSync(join(dir, 'project.json'), JSON.stringify({
        frontend: { title: 'base', apiBaseUrl: '/api' },
        analytics: { public: true, key: 'base-key' },
      }))
      expect(loadPublicConfig(dir).title).toBe('base')
      writeFileSync(join(dir, 'user.project.json'), JSON.stringify({
        frontend: { title: 'user' }, analytics: { key: 'user-key' },
      }))
      expect(loadPublicConfig(dir)).toEqual({ title: 'user', apiBaseUrl: '/api', analyticsKey: 'user-key' })
      writeFileSync(join(dir, 'user.project.json'), '[]')
      expect(() => loadPublicConfig(dir)).toThrow()
      writeFileSync(join(dir, 'user.project.json'), '{bad')
      expect(() => loadPublicConfig(dir)).toThrow()
    } finally { rmSync(dir, { recursive: true, force: true }) }
  })
})
