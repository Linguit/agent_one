import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import { createWebHistory } from 'vue-router'
import App from './App.vue'
import { config } from './config'
import { useAuthStore } from './auth'
import { createAppRouter } from './router'
import './style.css'

document.title = config.title
const pinia = createPinia()
const router = createAppRouter(pinia, createWebHistory())
const auth = useAuthStore(pinia)
watch(() => auth.authenticated, active => {
  const current = router.currentRoute.value
  if (!active && current.meta.requiresAuth) {
    void router.replace({ name: 'login', query: { redirect: current.fullPath } })
  }
})
createApp(App).use(pinia).use(router).mount('#app')
