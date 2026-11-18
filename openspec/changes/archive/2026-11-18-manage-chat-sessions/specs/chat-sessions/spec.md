## ADDED Requirements

### Requirement: 会话访问与持久化

系统 MUST 使用可信用户范围读写 SQLite 会话及消息。

#### Scenario: 隔离两个用户的会话

- **WHEN** 用户创建会话或读取列表
- **THEN** 系统仅返回该用户范围内的会话，并以更新时间和 ID 降序排列

#### Scenario: 外部会话与未认证请求

- **WHEN** 已认证用户访问不属于自己的会话或未知 ID
- **THEN** 系统返回 AUTH_FORBIDDEN
- **AND** 未认证请求返回 AUTH_UNAUTHORIZED

### Requirement: 消息生命周期

系统 MUST 原子写入消息及会话状态，持久化消息角色、内容、序号、时间和结构化元数据。

#### Scenario: 并发追加和首条用户消息

- **WHEN** 用户给会话追加消息
- **THEN** 消息以连续序号保存，首条用户消息生成不超过 80 字符的标题，每次追加更新会话时间
- **AND** 详情按序号返回消息以及其 references 和 toolCallIds 元数据

#### Scenario: 清空或删除会话

- **WHEN** 用户清空会话
- **THEN** 系统清除消息并恢复默认标题和初始序号
- **AND** 删除会话时系统同时删除其子消息

### Requirement: 前端与服务端状态对账

前端 MUST 使用服务端响应更新列表和详情，并在认证切换时清除会话缓存。

#### Scenario: 成功变更后的对账

- **WHEN** 创建、追加、清空或删除请求成功
- **THEN** 前端重新读取列表与仍然存在的当前详情
