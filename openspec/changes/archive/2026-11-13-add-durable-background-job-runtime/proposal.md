## Why

文档索引和 AIOps 需要跨连接、跨进程保留任务进度，才能在客户端断开或进程重启后继续处理。持久化事件也为后续业务提供按序恢复进度的依据。

## What Changes

- 使用 SQLite 保存后台任务及可重放事件。
- 在 FastAPI lifespan 管理 worker，支持租约、重试、超时和协作式取消。
- 添加按认证身份隔离的任务查询、取消和重试接口。

## Capabilities

### New Capabilities

- `durable-background-job-runtime`：任务存储、执行、事件和管理接口。

### Modified Capabilities

无。

## Impact

涉及 Alembic、SQLite Repository、FastAPI、共享契约和测试。文档索引、AIOps 业务 handler 与 SSE HTTP 协议由后续变更接入。
