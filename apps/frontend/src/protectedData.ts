import { defineStore } from 'pinia'

export const useProtectedCleanup = defineStore('protectedCleanup', () => {
  const callbacks = new Set<() => void>()
  function register(cleanup: () => void) {
    callbacks.add(cleanup)
    return () => callbacks.delete(cleanup)
  }
  function clear() {
    for (const cleanup of [...callbacks]) cleanup()
  }
  return { register, clear }
})

export const useProtectedData = defineStore('protectedData', {
  state: () => ({ chat: {} as Record<string, unknown>, knowledge: {} as Record<string, unknown>,
    aiops: {} as Record<string, unknown> }),
})
