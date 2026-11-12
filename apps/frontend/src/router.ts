import { createRouter, type RouterHistory } from 'vue-router'
import type { Pinia } from 'pinia'
import { useAuthStore } from './auth'
import { workspaceRoutes } from './workspaceRoutes'
import WorkspaceLayout from './WorkspaceLayout.vue'
import WorkspacePlaceholder from './WorkspacePlaceholder.vue'
import AuthView from './AuthView.vue'

export function createAppRouter(pinia: Pinia, history: RouterHistory) {
  const auth = useAuthStore(pinia)
  const router = createRouter({
    history,
    routes: [
      { path: '/login', name: 'login', component: AuthView, meta: { publicOnly: true } },
      { path: '/register', name: 'register', component: AuthView, meta: { publicOnly: true } },
      {
        path: '/', component: WorkspaceLayout, meta: { requiresAuth: true }, redirect: '/chat',
        children: workspaceRoutes.map(({ path, name }) => ({ path, name, component: WorkspacePlaceholder })),
      },
      { path: '/:pathMatch(.*)*', redirect: '/chat' },
    ],
  })
  let initialization: Promise<void> | undefined
  router.beforeEach(async to => {
    await (initialization ??= auth.initialize())
    if (to.meta.requiresAuth && !auth.authenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (to.meta.publicOnly && auth.authenticated) return '/chat'
  })
  return router
}

export function workspaceRedirect(value: unknown): string {
  if (typeof value !== 'string') return '/chat'
  const path = value.split(/[?#]/, 1)[0]
  return workspaceRoutes.some(route => route.path === path) ? value : '/chat'
}
