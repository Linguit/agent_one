<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Layers3, LogOut, UserRound } from 'lucide-vue-next'
import type { HealthResponse } from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { config } from './config'
import { useFeedback } from './feedback'
import { apiClient } from './transport'
import { workspaceRoutes } from './workspaceRoutes'
import AsyncStatusBadge from './components/AsyncStatusBadge.vue'

const auth = useAuthStore()
const route = useRoute()
const feedback = useFeedback()
const current = computed(() => workspaceRoutes.find(item => item.name === route.name))
const signingOut = ref(false)
const service = ref<'loading' | 'success' | 'error'>('loading')
const controller = new AbortController()
onMounted(async () => {
  try {
    await apiClient<HealthResponse>(config.apiBaseUrl.replace(/\/$/, '') + '/health', {
      signal: controller.signal,
    })
    service.value = 'success'
  } catch {
    if (!controller.signal.aborted) service.value = 'error'
  }
})
onUnmounted(() => controller.abort())

async function logout() {
  signingOut.value = true
  try {
    await auth.logout()
    feedback.show('success', '已退出登录。')
  } catch (reason) {
    if (auth.authenticated) {
      feedback.show('error', reason instanceof Error ? reason.message : '退出失败，请重试。')
    }
  } finally {
    signingOut.value = false
  }
}
</script>

<template>
  <div class="workspace">
    <aside class="rail" aria-label="工作台侧栏">
      <div class="brand"><Layers3 aria-hidden="true" /> <span>{{ config.title }}</span></div>
      <nav aria-label="业务导航">
        <RouterLink v-for="item in workspaceRoutes" :key="item.name" :to="{ name: item.name }">
          <component :is="item.icon" aria-hidden="true" /> {{ item.title }}
        </RouterLink>
      </nav>
      <section v-if="route.name === 'chat'" class="sessions" aria-label="会话">
        <h2>会话</h2>
        <slot name="sessions"><p>会话列表待接入</p></slot>
      </section>
      <div class="account">
        <div class="account-email"><UserRound aria-hidden="true" /> <span>{{ auth.user?.email }}</span></div>
        <button :disabled="signingOut" @click="logout">
          <LogOut aria-hidden="true" /> {{ signingOut ? '正在退出…' : '退出登录' }}
        </button>
      </div>
    </aside>
    <div class="workspace-main">
      <header class="workspace-bar">
        <h1 id="workspace-title">{{ current?.title }}</h1>
        <AsyncStatusBadge :state="service"
          :label="service === 'success' ? '服务可用' : service === 'error' ? '服务不可用' : '正在检查服务'" />
      </header>
      <main class="workspace-canvas" aria-labelledby="workspace-title"><RouterView /></main>
    </div>
  </div>
</template>
