<script setup lang="ts">
import { CheckCircle2, Circle, Clock3, TriangleAlert } from 'lucide-vue-next'

const labels = { idle: '待处理', loading: '进行中', success: '已完成', error: '失败' }
const icons = { idle: Circle, loading: Clock3, success: CheckCircle2, error: TriangleAlert }
defineProps<{ state: keyof typeof labels; label?: string }>()
</script>

<template>
  <span class="status-badge" role="status" :data-state="state">
    <component :is="icons[state]" aria-hidden="true" /> {{ label || labels[state] }}
  </span>
</template>
