## ADDED Requirements

### Requirement: 非流式聊天会话契约

共享类型与 OpenAPI MUST 定义会话、消息、元数据及创建、列表、详情、追加、清空和删除的请求与响应。

#### Scenario: 统一会话信封

- **WHEN** 客户端访问聊天会话接口
- **THEN** 接口返回共享成功或错误信封，OpenAPI 声明适用的 401 和 403 响应
