<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { workspaceRoutes } from './workspaceRoutes'
import AppEmptyState from './components/AppEmptyState.vue'

const route = useRoute()
const item = computed(() => workspaceRoutes.find(entry => entry.name === route.name))
</script>

<template>
  <div v-if="item" class="placeholder">
    <component :is="item.icon" class="placeholder-icon" aria-hidden="true" />
    <AppEmptyState title="功能待接入" :message="item.description" />
  </div>
</template>
