<script setup lang="ts">
import { Layers, ArrowUpRight } from 'lucide-vue-next'
import { config } from './config'
</script>

<template>
  <main class="foundation">
    <header class="topbar"><span class="brand"><Layers :size="22" /> SUPER AI</span><span>工程基础 / P01</span></header>
    <section class="hero" aria-labelledby="page-title">
      <p class="eyebrow">FOUNDATION · 01</p>
      <h1 id="page-title">{{ config.title }}</h1>
      <p class="intro">从清晰的边界开始。项目目录、配置隔离与质量检查已建立，产品能力由后续提案逐步实现。</p>
      <span class="badge">桌面 Web 基础骨架</span>
    </section>
    <section class="grid" aria-label="基础工程范围">
      <article><span class="number">01</span><h2>应用骨架</h2><p>Vue 桌面页面与 FastAPI 健康接口，提供后续开发的起点。</p></article>
      <article><span class="number">02</span><h2>安全配置</h2><p>本地 JSON 分层合并，浏览器仅接收明确允许的公开字段。</p></article>
      <article><span class="number">03</span><h2>质量基线</h2><p>类型检查、自动化测试与构建检查，让每一步都有依据。</p></article>
    </section>
    <footer><span>当前不包含认证、聊天、知识库、AIOps 或 MCP 功能。</span><span class="next">下一步由 OpenSpec 提案定义 <ArrowUpRight :size="16" /></span></footer>
  </main>
</template>
