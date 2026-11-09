import { defineStore } from 'pinia'
import type { AuthLoginData, AuthRequest, AuthMeData } from '@super-ai/api-contracts'
import { config } from './config'

const KEY = 'super-ai.auth.token'
export const authClient = {
  async request<T>(path: string, init: RequestInit = {}) {
    const token = localStorage.getItem(KEY)
    const headers = new Headers(init.headers)
    headers.set('Content-Type', 'application/json')
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`${config.apiBaseUrl}${path}`, { ...init, headers })
    const envelope = await response.json() as { ok: boolean; data?: T; error?: { message: string } }
    if (!response.ok || !envelope.ok) throw new Error(envelope.error?.message ?? '请求失败')
    return envelope.data as T
  },
  async login(body: AuthRequest) { const data = await this.request<AuthLoginData>('/auth/login', { method: 'POST', body: JSON.stringify(body) }); localStorage.setItem(KEY, data.token); return data.user },
  async me() { return this.request<AuthMeData>('/auth/me') },
  async logout() { try { await this.request('/auth/logout', { method: 'POST' }) } finally { localStorage.removeItem(KEY) } },
  clear() { localStorage.removeItem(KEY) },
}
export const useAuthStore = defineStore('auth', { state: () => ({ user: null as AuthMeData | null, initialized: false }), actions: { async initialize() { try { this.user = await authClient.me() } catch { authClient.clear(); this.user = null } finally { this.initialized = true } }, async logout() { await authClient.logout(); this.user = null } } })
