<script setup lang="ts">
import { ref } from 'vue'
import { useConfigurationStore } from '../configurationStore'
const store = useConfigurationStore()
const busy = ref(false)
const error = ref('')
const editing = ref<string | null>(null)
const label = ref('')
const content = ref('')
async function run(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '操作失败，请重试。' }
  finally { busy.value = false }
}
async function savePrompt() {
  await run(async () => {
    const body = { label: label.value, content: content.value }
    if (editing.value) await store.updatePrompt(editing.value, body)
    else await store.createPrompt(body)
    editing.value = null; label.value = ''; content.value = ''
  })
}
function toggleSkill(id: string, checked: boolean) {
  return run(() => store.saveSelection({ selectedPromptId: store.selectedPromptId,
    selectedSkillIds: checked ? [...store.selectedSkillIds, id] : store.selectedSkillIds.filter(value => value !== id) }))
}
function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void run(async () => { await store.uploadSkill(file); input.value = '' })
}
</script>
<template>
  <aside class="chat-configuration" aria-label="聊天配置">
    <p v-if="error" role="alert">{{ error }}</p>
    <button :disabled="busy" @click="run(store.refresh)">刷新配置</button>
    <details open><summary>Prompt</summary>
      <fieldset :disabled="busy"><legend>选择提示词</legend>
        <label><input type="radio" name="prompt" :checked="!store.selectedPromptId"
          @change="run(() => store.saveSelection({ selectedPromptId: null, selectedSkillIds: store.selectedSkillIds }))" />默认提示词</label>
        <div v-for="prompt in store.prompts" :key="prompt.id" class="configuration-row">
          <label><input type="radio" name="prompt" :checked="store.selectedPromptId === prompt.id"
            @change="run(() => store.saveSelection({ selectedPromptId: prompt.id, selectedSkillIds: store.selectedSkillIds }))" />{{ prompt.label }}</label>
          <button @click="editing = prompt.id; label = prompt.label; content = prompt.content">编辑</button>
          <button @click="run(() => store.deletePrompt(prompt.id))">删除</button>
        </div>
      </fieldset>
      <form aria-label="提示词编辑" @submit.prevent="savePrompt">
        <label>提示词名称<input v-model="label" required maxlength="200" /></label>
        <label>提示词正文<textarea v-model="content" required rows="5" /></label>
        <button :disabled="busy">{{ editing ? '保存提示词' : '新建提示词' }}</button>
        <button v-if="editing" type="button" @click="editing = null; label = ''; content = ''">取消编辑</button>
      </form>
    </details>
    <details open><summary>Skill</summary>
      <fieldset :disabled="busy"><legend>选择技能（可多选）</legend>
        <div v-for="skill in store.skills" :key="skill.id" class="configuration-row">
          <label><input type="checkbox" :checked="store.selectedSkillIds.includes(skill.id)"
            @change="toggleSkill(skill.id, ($event.target as HTMLInputElement).checked)" />{{ skill.name }}</label>
          <details><summary>说明</summary><p>{{ skill.description }}</p><p>{{ skill.summary }}</p></details>
          <button @click="run(() => store.deleteSkill(skill.id))">删除技能</button>
        </div>
        <label>上传 SKILL.md<input type="file" accept=".md" @change="upload" /></label>
      </fieldset>
    </details>
  </aside>
</template>
