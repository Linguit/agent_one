import type {
  ChatConfiguration, ChatConfigurationInput, ChatDeleted, PromptInput,
  UserChatPrompt, UserChatSkill,
} from '@super-ai/api-contracts'
import type { useAuthStore } from './auth'

export function createConfigurationClient(auth: Pick<ReturnType<typeof useAuthStore>, 'request'>) {
  return {
    get: () => auth.request<ChatConfiguration>('/chat/configuration'),
    save: (selection: ChatConfigurationInput) => auth.request<ChatConfiguration>(
      '/chat/configuration', { method: 'PUT', body: JSON.stringify(selection) },
    ),
    createPrompt: (body: PromptInput) => auth.request<UserChatPrompt>(
      '/chat/prompts', { method: 'POST', body: JSON.stringify(body) },
    ),
    updatePrompt: (id: string, body: PromptInput) => auth.request<UserChatPrompt>(
      `/chat/prompts/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body) },
    ),
    deletePrompt: (id: string) => auth.request<ChatDeleted>(
      `/chat/prompts/${encodeURIComponent(id)}`, { method: 'DELETE' },
    ),
    uploadSkill: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return auth.request<UserChatSkill>('/chat/skills', { method: 'POST', body })
    },
    deleteSkill: (id: string) => auth.request<ChatDeleted>(
      `/chat/skills/${encodeURIComponent(id)}`, { method: 'DELETE' },
    ),
  }
}
