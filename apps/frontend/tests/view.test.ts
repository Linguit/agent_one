import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import FoundationView from '../src/FoundationView.vue'

it('显示桌面工程骨架与明确范围', () => {
  const wrapper = mount(FoundationView)
  expect(wrapper.get('h1').text()).toBe('测试骨架')
  expect(wrapper.findAll('article')).toHaveLength(3)
  expect(wrapper.text()).toContain('当前不包含认证、聊天、知识库、AIOps 或 MCP 功能')
})
