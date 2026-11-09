## 设计

### 上下文和值对象

CurrentUser 提供 user_id。OwnerScope 将 owner_user_id 与 tenant_id 绑定，当前阶段二者相等。空值拒绝。请求生命周期通过依赖注入传递，不在模块导入期间读取配置或创建外部客户端。

### Repository

受保护方法签名必须显式接收 owner_user_id，并把 owner 条件放入 SQL 查询。SQLite helper 统一生成 owner 条件和不可枚举结果。父资源越权映射 AUTH_FORBIDDEN。

### 向量约定

Milvus filter 必须包含 tenantId 和 allowedKnowledgeBaseIds。KB 列表为空时直接返回空结果，不连接 Milvus。召回后的可选 document/metadata filter 在 tool 层执行。删除必须同时包含 tenantId、knowledgeBaseId、documentId。ownerUserId 作为 metadata 保留。

### API 与客户端

OpenAPI 提供 bearer、401、403 复用组件。登出撤销认证并清理客户端可见状态，不删除持久数据。

