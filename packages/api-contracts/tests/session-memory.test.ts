import { expect, expectTypeOf, it } from 'vitest'
import { ERROR_CATALOG } from '../src/index'
import type { ChatMemoryUpdate, ChatSession, MemoryMode } from '../src/index'

it('defines memory state and shared transport errors', () => {
  expectTypeOf<MemoryMode>().toEqualTypeOf<'every_30_turns' | 'context_70_percent' | 'manual'>()
  expectTypeOf<ChatMemoryUpdate['memoryMode']>().toEqualTypeOf<MemoryMode>()
  expectTypeOf<ChatSession['contextWindowTokens']>().toEqualTypeOf<number>()
  expectTypeOf<ChatSession['lastCompactedAt']>().toEqualTypeOf<string | null>()
  expectTypeOf<ChatSession['canCompact']>().toEqualTypeOf<boolean>()
  expect(ERROR_CATALOG.CHAT_CONTEXT_LIMIT_REACHED).toEqual({ category: 'BUSINESS', httpStatus: 409,
    message: '上下文已达到模型窗口的 95%，请手动压缩后重试。' })
})
