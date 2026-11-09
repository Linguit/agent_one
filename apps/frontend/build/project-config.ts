import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { PublicConfig } from '../src/public-config'

type JsonObject = Record<string, unknown>

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function readObject(path: string): JsonObject {
  let value: unknown
  try { value = JSON.parse(readFileSync(path, 'utf8')) }
  catch { throw new Error('无法读取合法 JSON 配置文件') }
  if (!isObject(value)) throw new Error('配置根节点必须为对象')
  return value
}

export function deepMerge(base: JsonObject, override: JsonObject): JsonObject {
  const result: JsonObject = structuredClone(base)
  for (const [key, value] of Object.entries(override)) {
    const previous = result[key]
    // 数据对象使用自有属性定义，__proto__ 不得改变原型。
    Object.defineProperty(result, key, {
      value: isObject(previous) && isObject(value) ? deepMerge(previous, value) : structuredClone(value),
      enumerable: true, configurable: true, writable: true,
    })
  }
  return result
}

export function projectPublicConfig(config: JsonObject): PublicConfig {
  const frontend = config['frontend']
  if (!isObject(frontend)
    || typeof frontend['title'] !== 'string'
    || typeof frontend['apiBaseUrl'] !== 'string') {
    throw new Error('frontend.title 与 frontend.apiBaseUrl 必须是字符串')
  }
  const result: PublicConfig = { title: frontend['title'], apiBaseUrl: frontend['apiBaseUrl'] }
  const analytics = config['analytics']
  if (isObject(analytics) && analytics['public'] === true) {
    if (typeof analytics['key'] !== 'string') throw new Error('公开 analytics.key 必须是字符串')
    result.analyticsKey = analytics['key']
  }
  return result
}

export function loadPublicConfig(directory: string): PublicConfig {
  const base = readObject(join(directory, 'project.json'))
  const userPath = join(directory, 'user.project.json')
  return projectPublicConfig(deepMerge(base, existsSync(userPath) ? readObject(userPath) : {}))
}
