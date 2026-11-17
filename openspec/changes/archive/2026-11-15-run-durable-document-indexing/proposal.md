## Why

文档上传后的嵌入和向量写入需要独立于 HTTP 请求运行，且在 worker 重启后能恢复。

## What Changes

- 客户端上传成功后显式创建持久索引任务，查询状态，并支持重试、重建和取消。
- worker 复用已保存的切分配置，调用 Qwen 和 Milvus 写入完整索引。

## Capabilities

### New Capabilities

- `durable-document-indexing` 提供文档索引任务与状态恢复。

### Modified Capabilities

- `api-contracts` 增加索引任务和文档索引状态接口契约。

## Impact

涉及 SQLite 迁移、持久任务 worker、知识库 API、共享契约和客户端。
