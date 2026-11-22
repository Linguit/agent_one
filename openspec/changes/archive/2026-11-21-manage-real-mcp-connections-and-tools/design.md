## Context

当前代码已包含可信 owner、Chat Agent、SQLite 工具审计和 Vue 工作台。P18 在这些实际接口上增加真实 MCP 来源；不根据旧 P01 范围说明宣称其他业务已经验收。

## Goals / Non-Goals

目标：用户隔离的连接管理、真实发现和调用、Chat/AIOps 可复用的 provider、桌面页面。
非目标：AIOps 流程、自定义 headers、服务部署和凭据向导、运行时模拟工具。

## Decisions

- Alembic 0010 建立 mcp_connections，owner 外键、范围约束、时间戳与发现缓存。所有操作带 owner 条件；PUT 清除检查缓存，check 用版本条件写回，避免覆盖并发编辑。
- MCP provider 使用 langchain-mcp-adapters 的客户端在每次请求中发现真实工具。缓存仅用于页面显示，不作为运行工具来源。不同来源同名或与内置工具重名，报明确冲突并终止请求。
- 发现每次尝试受 timeoutSeconds 约束，最多 retries+1 次。工具调用仅一次，受相同超时约束，绝不自动重放可能有副作用的调用。取消向上传递。
- 用户没有任何连接记录时才读取 clsMcpServer.url 真实回退；有禁用记录时不回退，不掩盖失败。配置通过现有 project_config 加载，无模块导入副作用。
- URL 限 http/https、有 host、无 userinfo；保留完整 URL。模型无自定义 headers，因此界面与文档明确禁止 query 中包含 token/secret。异常只暴露固定安全错误类别，不保存原始异常、参数值或工具结果。
- Agent 注入请求 owner 的 enabled 工具并复用现有 tool.call SSE。统一审计改为参数键及占位符、固定安全摘要，禁止记录原始参数和结果。
- 前端 typed client 和串行 Pinia 操作以服务器列表为事实来源，换用户即清空并丢弃旧响应。Vue 仅渲染文本，不渲染服务返回 HTML。

## Risks / Trade-offs

- 远端调用超时后副作用是否完成未知 → 不自动重试调用，明确失败。
- URL 包含 query 会持久化并返回 → 文档和表单禁止放入凭据；不支持 headers。
- 用户 URL 需要访问主机官方服务 → 允许 http/https 主机地址；网络访问权限由部署网络控制。
- 发现重试会增加总等待 → 上限为 (retries+1)*timeoutSeconds，所有次数和超时严格校验。

## Migration Plan

部署前运行 Alembic upgrade head；降级删除连接表。测试使用临时 SQLite。官方 CLS smoke 单独记录，缺少配置、凭据或服务明确未执行，不用单测替身替代。

## Open Questions

无。P26 补充官方服务启动与凭据操作细节。
