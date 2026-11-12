import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import AppFeedback from '../src/components/AppFeedback.vue'
import AppEmptyState from '../src/components/AppEmptyState.vue'
import AppErrorState from '../src/components/AppErrorState.vue'
import AppLoadingState from '../src/components/AppLoadingState.vue'
import AsyncStatusBadge from '../src/components/AsyncStatusBadge.vue'
import { useFeedback } from '../src/feedback'

afterEach(() => vi.useRealTimers())

it('异步状态包含可朗读的文字', () => {
  expect(mount(AppEmptyState).get('[role="status"]').text()).toBe('暂无内容')
  expect(mount(AppErrorState).get('[role="alert"]').text()).toContain('加载失败')
  expect(mount(AppLoadingState).get('[role="status"]').text()).toContain('正在加载')
  expect(mount(AsyncStatusBadge, { props: { state: 'success' } }).get('[role="status"]').text()).toBe('已完成')
})

it('反馈支持三秒计时、替换、关闭和卸载清理', async () => {
  vi.useFakeTimers()
  const pinia = createPinia()
  const feedback = useFeedback(pinia)
  const wrapper = mount(AppFeedback, { global: { plugins: [pinia] } })
  feedback.show('success', '已保存')
  await nextTick()
  expect(wrapper.get('[role="status"]').text()).toContain('已保存')
  vi.advanceTimersByTime(2500)
  feedback.show('error', '保存失败')
  await nextTick()
  vi.advanceTimersByTime(2999)
  expect(wrapper.get('[role="alert"]').text()).toContain('保存失败')
  vi.advanceTimersByTime(1)
  await nextTick()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  feedback.show('info', '有新消息')
  await nextTick()
  await wrapper.get('button[aria-label="关闭反馈"]').trigger('click')
  expect(feedback.message).toBeNull()
  feedback.show('info', '再次提示')
  wrapper.unmount()
  expect(vi.getTimerCount()).toBe(0)
})
