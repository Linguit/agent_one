# P22 验证记录

变更：`persist-and-automate-diagnosis-cases`。验证日期：2026-11-25。

## 验证摘要

| 维度 | 结果 |
| --- | --- |
| 完整性 | proposal/design/specs/tasks 齐备，三项 Requirement、七个 Scenario 均有实现和测试 |
| 正确性 | 成功最终报告、空证据、并发首次创建、回滚重试、legacy 内容去重、owner 隔离、索引及下一轮检索已覆盖 |
| 一致性 | 自动 DiagnosisCasePersistor 与 legacy 路由独立；两者复用现有文档/索引仓储，不直接写向量 |

## 需求与实现映射

| Requirement | 实现证据 | 场景验证 |
| --- | --- | --- |
| 成功诊断自动沉淀案例 | `apps/backend/alembic/versions/0012_diagnostic_cases.py:11`；`diagnosis_case_persistor.py:24`；`diagnostic_case_source.py:23`；`memory/sqlite/jobs.py:325` | `test_success_hook_creates_structured_case_document_and_index`、五组 `test_ineligible_diagnoses_never_create_cases`、`test_empty_evidence_snapshot_and_concurrent_idempotency`、`test_case_failure_rolls_back_success_and_recovers`、`test_worker_completion_automatically_persists_case` |
| 独立 legacy 手动保存 | `apps/backend/src/super_ai/diagnostic_case_api.py:58`，直接调用文档与索引仓储，不调用自动 persistor | `test_legacy_save_and_case_api_are_distinct_and_owner_scoped`：同任务重复及不同任务相同内容均冲突；legacy 不建 case，随后自动 persist 可独立创建结构化文档 |
| 案例查询隔离与检索来源 | `diagnostic_case_api.py:40`、`:48`；`memory/sqlite/diagnostic_cases.py:36`；`document_indexing.py:99`；`knowledge_retrieval.py:125`；`packages/api-contracts/src/diagnostics.ts` | API 测试覆盖另一用户的列表/详情/手动保存与未认证；`test_case_uses_normal_indexer_and_is_retrieved_with_provenance` 覆盖正常 P11 索引、hybrid retrieval、来源 metadata，以及索引前/删除后/其他用户不召回 |

上述测试位于 `apps/backend/tests/test_diagnostic_cases.py`。迁移另由 `test_migration_roundtrip` 检查 upgrade/downgrade/upgrade、历史文档 metadata 默认值和 task_id 唯一约束；报告提取保留不确定性，Markdown 不声称修复已经执行。

## 事务与故障核对

- 诊断 job 在有效租约中更新为 succeeded 后、事务提交前执行显式注入 hook。Persistor 重新检查 owner、最新诊断终态、报告与 end checkpoint。
- 成功状态、case、文档、index task 和 index job 同事务提交；索引入队失败会一起回滚，不留下成功状态或孤立文档。正常索引由 P11 worker 执行，案例创建不代表索引成功。
- 八个并发首次 persist 调用最终只产生一个案例、一份自动文档、一个索引任务；后加证据不改写最初的 evidence_ids 快照。空证据保存空列表。
- legacy 只共享纯读取/metadata helper 及现有基础仓储，与自动路径不共享保存 service，也不共享 source-task 幂等语义。
- 降级采用 SQLite 原地 DROP COLUMN，避免批量重建知识文档表破坏 P11 触发器；迁移往返和既有 P21 迁移测试均通过。

## 门禁结果

- 后端：`uv run ruff check .`、`uv run pyright` 通过；完整 `uv run pytest` 204 项通过。补充跨诊断内容冲突断言后，案例专项 13 项再次通过。
- contracts：typecheck、8 项测试通过。
- frontend：typecheck、39 项测试、build、security 通过。
- 桌面：1440×900 Edge 浏览器检查通过；该测试使用 API 夹具，不代表真实 MCP 验收。
- foundation：6 项通过，含未跟踪文件的空白检查和基础设施边界。
- docs：build、security 通过，两份本机 JSON 请求均为 403。
- `git diff --check` 通过；全量 OpenSpec 验证在同步和归档收尾阶段记录。

已有 MCP 协议测试产生 2 个 `streamable_http_client` 弃用警告，无测试失败。开发者真实配置、凭据和数据库未被修改，原有向量改动保留；P21 解释注释仅为通过 Ruff 做换行。

## 真实 smoke 条件

本次只读检查：Qwen typed 配置有效，但这不代表真实调用通过；本机两个用户启用的 MCP 连接 TCP 均不可达，未配置活跃告警源。因此未执行真实“诊断→case→索引→再检索”端到端 smoke。

测试中的报告/告警 fixture 明确标注测试用途；索引与检索测试仅替换 provider/vector 边界，使用真实 SQLite、P11 DocumentIndexer 和 hybrid KnowledgeRetrieval。测试闭环不作为真实根因或真实外部服务验收结论。

## 分级结论

- CRITICAL：无未解决的实现问题。
- WARNING：真实 smoke 未执行，环境限制已如实记录，不使用替身补验。
- SUGGESTION：无归档前额外要求。

完整性、正确性、一致性均已核对，没有跳过 artifact 检查。按用户授权在全部门禁通过后同步规范和归档；不提交或推送代码。

## 归档收尾

主规范已同步三项要求及七个场景；归档前 `openspec validate --all` 27/27 通过，`git diff --check` 通过。9/9 任务完成，归档命令保留验证并跳过重复 spec 写入。

已归档至 `openspec/changes/archive/2026-11-25-persist-and-automate-diagnosis-cases`。归档后 `openspec validate --all` 26/26 通过、`git diff --check` 通过；9/9 任务、`.openspec.yaml` 及主规范与 delta 一致性均已核对。OpenSpec 遥测上报网络超时不影响规范验证结果。
