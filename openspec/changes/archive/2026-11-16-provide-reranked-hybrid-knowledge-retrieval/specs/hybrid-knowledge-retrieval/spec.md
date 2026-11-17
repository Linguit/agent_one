## ADDED Requirements

### Requirement: 按用户执行混合知识检索
系统 SHALL 提供绑定可信 owner 和 tenant 的 knowledge_retrieval LangChain 工具。query 去除首尾空白后必须非空，topK 默认和最大为 5。知识库与文档过滤条件只能缩小成功索引的当前用户语料。

#### Scenario: 检索混合语料
- **WHEN** 用户提交合法查询且存在有权访问的索引语料
- **THEN** 系统嵌入查询，随后并行执行 Milvus 向量召回和内存 BM25L。中文按单字和连续双字切分，保留 ASCII 运维词，不相交词项贡献零，BM25L 分数非负。

#### Scenario: 过滤越权语料
- **WHEN** 工具收到指向其他用户文档的过滤条件
- **THEN** 返回空结果，且不访问外部提供方。

### Requirement: 融合并保留重排证据
系统 SHALL 使用 k=60 的 RRF 融合，按稳定 chunk ID 打破同分，至多送 20 条至 Qwen 重排。输出至多 topK 条且无最低分阈值，保留标识、来源、摘录、元数据、各阶段原始排名和分数。未命中的分支排名和分数为空，兼容 score 等于 rerankScore。

#### Scenario: 重排改变候选顺序
- **WHEN** Qwen 重新排序候选
- **THEN** 输出遵循重排顺序，各召回排名仍保留。

#### Scenario: 无召回命中或服务失败
- **WHEN** 两路均无命中或必需阶段失败
- **THEN** 无命中时返回空结果，失败时安全报告对应阶段。
