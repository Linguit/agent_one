## Purpose

建立统一租户隔离边界。

## Requirements

### Requirement: Owner scope is mandatory
Repository 方法 SHALL 显式接收 owner_user_id，空值拒绝。

#### Scenario: Cross-user read
- **WHEN** 用户 B 读取用户 A 资源
- **THEN** 不泄漏资源细节

### Requirement: Parent authorization
父资源越权 SHALL 返回 AUTH_FORBIDDEN 403。

#### Scenario: Parent denied
- **WHEN** 用户访问其他用户父资源
- **THEN** 返回 AUTH_FORBIDDEN 403

### Requirement: Tenant and vector filters
向量 filter SHALL 包含 tenantId 与 allowedKnowledgeBaseIds，空列表返回空结果。

#### Scenario: Empty KB scope
- **WHEN** allowedKnowledgeBaseIds 为空
- **THEN** 不连接 Milvus 并返回空结果

### Requirement: Protected API contracts
受保护 path SHALL 使用 bearer、401、403 复用模式。

#### Scenario: Protected path
- **WHEN** 未认证访问受保护 path
- **THEN** 返回 401

### Requirement: Logout retention
登出 SHALL 只撤销认证并清理客户端状态。

#### Scenario: Logout keeps data
- **WHEN** 用户登出
- **THEN** 持久数据保留

### Requirement: Architectural boundary
列出的未来资源 SHALL 遵守 owner scope。

#### Scenario: Future resources
- **WHEN** 创建未来资源
- **THEN** 使用当前 owner scope

