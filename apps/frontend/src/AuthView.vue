<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Layers3 } from 'lucide-vue-next'
import { useAuthStore } from './auth'
import { config } from './config'
import { useFeedback } from './feedback'
import { workspaceRedirect } from './router'
import AppErrorState from './components/AppErrorState.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const feedback = useFeedback()
const registering = computed(() => route.name === 'register')
const email = ref('')
const password = ref('')
const pending = ref(false)
const error = ref('')
watch(registering, () => { error.value = ''; password.value = '' })

async function submit() {
  if (pending.value) return
  pending.value = true
  error.value = ''
  const body = { email: email.value.trim(), password: password.value }
  try {
    if (registering.value) {
      await auth.register(body)
      feedback.show('success', '注册成功，请登录。')
      await router.replace({ name: 'login', query: route.query })
    } else {
      await auth.login(body)
      await router.replace(workspaceRedirect(route.query.redirect))
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '请求失败，请重试。'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card" aria-labelledby="auth-title">
      <div class="brand"><Layers3 aria-hidden="true" /> {{ config.title }}</div>
      <h1 id="auth-title">{{ registering ? '创建账号' : '登录工作台' }}</h1>
      <form @submit.prevent="submit" :aria-busy="pending">
        <label>邮箱<input v-model="email" type="email" autocomplete="email" required :disabled="pending"></label>
        <label>密码<input v-model="password" type="password"
          :autocomplete="registering ? 'new-password' : 'current-password'" required :disabled="pending"></label>
        <AppErrorState v-if="error" :message="error" />
        <button class="primary-button" :disabled="pending">
          {{ pending ? '正在提交…' : registering ? '注册' : '登录' }}
        </button>
      </form>
      <RouterLink :to="{ name: registering ? 'login' : 'register', query: route.query }">
        {{ registering ? '已有账号？登录' : '没有账号？注册' }}
      </RouterLink>
    </section>
  </main>
</template>
