## Context

P11 在 SQLite 保留原文和分块配置，并记录索引状态。

## Goals / Non-Goals

向 Agent 提供可绑定当前用户的 LangChain 检索工具。公开搜索端点不在本次范围内。

## Decisions

- SQLite 按 owner、成功索引状态和可选过滤条件确定语料。复用索引分块与稳定 ID，Milvus 同时限制 tenant、知识库与文档，并与语料核对。
- 查询嵌入完成后并行运行同步 Milvus 查找和内存 BM25L。RRF 同分按 chunk ID 排序，重排最多 20 个候选。
- 复用 Qwen provider，由工具工厂按可信 scope 绑定资源。错误只暴露失败阶段。

## Risks / Trade-offs

每次请求重新分块并计算词频，成本随过滤后的语料增长。
