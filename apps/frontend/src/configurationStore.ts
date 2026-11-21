import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import type { ChatConfiguration, ChatConfigurationInput, PromptInput } from '@super-ai/api-contracts'
import { useAuthStore } from './auth'
import { createConfigurationClient } from './configurationClient'

export const useConfigurationStore = defineStore('chat-configuration', () => {
  const auth = useAuthStore()
  const client = createConfigurationClient(auth)
  const configuration = ref<ChatConfiguration | null>(null)
  const prompts = computed(() => configuration.value?.prompts ?? [])
  const skills = computed(() => configuration.value?.skills ?? [])
  const selectedPromptId = computed(() => configuration.value?.selectedPromptId ?? null)
  const selectedSkillIds = computed(() => configuration.value?.selectedSkillIds ?? [])
  let generation = 0
  let pending = Promise.resolve()

  watch(() => auth.user?.id, () => {
    generation++
    configuration.value = null
    pending = Promise.resolve()
  }, { flush: 'sync' })

  function enqueue(action: () => Promise<unknown>, returnsConfiguration = false) {
    const ownerGeneration = generation
    const current = () => ownerGeneration === generation
    const result = pending.then(async () => {
      if (!current()) return
      const response = await action()
      if (!current()) return
      const fresh = returnsConfiguration ? response as ChatConfiguration : await client.get()
      if (current()) configuration.value = fresh
    })
    pending = result.catch(() => {})
    return result
  }

  const refresh = () => enqueue(client.get, true)
  const saveSelection = (selection: ChatConfigurationInput) => enqueue(
    () => client.save({
      selectedPromptId: selection.selectedPromptId,
      selectedSkillIds: [...selection.selectedSkillIds],
    }), true,
  )
  const createPrompt = (body: PromptInput) => enqueue(() => client.createPrompt({ ...body }))
  const updatePrompt = (id: string, body: PromptInput) => enqueue(
    () => client.updatePrompt(id, { ...body }),
  )
  const deletePrompt = (id: string) => enqueue(() => client.deletePrompt(id))
  const uploadSkill = (file: File) => enqueue(() => client.uploadSkill(file))
  const deleteSkill = (id: string) => enqueue(() => client.deleteSkill(id))

  return {
    configuration, prompts, skills, selectedPromptId, selectedSkillIds,
    refresh, saveSelection, createPrompt, updatePrompt, deletePrompt, uploadSkill, deleteSkill,
  }
})
