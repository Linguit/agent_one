## Why

诊断报告与证据已经持久化，但尚未自动进入知识检索。需要把成功完成的诊断沉淀为可追溯、owner scoped 的结构化案例，通过现有索引任务进入下一轮 RAG。

## What Changes

- 增加结构化诊断案例表及 owner scoped 列表、详情 API。
- 独立 DiagnosisCasePersistor 在诊断成功收尾时，按 source task 幂等创建案例、Markdown 知识文档和 durable index task。
- 补齐 legacy 显式保存接口；它按文档内容去重，重复返回 BUSINESS_CONFLICT，不创建结构化案例。
- 知识文档与检索引用保留 knowledgeType、source diagnosis/report/evidence metadata。

## Capabilities

### New Capabilities
- `diagnosis-case-knowledge`: 成功诊断的自动案例沉淀、legacy 手动保存、owner 查询及后续检索来源。

### Modified Capabilities
无；通过新增案例能力复用现有文档与 durable indexing，不改变普通上传语义。

## Impact

涉及 Alembic、诊断完成事务、文档/索引仓储的事务组合、检索引用 metadata、后端 API 和共享契约。保留既有本地向量改动，不自动提交或推送；无前端页面变更。
