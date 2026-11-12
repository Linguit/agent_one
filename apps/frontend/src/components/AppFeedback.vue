<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { useFeedback } from '../feedback'

const feedback = useFeedback()
const labels = { success: '成功', info: '提示', error: '错误' }
let timer: ReturnType<typeof setTimeout> | undefined
watch(() => feedback.message, message => {
  clearTimeout(timer)
  if (message) timer = setTimeout(feedback.dismiss, 3000)
}, { immediate: true, flush: 'sync' })
onUnmounted(() => clearTimeout(timer))
</script>

<template>
  <div v-if="feedback.message" class="feedback" :data-kind="feedback.message.kind">
    <div :role="feedback.message.kind === 'error' ? 'alert' : 'status'">
      <strong>{{ labels[feedback.message.kind] }}</strong> {{ feedback.message.text }}
    </div>
    <button type="button" aria-label="关闭反馈" @click="feedback.dismiss"><X aria-hidden="true" /></button>
  </div>
</template>
