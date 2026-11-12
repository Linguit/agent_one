<script setup lang="ts">
defineProps<{ message?: string }>()
</script>

<template><div class="app-state" role="status">{{ message || '正在加载…' }}</div></template>
