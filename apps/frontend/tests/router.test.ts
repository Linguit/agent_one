import { createPinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '../src/auth'
import { useProtectedCleanup, useProtectedData } from '../src/protectedData'
import { createAppRouter, workspaceRedirect } from '../src/router'

const key = 'super-ai.auth.token'
const user = { id: '1', email: 'test@example.com' }
const success = (data: unknown) => Response.json({ ok: true, data })

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

it('保护路径并保存完整返回地址，只初始化一次', async () => {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  const initialize = vi.spyOn(auth, 'initialize')
  const router = createAppRouter(pinia, createMemoryHistory())
  await router.push('/knowledge?filter=a#list')
  expect(router.currentRoute.value.name).toBe('login')
  expect(router.currentRoute.value.query.redirect).toBe('/knowledge?filter=a#list')
  await router.push('/register')
  expect(router.currentRoute.value.name).toBe('register')
  await router.push('/unknown')
  expect(router.currentRoute.value.query.redirect).toBe('/chat')
  expect(initialize).toHaveBeenCalledTimes(1)
  expect(workspaceRedirect('/knowledge?filter=a#list')).toBe('/knowledge?filter=a#list')
  expect(workspaceRedirect('//example.com/chat')).toBe('/chat')
})

it('恢复会话并拦截登录和注册页，成功登出后清理状态', async () => {
  localStorage.setItem(key, 'session')
  const fetcher = vi.fn()
    .mockResolvedValueOnce(success(user))
    .mockResolvedValueOnce(success({ loggedOut: true }))
  vi.stubGlobal('fetch', fetcher)
  const pinia = createPinia()
  const router = createAppRouter(pinia, createMemoryHistory())
  await router.push('/register')
  expect(router.currentRoute.value.path).toBe('/chat')
  await router.push('/login')
  expect(router.currentRoute.value.path).toBe('/chat')
  const auth = useAuthStore(pinia)
  expect(auth.user).toEqual(user)
  expect(fetcher.mock.calls[0]?.[0]).toMatch(/\/auth\/me$/)
  expect(fetcher.mock.calls[0]?.[1].headers.get('Authorization')).toBe('Bearer session')
  const data = useProtectedData(pinia)
  data.chat.history = ['secret']
  const cleanup = vi.fn()
  useProtectedCleanup(pinia).register(cleanup)
  await auth.logout()
  expect(fetcher.mock.calls[1]?.[0]).toMatch(/\/auth\/logout$/)
  expect(fetcher.mock.calls[1]?.[1].method).toBe('POST')
  expect(auth.user).toBeNull()
  expect(data.chat).toEqual({})
  expect(cleanup).toHaveBeenCalledOnce()
  expect(localStorage.getItem(key)).toBeNull()
})

it('401 清理当前会话及注册状态', async () => {
  localStorage.setItem(key, 'session')
  vi.stubGlobal('fetch', vi.fn()
    .mockResolvedValueOnce(success(user))
    .mockResolvedValueOnce(new Response(null, { status: 401 })))
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  await auth.initialize()
  const data = useProtectedData(pinia)
  data.knowledge.documents = ['secret']
  const registry = useProtectedCleanup(pinia)
  const removed = vi.fn()
  registry.register(removed)()
  await expect(auth.request('/knowledge')).rejects.toMatchObject({ status: 401 })
  expect(auth.authenticated).toBe(false)
  expect(data.knowledge).toEqual({})
  expect(localStorage.getItem(key)).toBeNull()
  expect(removed).not.toHaveBeenCalled()
})
