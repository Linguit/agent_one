## Context

P01/P02 已建立配置加载、FastAPI 工厂和统一接口合同，但后端尚无持久化模块。该 change 需要跨配置、异步数据库、迁移、依赖注入和测试，必须保持 import 无 I/O。

## Goals / Non-Goals

**Goals:**
- 在 `super_ai.memory` 建立 SQLAlchemy async engine/session、声明式 Base、repository protocol 与 SQLite 实现。
- 让数据库 URL 只来自本地 JSON merge 配置，并支持显式 provider/lifespan 创建与关闭资源。
- 以 Alembic 迁移和 metadata 一致性测试锁定 schema 边界。
- 用不可变 domain record 隔离领域服务和 ORM model，提供未来 PostgreSQL 替换点。

**Non-Goals:**
- 不实现任何具体领域 CRUD、认证、Chat、知识、任务、MCP、AIOps、反馈或审计功能。
- 不在 import 阶段读取配置、连接 SQLite 或运行迁移。

## Decisions

1. **SQLAlchemy 2 async + aiosqlite**：与现有依赖和 SQLite 本地开发目标一致；通过 Repository Protocol 隔离未来 PostgreSQL，避免领域服务依赖 ORM。
2. **Alembic 唯一迁移权威**：metadata 用于模型声明与一致性检查，schema 变更只通过 `alembic upgrade head`；不在应用启动自动 create_all。
3. **显式资源生命周期**：`create_engine_provider()`/session factory 由 FastAPI lifespan 或测试 fixture 调用，模块导入仅声明类型和函数。
4. **最小规范化 schema**：首个迁移只建立 persistence foundation 所需的版本/探针表，不提前添加领域表；JSON 仅用于明确非查询扩展字段，时间统一 UTC、ID 由 UUID 生成。
5. **事务约定**：repository 不隐式提交；provider/服务边界显式 `begin`、commit 或 rollback，异常时回滚并关闭 session。

## Risks / Trade-offs

- [Risk] SQLite 并发写入有限 → 测试验证独立 async session，设置合理 busy timeout，未来可替换 PostgreSQL。
- [Risk] metadata 与迁移漂移 → fresh upgrade 后比较表集合和迁移 head 的合同测试。
- [Risk] 配置误指向开发者本机数据库 → 测试只注入临时 URL，禁止读取默认 var/memory.sqlite3。

## Migration Plan

新增 Alembic 环境和首个迁移；测试环境执行 fresh upgrade。应用默认只创建 provider，不自动迁移；部署/开发流程显式运行 `alembic upgrade head`。回滚通过 Alembic downgrade 或移除 provider 接入，不涉及业务数据迁移。

## Open Questions

无；后续领域 change 需在此边界上新增规范化模型和 repository contract。
