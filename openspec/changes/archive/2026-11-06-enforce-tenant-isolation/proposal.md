## Why

当前认证已建立，但资源访问尚未形成强制 owner scope，容易出现先按资源 ID 查询再补权限判断的越权与枚举风险。现在建立本地单租户模型，为后续所有资源和向量检索提供统一边界。

## What Changes

- **BREAKING** 所有受保护 Repository 方法显式接收 owner_user_id，并在查询条件中执行 scope。
- 定义 CurrentUser、OwnerScope、tenant 上下文及 SQLite scoped helper。
- 统一跨用户错误语义，父资源越权返回 AUTH_FORBIDDEN 403，资源不存在不泄漏细节。
- 为未来受保护 API 建立 bearer、401、403 复用契约。
- 约定 Milvus tenantId、allowedKnowledgeBaseIds 过滤和删除 scope。
- 登出仅撤销认证并清理客户端状态。
- 在架构文档声明所有未来资源遵守 tenant 边界。

## Capabilities

### New Capabilities
- \`tenant-isolation\`: 统一 owner scope、Repository、SQLite 和向量过滤边界。

### Modified Capabilities`r`n`r`n## Impact

影响 apps/backend 的认证上下文、Repository 约定、contracts/OpenAPI、测试和架构文档。P01 仅提供可复用边界和测试，不实现聊天、知识库、向量服务或其他业务资源。


