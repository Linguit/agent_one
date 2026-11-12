<script setup lang="ts">
import { useAuthStore } from './auth'
import AppFeedback from './components/AppFeedback.vue'
import AppLoadingState from './components/AppLoadingState.vue'

const auth = useAuthStore()
</script>

<template>
  <AppLoadingState v-if="!auth.initialized" message="正在检查登录状态…" />
  <RouterView v-else />
  <AppFeedback />
</template>
