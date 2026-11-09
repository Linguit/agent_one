# Super AI 工程基础

当前范围为目录、健康接口、桌面骨架、类型契约和配置安全边界。认证、聊天、知识库、AIOps、MCP 由后续提案实现。

## 本地验证

根目录安装 npm 依赖，后端执行 uv sync。按根 README 复制两份空凭据模板为 ignored 本机 JSON。

| 范围 | 命令 |
| --- | --- |
| 后端 | uv run ruff check . / uv run pyright / uv run pytest |
| 契约 | npm run contracts:typecheck / npm run contracts:test |
| 前端 | npm run frontend:typecheck / npm run frontend:test / npm run frontend:build |
| 配置安全 | npm run frontend:security / npm run foundation:test |
| 文档 | npm run docs:build |
| 规范 | openspec validate --all |

## 安全与部署边界

应用只读取本地 JSON 深合并结果，前端仅接收公开白名单字段。秘密不得进入 bundle，测试不读取开发者真实配置。
Compose 最终只运行 etcd、MinIO、Milvus、Attu、Alertmanager；前后端和官方 CLS MCP Server 运行在主机。P01 不提供 Compose 部署。
完整技术栈、tenant 隔离与真实 MCP 约束见根 AGENTS.md。文档和规范正文使用简体中文；提交采用 Conventional Commits。

当前依赖审计及固定版本限制见 [依赖检查记录](dependency-notes.md)。
