## ADDED Requirements

### Requirement: 有界且真实的诊断图
系统 SHALL 使用 START→planner→executor→replanner→(executor|report)→END 的 LangGraph，最多六个步骤、三次重规划。Planner MUST 先检索 owner scoped SOP，再发现用户 enabled MCP，最终计划仅含注册工具且恰好一个真实 SearchLog 类步骤。

#### Scenario: 有 SOP 或无 SOP
- **WHEN** 检索返回知识片段或空结果
- **THEN** 系统保存实际知识证据或明确无 SOP，并基于 alert/query 规划，不创建虚假 SOP

#### Scenario: 工具缺失或计划无效
- **WHEN** 用户无 SearchLog、计划包含未知工具或重复 SearchLog
- **THEN** 任务明确失败并持久化安全错误，缺失工具使用 SYSTEM_UNAVAILABLE

#### Scenario: 工具失败与重规划上限
- **WHEN** 工具调用失败或达到步骤/重规划上限
- **THEN** 保存真实失败，Replanner 根据已有证据继续或报告，不补造成功且不会无限循环

### Requirement: 规范化证据与恢复
系统 SHALL 使用 durable job 后台执行并持久化安全输入、版本计划、步骤、工具审计、分类证据、checkpoint、报告和 report_evidence_links。所有记录 MUST owner scoped，执行期间的诊断产物写入 MUST 受有效 lease 和取消 fencing 保护，工具审计独立记录调用事实。

#### Scenario: 断开与 worker 重启
- **WHEN** 客户端断开或 worker 在节点边界重启
- **THEN** 后台任务继续或从 SQLite checkpoint 恢复，已完成步骤不重复；未完成外部调用明确标记不确定

#### Scenario: 取消重试超时
- **WHEN** 使用后台任务 cancel/retry 或发生超时
- **THEN** 诊断状态及事件与最新后台任务一致，取消后不能写入成功报告

#### Scenario: 隔离与脱敏
- **WHEN** 其他用户请求详情、证据链、流或输入包含凭据
- **THEN** 不泄漏其他 owner 记录，持久化和输出均脱敏

### Requirement: 诊断 API 与持久 SSE
系统 SHALL 提供 POST/GET /aiops/diagnostics、GET /aiops/diagnostics/{id}、GET /aiops/diagnostics/{id}/evidence-chain、POST /aiops/diagnostics/{id}:stream。创建返回 backgroundJob。诊断 accepted/running/succeeded/failed/cancelled 分别映射 job queued/running/succeeded/failed/cancelled。取消和重试 MUST 复用后台任务 API。

#### Scenario: 事件回放
- **WHEN** 客户端携带持久 sequence 恢复流
- **THEN** 按顺序返回后续事件，使用 task.status/task.message/progress、tool.call、reference.source、report、complete/error，不生成 plan/step/replan 类型

### Requirement: 中文报告与来源关联
系统 SHALL 仅依据 alert、SOP、plan、真实 evidence 渲染固定结构：# 告警分析报告、## 📋 活跃告警清单、逐条 ## 🔍 告警根因分析N（详情/症状/日志证据/根因结论）、## 🛠️ 处理方案执行N（已执行步骤/建议/预期效果）、## 📊 结论（整体评估/关键发现/后续建议/风险评估）。关键结论 MUST 通过独立 report_evidence_links 关联真实证据，证据不足标注不确定性。

#### Scenario: 模型失败或证据不足
- **WHEN** 报告模型失败、引用无效或无日志结果
- **THEN** 使用基于已存证据的结构化中文 fallback，明确无法确认根因，绝不伪造根因或工具结果
