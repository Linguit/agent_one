## Why

现有后台任务、知识检索、真实 MCP 与活跃告警需要组合为可恢复、可审计的诊断流程。诊断结论必须建立在真实证据上，客户端断开不应中止执行。

## What Changes

- 新增有界 LangGraph Planner → Executor → Replanner → Report，先检索 SOP 再发现当前用户工具，严格保留一个 SearchLog 步骤。
- 新增 owner scoped 诊断、步骤、证据、报告关联和 checkpoint，复用 durable jobs、通用工具审计和共享 SSE。
- 新增诊断创建、列表、详情、证据链与流 API；取消和重试复用后台任务 API。
- 输出固定中文报告，证据不足或模型失败时诚实降级；禁止伪造日志和根因。

## Capabilities

### New Capabilities
- `aiops-diagnosis`: 可恢复诊断、规范化证据链、中文报告及事件恢复。

### Modified Capabilities
无。

## Impact

涉及后端生命周期、SQLite/Alembic、后台任务与共享接口契约；复用 Qwen、知识检索、真实 MCP 和告警聚合。测试使用显式 provider 替身，真实 CLS/Qwen 验收单独记录，不自动提交或推送。
