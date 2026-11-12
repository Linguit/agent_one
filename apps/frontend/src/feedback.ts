import { defineStore } from 'pinia'
import { shallowRef } from 'vue'

export const useFeedback = defineStore('feedback', () => {
  const message = shallowRef<{ kind: 'success' | 'info' | 'error'; text: string } | null>(null)

  function show(kind: 'success' | 'info' | 'error', text: string) {
    message.value = { kind, text }
  }

  function dismiss() {
    message.value = null
  }

  return { message, show, dismiss }
})
