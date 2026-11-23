<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../chatStore'
const store = useChatStore()
const busy = ref(false)
const error = ref('')
async function run(action: () => Promise<void>) {
  if (busy.value || store.liveTurn) return
  busy.value = true; error.value = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '操作失败，请重试。' }
  finally { busy.value = false }
}
</script>
<template>
  <button :disabled="busy || !!store.liveTurn" @click="run(store.create)">＋ 新建会话</button>
  <p v-if="error" role="alert">{{ error }}</p>
  <ul class="chat-session-list">
    <li v-for="session in store.sessions" :key="session.id">
      <button :aria-current="store.active?.id === session.id ? 'true' : undefined"
        :disabled="busy || !!store.liveTurn" @click="run(() => store.select(session.id))">{{ session.title }}</button>
      <button :aria-label="`删除会话 ${session.title}`" :disabled="busy || !!store.liveTurn"
        @click="run(() => store.remove(session.id))">×</button>
    </li>
  </ul>
</template>
