## Why

认证、Chat、知识、任务、MCP、AIOps、反馈和审计后续都需要可靠的持久化边界。当前后端只有配置和 health 基础，缺少可替换、可测试且导入安全的数据库基础，直接在领域代码中创建 ORM 或连接会造成耦合和测试污染。

## What Changes

- 建立基于 SQLAlchemy 2 async + aiosqlite 的 SQLite persistence foundation。
- 从本地 JSON merge 配置读取数据库 URL，并提供显式 engine/session provider。
- 以 Alembic 作为唯一 schema 迁移权威，加入 Base、迁移环境和首个基础迁移。
- 建立 Repository Protocol、不可变 record、SQLite repository 边界和事务约定。
- 提供临时 SQLite 测试 fixture、migration helper、import-safety 和并发/回滚测试。
- **BREAKING**：领域服务不得接收 ORM model 或自行创建数据库资源。

## Capabilities

### New Capabilities
- `sqlite-repository-foundation`: 数据库配置、异步会话、迁移、repository 抽象和测试基础。

### Modified Capabilities
- 无。

## Impact

影响 `apps/backend/src/super_ai/memory`、Alembic 配置和 migrations、项目 JSON 配置模板及后端测试；不实现任何认证、Chat、知识、任务、MCP、AIOps、反馈或审计领域 CRUD。
