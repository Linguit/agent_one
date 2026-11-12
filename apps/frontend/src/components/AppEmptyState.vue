<script setup lang="ts">
defineProps<{ title?: string; message?: string }>()
</script>

<template>
  <div class="app-state" role="status">
    <h2>{{ title || '暂无内容' }}</h2>
    <p v-if="message">{{ message }}</p>
  </div>
</template>
