## Context

P21 已有诊断报告、证据与 end checkpoint，job 才是诊断终态来源。当前尚无 legacy 保存路由。文档与索引仓储已有 owner 检查、内容摘要去重及 P11 入队机制；索引和检索目前没有文档级来源 metadata。

## Goals / Non-Goals

目标：成功诊断自动、原子、按 source task 幂等沉淀 owner case；保留独立 legacy 手动补充语义；正常索引后可参与下一轮 RAG。

非目标：新增前端页面、改变诊断结论、补造缺失证据、绕过 P11 直接写向量、自动提交推送。

## Decisions

- 新建 aiops_diagnostic_cases，task_id 全局唯一，保存用户指定全部字段及 id；来源任务/报告、文档、索引任务保留 owner 关联。knowledge_documents 新增非空 metadata JSON（历史记录默认空对象），用来保存来源，不额外建立平行文档表。
- 独立 DiagnosisCasePersistor 是自动主路径。JobRepository 支持显式注入的 succeeded hook；只在有效租约将诊断 job 更新为 succeeded 后、事务提交前调用。Persistor 再检查最新诊断 job 为 succeeded、owner task、最终 report 和 end checkpoint；保存当前事务查到的 evidence IDs，允许空列表。
- 成功状态、case、文档、index task 及 index job 原子提交。异常全部回滚，既有 lease recovery/retry 可重试；事务串行化及 task_id 唯一约束保护并发幂等。重复 persist 返回原 case，不重建或重排索引；删除文档不隐式再生案例。
- 扩展 DocumentRepository.add、IndexTasks.create 支持显式外部 transaction；普通 API 保持原语义。自动与 legacy 均调用这些既有仓储；不触碰向量 SDK。索引 worker 仍独立执行，索引失败不会伪装为可检索成功。
- legacy POST /aiops/diagnostics/{id}:save-to-knowledge 在自己的事务中检查当前用户成功诊断和最终报告，直接将脱敏报告保存为文档并入队。它不调用 DiagnosisCasePersistor、不创建结构化 case，按报告内容 SHA256 重复返回 BUSINESS_CONFLICT；与自动路径的 source task 幂等不同。
- 字段从已有 Markdown 报告章节、告警证据和安全查询确定性提取，不再调用 LLM 推测根因。报告不确定性原样保留，缺失字段明确说明未提供。自动文档 knowledgeType=diagnostic-case，保存 sourceDiagnosticTaskId/sourceReportId/sourceEvidenceIds；手动文档使用 diagnostic-report。
- 索引 chunk metadata 及 hybrid retrieval 引用继承文档 metadata，仍按 owner 和 index_status=succeeded 召回。结构化案例 API 仅返回当前 owner 数据。

## Risks / Trade-offs

- 成功收尾事务执行文档写入 → 仅本地 SQLite 操作，无模型、MCP 或向量网络调用；失败回滚后由 durable job 恢复。
- 报告章节缺失或 fallback → 不推断根因，诚实保存原报告与缺失说明；空 evidence IDs 不补造引用。
- 模型报告有不确定性 → case 保留原文和来源，知识沉淀不代表人工核验通过。

## Migration Plan

0012 迁移创建案例表并增加文档 metadata，临时 SQLite 验证 upgrade/downgrade/upgrade 和历史文档默认值。运行 backend/contracts 及项目门禁后核对四维场景，真实服务可用时执行诊断→case→索引→再检索 smoke，否则明确记录未执行，再同步规范与归档。
