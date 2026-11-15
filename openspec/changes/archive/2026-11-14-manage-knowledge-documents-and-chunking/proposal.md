## Why

知识库需要有可追溯的文档来源和确定的切分规则，才能为后续索引提供稳定输入。

## What Changes

- 为每个已认证用户提供一个隐式默认知识库，以及文档上传、列表、详情、删除和切分预览。
- 支持 UTF-8 Markdown 和 PDF，实施 10 MiB 限制、重复检测、显式覆盖及旧向量清理。
- 持久化索引所需的正文、元数据和实际切分配置，供后续索引复用切分入口。
- 本期范围限定为文档管理和切分。

## Capabilities

### New Capabilities

- `knowledge-documents` 提供默认知识库、文档生命周期和切分预览。

### Modified Capabilities

- `api-contracts` 增加知识库文档接口契约。

## Impact

涉及共享 TypeScript 契约、FastAPI OpenAPI、SQLite 迁移、现有 Milvus 删除边界及文档提取依赖。
