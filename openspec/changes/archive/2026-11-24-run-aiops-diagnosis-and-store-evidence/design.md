## Context

基于现有 JobRepository/JobWorker、KnowledgeRetrieval、McpProvider、AlertAggregator、Qwen provider 和 owner scoped SQLite。模块导入不创建资源，由应用生命周期注入。

## Goals / Non-Goals

目标：有界、可恢复、证据优先诊断，规范化存储及可回放 SSE。非目标：自动执行修复、生成模拟日志、前端诊断工作台、改变主机部署边界。

## Decisions

- StateGraph 固定 START→planner→executor→replanner→(executor|report)→END；节点边界持久化下一节点及有界状态，重启从 checkpoint 继续。最多六步、三次重规划；Planner 提示限定诊断读取。无法保证上游 exactly-once；进程在调用中崩溃时标记不确定失败，不重复调用 SearchLog。
- Planner 首次调用 owner scoped knowledge_retrieval，再发现用户启用 MCP。LLM 返回结构化计划，经服务端验证注册工具、步数及恰好一个 SearchLog；缺失时报 SYSTEM_UNAVAILABLE。工具参数按真实 schema 校验，不虚构默认参数。
- 使用六张规范化表：diagnostic_tasks、diagnostic_steps、diagnostic_evidence、diagnostic_reports、report_evidence_links、graph_checkpoints。计划版本在 checkpoint、步骤分行、证据按引用分行；审计复用 agent_tool_call_audits。
- 任务与 job 同事务创建。诊断状态从最新 job 派生：queued→accepted，其余同名；不另造取消接口。显式 retry 创建新 job，诊断读取最新 job 并恢复已有证据。
- 诊断产物写入通过有效 job lease、owner、无取消标记进行 fencing；步骤完成与证据/引用事件同事务，计划与版本 checkpoint 同事务，报告与关联/checkpoint/事件同事务。通用工具审计按 owner 独立记录调用事实。流仅回放/轮询持久 job events，不绑定执行协程，持久 sequence 为恢复游标。
- 共享 typed task.status 包含 task.message/progress；工具 tool.call、证据 reference.source、报告 report。终态 complete/error 从持久 job 终态派生，不引入 plan/step/replan 事件。
- 模型只输入脱敏 alert/query/SOP/plan/证据，结构化报告字段携带 evidence IDs；服务端验证 ID 属于当前 owner/task，再渲染固定中文 Markdown。模型失败或引用无效使用明确不确定的中文 fallback。每个报告结论与证据建立独立关联。

## Risks / Trade-offs

- 外部读取调用与 SQLite 无分布式事务 → 保留 started 审计及不确定结果，恢复不伪造成功。
- 模型幻觉 → 结构化引用验证、保守提示、fallback；引用存在不代表因果已证明，报告明确不确定性。
- 上游文本含凭据 → 复用 redact，并提取配置 secret 值进行统一脱敏；错误仅存安全代码。

## Migration Plan

Alembic head 增量建表，临时 SQLite 验证 upgrade/downgrade/upgrade。先运行全部门禁，再同步规范和归档。真实 CLS/Qwen smoke 仅在环境具备时执行并明确记录结果。
