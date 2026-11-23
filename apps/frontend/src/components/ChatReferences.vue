<script setup lang="ts">
import { rankedReferences, stage } from '../chatPresentation'
import { RouterLink } from 'vue-router'
defineProps<{ references: unknown }>()
</script>

<template>
  <section v-if="rankedReferences(references).length" class="chat-references" aria-label="回答引用">
    <article v-for="(source, index) in rankedReferences(references)" :key="source.chunkId ?? source.uri">
      <strong>{{ index + 1 }}. {{ source.source ?? source.title }}</strong>
      <p v-if="source.excerpt">{{ source.excerpt }}</p>
      <small>文档 {{ source.documentId ?? '未提供' }} · 知识库 {{ source.knowledgeBaseId ?? '未提供' }}</small>
      <dl>
        <dt>vector</dt><dd>{{ stage(source.vectorRank, source.vectorScore) }}</dd>
        <dt>BM25</dt><dd>{{ stage(source.bm25Rank, source.bm25Score) }}</dd>
        <dt>RRF</dt><dd>{{ stage(source.rrfRank, source.rrfScore) }}</dd>
        <dt>rerank</dt><dd>{{ stage(source.rerankRank, source.rerankScore ?? source.score) }}</dd>
      </dl>
      <details><summary>来源详情与检索轨迹</summary>
        <p>vector / BM25 → RRF 融合 → rerank 重排</p>
        <dl><template v-for="(value, key) in source.metadata" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></template></dl>
        <RouterLink v-if="source.documentId && source.knowledgeBaseId"
          :to="{ name: 'knowledge', query: { kb: source.knowledgeBaseId, document: source.documentId } }">打开来源文档</RouterLink>
      </details>
    </article>
  </section>
</template>
