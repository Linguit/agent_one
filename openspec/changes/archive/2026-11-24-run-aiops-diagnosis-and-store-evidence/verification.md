# P21 验证记录

变更：`run-aiops-diagnosis-and-store-evidence`。验证日期：2026-11-24。

## 验证摘要

| 维度 | 结果 |
| --- | --- |
| 完整性 | 四类 artifacts 完整，四项 Requirement 均有实现与测试 |
| 正确性 | SOP/no-SOP、真实工具注册约束、失败、上限、恢复、取消/重试/超时、规范化证据、报告引用及隔离已覆盖 |
| 一致性 | 使用现有 owner、durable jobs、MCP、检索、Qwen 与共享 SSE；没有诊断专用取消接口或 plan/step/replan 事件 |

## 实现与场景映射

| Requirement | 实现证据 | 场景验证 |
| --- | --- | --- |
| 有界且真实的诊断图 | `apps/backend/src/super_ai/diagnostic_runtime.py:88`（计划校验）、`:153`（真实调用）、`:257`（StateGraph）；`diagnostic_contracts.py:5`（六步、三次重规划） | `test_graph_real_constraints_normalization_fallback`、`test_missing_searchlog_explicit_failure`、`test_plan_rejects_unknown_duplicate_and_bad_schema`、`test_replan_bound_and_restart_does_not_repeat_log` |
| 规范化证据与恢复 | `apps/backend/alembic/versions/0011_aiops_diagnostics.py`；`memory/sqlite/diagnostics.py:37`（原子创建）、`:145`（证据链含审计）、`:184`（lease/owner/cancel fencing） | `test_worker_lease_restart_resumes_completed_evidence`、`test_worker_timeout_persists_failed_status`、`test_cancel_fences_report_and_retry`、`test_migration_roundtrip_and_composite_links`、`test_mcp_log_blocks_are_split_and_error_is_not_evidence` |
| 诊断 API 与持久 SSE | `apps/backend/src/super_ai/diagnostic_api.py:29`（创建）、`:46`（详情）、`:52`（证据链）、`:75`（持久事件回放）；`packages/api-contracts/src/diagnostics.ts` | `test_worker_survives_client_disconnect_and_stream_replay` 覆盖创建后断开、后台完成、序号恢复、认证和另一用户的详情/证据链/流拒绝；contracts 诊断测试覆盖状态映射 |
| 中文报告与来源关联 | `apps/backend/src/super_ai/diagnostic_report.py:15`；模型结论校验当前任务 evidence IDs 及对应告警；报告、关联、终态 checkpoint、report 事件同事务写入 | `test_report_provenance_rejects_invented_evidence`、`test_multiple_alerts_keep_distinct_report_sections`、fallback 参数化测试 |

上述测试均位于 `apps/backend/tests/test_diagnostics.py`。测试仅在 provider 边界提供替身；测试记录明确标注测试用途，不作为真实产品根因证据。没有用 mock 日志宣称真实诊断成功。

## 门禁

- Alembic 临时 SQLite：upgrade head → downgrade 0010 → upgrade head，复合 report/evidence 外键检查通过；未修改开发者真实数据库结构。
- 后端：Ruff、strict Pyright 通过；完整 pytest 191 项通过。最后的诊断局部修复另运行 15 项诊断测试。
- contracts：typecheck 及 7 项测试通过。
- frontend：typecheck、39 项测试、build、security 通过。
- frontend:desktop：Edge 1440×900 布局、溢出、控制台及访问边界检查通过；浏览器 API 夹具不代表真实 MCP 验收。
- foundation:test：6 项通过；docs:build、docs:security 通过。
- OpenSpec 全量验证和差异空白检查在归档前后执行；最终结果以归档收尾记录为准。

后端现有 MCP 协议测试产生 2 个 `streamable_http_client` 弃用警告，未出现测试失败。

## 真实 smoke 与恢复边界

当前本机存在 2 个用户启用的 MCP 连接，两个地址的 TCP 连通性检查均失败；部署配置未设置活跃告警源。因此未执行 CLS MCP + Qwen 端到端 smoke，也未声称真实日志查询或真实根因分析验收通过。Qwen 配置存在不代表调用已通过。

外部调用与 SQLite 无分布式事务：worker 在调用中断时保留不确定结果，恢复将 started 步骤标记失败，不重复 SearchLog；报告明确不确定性。模型引用存在只能证明来源可追溯，不能单独证明因果。无日志、模型失败、无效引用均使用诚实 fallback。

## 问题分级

- CRITICAL：无未解决的实现问题。
- WARNING：真实端到端 smoke 未执行，原因及环境检查如上；不使用替身补验。
- SUGGESTION：无额外归档前要求。

完整性、正确性、一致性检查均已执行，没有跳过 artifact 核对。规范同步与归档按用户授权在门禁通过后执行，不提交或推送代码。

## 归档收尾

主规范 `openspec/specs/aiops-diagnosis/spec.md` 已同步四项要求；归档前 `openspec validate --all` 26/26 通过，`git diff --check` 通过，9/9 任务完成。归档命令保留验证并跳过重复 spec 写入。

已归档至 `openspec/changes/archive/2026-11-24-run-aiops-diagnosis-and-store-evidence`。归档后全量规范验证 25/25 通过、`git diff --check` 通过；已核对 9/9 任务、`.openspec.yaml` 保留和主规范/delta 一致。OpenSpec 遥测上报出现网络超时，规范验证本身成功。
