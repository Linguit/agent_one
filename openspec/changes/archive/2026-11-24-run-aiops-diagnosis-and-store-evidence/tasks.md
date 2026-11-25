## 1. 持久化与契约

- [x] 1.1 实现六张规范化表及 Alembic 迁移、owner/lease fencing 和 checkpoint 仓储。
- [x] 1.2 定义诊断 API 模型、状态映射及共享 typed SSE task.message/progress。

## 2. 诊断执行

- [x] 2.1 实现 SOP 优先、真实 MCP 发现、恰好一个 SearchLog 的有界 Planner。
- [x] 2.2 实现真实 Executor、证据持久化、审计、Replanner 上限及恢复。
- [x] 2.3 实现中文报告、provenance links、诚实 fallback 和脱敏。
- [x] 2.4 接入 durable worker 和五个 API，事件回放复用 job cancel/retry。

## 3. 验证与交付

- [x] 3.1 覆盖 SOP/no-SOP、工具约束/失败、上限、恢复/取消/重试/超时、checkpoint、规范化证据、报告来源、隔离及脱敏测试。
- [x] 3.2 运行 migration、backend/contracts 及项目全部门禁，修复问题；记录真实 smoke 环境和结果。
- [x] 3.3 完成 verify 报告、spec sync、openspec validate --all、git diff --check 后归档。
