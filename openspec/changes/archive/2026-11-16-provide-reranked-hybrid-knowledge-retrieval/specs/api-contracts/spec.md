## ADDED Requirements

### Requirement: 知识检索工具共享契约
共享契约 SHALL 定义知识检索工具输入、输出和引用类型。

#### Scenario: 消费工具结果
- **WHEN** 调用方处理检索响应
- **THEN** 可以读取 chunkId、documentId、knowledgeBaseId、source、excerpt、metadata、分支排名和分数、rrfScore、rerankRank、rerankScore 与 score。
