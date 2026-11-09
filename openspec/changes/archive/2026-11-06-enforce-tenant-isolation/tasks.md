## 1. 核心边界
- [x] 实现 CurrentUser、OwnerScope、tenant 上下文和值校验
- [x] 实现 SQLite scope helper 与 scoped Repository 协议
- [x] 实现 Milvus filter/delete builder 约定

## 2. 契约与文档
- [x] 更新 OpenAPI/contracts bearer、401、403 复用模式
- [x] 更新 AGENTS/架构文档中的资源边界声明
- [x] 更新认证登出保留语义

## 3. 测试与门禁
- [x] 编写双用户读取、更新、删除、父子资源和不可枚举合同测试
- [x] 编写 owner_user_id、空 scope 参数级失败测试
- [x] 运行全部 backend/contracts/frontend/OpenSpec 门禁并修复问题


