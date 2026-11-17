## ADDED Requirements

### Requirement: 文档索引任务契约

共享契约和 OpenAPI SHALL 定义索引任务创建、状态、重试重建和取消，并复用统一响应和属主鉴权。

#### Scenario: 客户端展示任务状态

- **WHEN** 客户端读取索引任务 DTO
- **THEN** 状态与文档 DTO 的索引状态使用相同枚举。
