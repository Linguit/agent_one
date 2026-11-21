import { expect, expectTypeOf, it } from 'vitest'
import { CHAT_CONFIGURATION_PATHS, SKILL_UPLOAD_POLICY } from '../src/index'
import type { ChatConfiguration, ChatConfigurationInput, UserChatSkill } from '../src/index'

it('defines editable configuration assets and strict Skill uploads', () => {
  expect(CHAT_CONFIGURATION_PATHS).toEqual([
    '/chat/configuration', '/chat/prompts', '/chat/prompts/{id}',
    '/chat/skills', '/chat/skills/{id}',
  ])
  expect(SKILL_UPLOAD_POLICY).toEqual({ filename: 'SKILL.md', maxBytes: 262144 })
  expectTypeOf<ChatConfigurationInput['selectedPromptId']>().toEqualTypeOf<string | null>()
  expectTypeOf<ChatConfigurationInput['selectedSkillIds']>().toEqualTypeOf<string[]>()
  expectTypeOf<ChatConfiguration['prompts'][number]['content']>().toEqualTypeOf<string>()
  expectTypeOf<ChatConfiguration['skills'][number]>().toEqualTypeOf<UserChatSkill>()
  expectTypeOf<UserChatSkill['filename']>().toEqualTypeOf<'SKILL.md'>()
})
