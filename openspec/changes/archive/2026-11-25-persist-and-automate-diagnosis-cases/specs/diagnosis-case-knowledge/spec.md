## ADDED Requirements

### Requirement: 成功诊断自动沉淀案例
系统 SHALL 由独立 DiagnosisCasePersistor 在诊断成功完成时按 source task 幂等创建 owner scoped 结构化 case、knowledgeType=diagnostic-case 的 Markdown 文档和 P11 durable index task。aiops_diagnostic_cases MUST 保存 owner_user_id、唯一 task_id、report_id、document_id、index_task_id、alert_name、service、keywords、root_cause、remediation、summary、evidence_ids、created_at。

#### Scenario: 成功最终报告
- **WHEN** 当前 owner 的诊断 job 确认为 succeeded 且存在成功最终报告
- **THEN** 同事务创建 case、知识文档和索引任务，并保存当时查到的 evidence IDs

#### Scenario: 不合格诊断与空证据
- **WHEN** 诊断失败、取消、没有最终报告，或成功报告的 evidence IDs 为空
- **THEN** 前三种不创建案例，最后一种诚实保存空列表，不补造证据

#### Scenario: 并发幂等与收尾恢复
- **WHEN** 同一个 source task 并发重复持久化或收尾事务中断重试
- **THEN** 最终至多一条 case、一份自动文档和一个索引任务，不留下部分提交产物

### Requirement: 独立 legacy 手动保存
系统 SHALL 提供 POST /aiops/diagnostics/{id}:save-to-knowledge，仅允许保存当前 user 的 succeeded diagnosis 最终报告。此路径 MUST 直接创建知识文档和索引任务，不调用自动 persistor、不创建 structured case；重复内容返回 BUSINESS_CONFLICT。

#### Scenario: 手动补充与重复
- **WHEN** 用户手动保存成功报告或重复保存相同内容
- **THEN** 首次直接创建文档及索引任务且不创建 case，重复返回冲突且不增加任务

#### Scenario: 跨用户和未成功诊断
- **WHEN** 请求其他用户的诊断或未成功的诊断
- **THEN** 拒绝保存，不泄漏其他 owner 数据或产生文档

### Requirement: 案例查询隔离与检索来源
系统 SHALL 提供 GET /aiops/diagnostic-cases、GET /aiops/diagnostic-cases/{id} 和共享 contracts，全部 owner scoped。结构化字段与 Markdown MUST 仅从已有真实 report/evidence 提取并保留不确定性；文档与检索引用 MUST 保存 source diagnosis/report/evidence metadata。

#### Scenario: owner 查询
- **WHEN** 当前用户列出或读取案例
- **THEN** 仅可见自己的案例，其他用户读取返回不存在

#### Scenario: 下一轮 RAG
- **WHEN** 案例经 P11 正常索引成功后，owner 再次检索相关故障
- **THEN** 案例可被 hybrid knowledge_retrieval 命中并带来源 metadata；索引前、删除后或其他用户不可召回
