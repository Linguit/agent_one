# 后端基础骨架

技术栈、配置和安全边界见根 AGENTS.md。FastAPI 应用在 lifespan 内创建 SQLite 引擎并管理后台任务 worker。

```powershell
uv sync
uv run ruff check .
uv run pyright
uv run pytest
uv run uvicorn super_ai.main:create_app --factory --host 127.0.0.1 --port 8000
```

启动前按根 README 创建本机 JSON，并对应用配置指向的 SQLite 数据库执行 Alembic 迁移。应用通过已安装的 `super_ai` 包导入。测试使用临时配置与数据库。

## 后台任务

业务入口用可信认证身份调用 `JobRepository.enqueue`。通过 `JobHandlers.register(kind, handler)` 注册异步处理函数，并把注册表传给 `create_app(job_handlers=...)`。handler 可以用 `JobContext.emit` 保存业务进度。事件消费者用 `list_events(job_id, owner_user_id=..., after_sequence=...)` 按序恢复，首次读取用 0。

任务管理端点使用 Bearer 认证。列表和详情返回任务元数据，取消已排队的任务立即生效，运行中的任务由 worker 协作取消。手动重试接受失败和已取消的任务，并返回关联的新任务。重启后 worker 回收过期租约。业务 handler 应能安全地重复执行，并及时响应异步取消。
