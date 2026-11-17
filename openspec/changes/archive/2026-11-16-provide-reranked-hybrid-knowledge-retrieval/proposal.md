## Why

已索引文档需要供 Agent 按当前用户检索，并附上可追溯的引用和各阶段分数。

## What Changes

- 提供 LangChain 工具，按可信用户范围执行 Milvus、BM25L、RRF 和 Qwen 重排。
- 增加工具输入、结果和引用契约。

## Capabilities

### New Capabilities

- `hybrid-knowledge-retrieval`：混合知识检索与重排。

### Modified Capabilities

- `api-contracts`：共享知识检索工具类型。

## Impact

涉及后端检索、索引语料、Milvus 查询和共享 TypeScript 契约。
