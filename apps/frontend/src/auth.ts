import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { AuthLoginData, AuthRequest, AuthMeData } from '@super-ai/api-contracts'
import { config } from './config'
import { useProtectedCleanup, useProtectedData } from './protectedData'
import { apiClient, sseClient } from './transport'
import type { RequestOptions } from './transport'

const key = 'super-ai.auth.token'
const base = config.apiBaseUrl.replace(/\/$/, '')
const post = (body?: AuthRequest): RequestInit => body
  ? { method: 'POST', body: JSON.stringify(body) }
  : { method: 'POST' }

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthMeData | null>(null)
  const initialized = ref(false)
  const authenticated = computed(() => user.value !== null)
  const cleanup = useProtectedCleanup()
  const data = useProtectedData()
  cleanup.register(() => data.$reset())

  function clear() {
    localStorage.removeItem(key)
    user.value = null
    cleanup.clear()
  }

  function sessionOptions(options: RequestOptions): RequestOptions {
    const bearer = localStorage.getItem(key)
    return bearer ? {
      ...options,
      bearer,
      onUnauthorized: () => {
        if (localStorage.getItem(key) === bearer) clear()
      },
    } : options
  }

  function request<T>(path: string, options: RequestOptions = {}) {
    return apiClient<T>(base + path, sessionOptions(options))
  }

  function stream(path: string, options: RequestOptions = {}) {
    return sseClient(base + path, sessionOptions(options))
  }

  async function initialize() {
    const token = localStorage.getItem(key)
    try {
      if (token) {
        const restored = await request<AuthMeData>('/auth/me')
        if (localStorage.getItem(key) === token) user.value = restored
      }
    } catch {
      if (localStorage.getItem(key) === token) clear()
    } finally {
      initialized.value = true
    }
  }

  async function login(body: AuthRequest) {
    const result = await apiClient<AuthLoginData>(base + '/auth/login', post(body))
    localStorage.setItem(key, result.token)
    user.value = result.user
  }

  function register(body: AuthRequest) {
    return apiClient<AuthMeData>(base + '/auth/register', post(body))
  }

  async function logout() {
    const token = localStorage.getItem(key)
    await request<{ loggedOut: boolean }>('/auth/logout', post())
    if (localStorage.getItem(key) === token) clear()
  }

  return { user, initialized, authenticated, initialize, login, register, logout, request, stream }
})
