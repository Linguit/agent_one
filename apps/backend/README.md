# 后端基础骨架

技术栈、配置和安全边界见根 AGENTS.md。当前只实现本地 JSON 加载、依赖注入入口、FastAPI create_app 和 GET /health；数据库与 Agent 服务未接入。

```powershell
uv sync
uv run ruff check .
uv run pyright
uv run pytest
uv run uvicorn super_ai.main:create_app --factory --host 127.0.0.1 --port 8000
```

启动前按根 README 创建本机 JSON。只从 super_ai 导入；安装包后无需修改 sys.path。测试注入临时配置，不依赖外部服务。SQLAlchemy 2 async、aiosqlite、Alembic 已声明依赖，尚无业务模型或迁移。
