## Why

P02 contracts 与 P03 persistence 已具备接口和持久化基础，但应用尚无可复用的身份边界。现在增加最小用户认证闭环，为后续受保护资源提供可信当前用户上下文，并确保凭据与会话令牌不会以明文落库。

## What Changes

- 增加用户注册、登录、登出、认证恢复和当前用户查询。
- 增加 users、auth_sessions 迁移、owner-safe repository、AuthService 和 FastAPI 认证依赖。
- 采用 Argon2 密码哈希、规范化唯一邮箱和 SHA-256 opaque bearer token hash 会话存储。
- 同步 API contracts、统一错误 envelope、Bearer security scheme 和本机前端 CORS。
- 前端增加可复用 authClient/auth state；完整页面留待 P08。
- 以验收测试覆盖迁移、认证流程、撤销、恢复、清理和敏感数据不落库。

## Capabilities

### New Capabilities

- `user-authentication`: 用户身份、认证会话、认证 API 与前端认证状态。

### Modified Capabilities

无。

## Impact

影响 `apps/backend` 的模型、迁移、repository、服务、依赖和路由，`packages/api-contracts` 的 DTO/错误契约，`apps/frontend` 的认证客户端与状态，以及 OpenSpec 主规范和相关测试依赖（pwdlib[argon2]）。
