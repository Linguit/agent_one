## Why

用户需要管理自己的真实 MCP 连接，让 Chat 和后续 AIOps 通过同一来源发现和调用工具，并保持 owner 隔离与安全审计。

## What Changes

- 增加用户级 MCP 连接持久化、CRUD、真实检查和工具发现。
- 有界超时与发现重试，拒绝同名工具冲突；调用不自动重试，避免副作用重复执行。
- 请求级向 Chat 注入真实工具，复用 SSE 和只保留参数键的安全审计。
- 增加桌面 MCP 管理页、typed client 与 Pinia store。
- 记录真实 CLS smoke 的实际执行状态；运行时不提供假 profile、列表或结果。

## Capabilities

### New Capabilities
- `real-mcp-connections`: 用户连接、真实发现、共享工具来源、Chat 注入及管理界面。

### Modified Capabilities
- 无。Chat 的现有工具生命周期与接口保持兼容。

## Impact

涉及 Alembic、FastAPI、LangChain MCP adapters、Chat Agent、统一审计、接口契约与 Vue 路由。官方 cls-mcp-server 在主机运行；P26 负责启动和凭据细节。本次不实现 AIOps、不支持自定义 headers，不更改前端配置白名单。
