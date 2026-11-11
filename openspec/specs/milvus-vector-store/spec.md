## Purpose

提供显式生命周期及租户隔离的 Milvus 向量操作。

## Requirements

### Requirement: 显式连接与集合初始化

适配器 MUST 从本地合并 JSON 的 vectorStore 获取配置，使用可注入的官方 PyMilvus 客户端，并提供 connect、initialize、health、insert、search、delete-document。

#### Scenario: 导入并重复初始化

- **WHEN** 导入模块并构造适配器，随后显式初始化两次
- **THEN** 导入和构造无连接副作用，初始化可重复执行并加载集合
- **AND** 新集合包含 chunkId 主键、documentId、knowledgeBaseId、ownerUserId、tenantId、content、source、createdAt、metadata、1024 维 FLOAT_VECTOR 和可过滤标量索引，向量索引为 HNSW/COSINE，M=16、efConstruction=200，检索 ef=64

### Requirement: 租户范围内的向量操作

适配器 MUST 从可信结构化 scope 生成查询条件。插入 MUST 写入标量与 metadata 中的 ownerUserId 和 tenantId。

#### Scenario: 在授权知识库内检索

- **WHEN** 按授权知识库列表检索
- **THEN** 表达式仅约束 tenantId 和 allowedKnowledgeBaseIds 对应的 knowledgeBaseId，值经过安全转义，空列表直接返回且不连接
- **AND** 文档及 metadata 条件由检索工具在 owner-scoped 粗召回后过滤

#### Scenario: 删除文档向量

- **WHEN** 删除指定知识库中的文档
- **THEN** 表达式同时约束 tenantId、knowledgeBaseId 和 documentId
- **AND** 空 tenant 或空 KB、文档删除范围在连接前拒绝
