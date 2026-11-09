import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import FoundationView from './FoundationView.vue'
import { config } from './config'
import './style.css'

document.title = config.title
const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', component: FoundationView }],
})
createApp(App).use(createPinia()).use(router).mount('#app')
