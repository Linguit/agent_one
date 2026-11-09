## Context

P03 提供 SQLAlchemy async persistence 与迁移基础，P02 提供统一 API contract/envelope。认证需要跨越数据库、服务、HTTP 依赖和前端状态，同时满足密码与 token 的安全边界。

## Goals / Non-Goals

**Goals:** 实现邮箱用户、Argon2 密码哈希、opaque bearer session、统一认证 API、可信当前用户依赖和前端恢复/清理。

**Non-Goals:** 自动过期、刷新 token、租户认证、完整登录页面、外部身份提供商和业务数据删除。

## Decisions

- users.email 以 trim+casefold 规范化并唯一索引；password_hash 仅保存 pwdlib Argon2 结果。
- auth_sessions 保存 token_hash（raw token 的 SHA-256 十六进制摘要）、created_at、last_seen_at、revoked_at 和 user_id 外键；raw token 只在登录响应返回。
- 未知邮箱使用固定 dummy Argon2 hash 完成验证，统一映射 AUTH_INVALID_CREDENTIALS。
- AuthService 负责注册/登录/注销/当前用户，FastAPI dependency 解析 Authorization Bearer 并更新 last_seen；不增加未设计的过期判断。
- contracts 作为请求/响应唯一来源，错误沿用 P02 envelope/requestId；前端 localStorage 仅保存 token，内存 state 保存用户。

## Risks / Trade-offs

- [Risk] bearer token 被客户端窃取 → 仅存 hash、登出撤销并避免日志输出 raw token。
- [Risk] SQLite 并发重复注册 → 数据库唯一约束，服务将冲突转为统一邮箱已存在错误。
- [Risk] Argon2 计算成本影响登录延迟 → dummy 校验与真实校验使用同一 pwdlib 配置，测试使用可注入 hasher。

## Migration Plan

先执行 Alembic migration 创建 users/auth_sessions，再部署 API；回滚时按依赖顺序删除会话和用户表。无数据迁移脚本外的外部资源。

## Open Questions

无；自动过期明确留给后续 change。
