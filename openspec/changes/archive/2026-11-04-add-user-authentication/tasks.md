## 1. 验收测试先行

- [x] 1.1 增加 migration/schema、repository、AuthService 与 API 的失败优先测试
- [x] 1.2 增加 contracts 类型/序列化测试和前端 authClient/auth state 测试

## 2. 后端持久化与认证

- [x] 2.1 新增 users/auth_sessions 模型及 Alembic migration
- [x] 2.2 实现 owner-safe repository、Argon2 密码服务和 token hash 会话逻辑
- [x] 2.3 实现认证 FastAPI dependency、路由、统一错误和 CORS

## 3. Contracts 与前端

- [x] 3.1 同步 Auth DTO、请求/响应、Bearer scheme 和 401 错误
- [x] 3.2 实现可复用 authClient/auth state，支持恢复、失效与登出清理

## 4. 验证与发布

- [x] 4.1 运行受影响门禁、openspec validate --all、diff check，修复 CRITICAL
- [x] 4.2 同步 delta specs 并归档 change
