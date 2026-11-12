<script setup lang="ts">
defineProps<{ message?: string }>()
</script>

<template><div class="app-state error-state" role="alert">{{ message || '加载失败，请重试。' }}</div></template>
