export interface PromptInput {
  label: string
  content: string
}

export interface UserChatPrompt extends PromptInput {
  id: string
}

export type SkillMetadata = null | boolean | number | string | SkillMetadata[] |
  { [key: string]: SkillMetadata }

export interface UserChatSkill {
  id: string
  filename: 'SKILL.md'
  name: string
  description: string
  summary: string
  content: string
  metadata: Record<string, SkillMetadata>
}

export interface ChatConfigurationInput {
  selectedPromptId: string | null
  selectedSkillIds: string[]
}

export interface ChatConfiguration extends ChatConfigurationInput {
  prompts: UserChatPrompt[]
  skills: UserChatSkill[]
}

export const CHAT_CONFIGURATION_PATHS = [
  '/chat/configuration', '/chat/prompts', '/chat/prompts/{id}',
  '/chat/skills', '/chat/skills/{id}',
] as const

export const SKILL_UPLOAD_POLICY = { filename: 'SKILL.md', maxBytes: 262144 } as const
