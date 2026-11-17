## ADDED Requirements

### Requirement: 显式调度与持久记录

上传 SHALL 仅创建文档，客户端随后显式创建索引任务。系统 SHALL 在一个 SQLite 事务中创建领域任务和持久作业。

#### Scenario: 上传后创建任务

- **WHEN** 上传完成并由客户端创建索引任务
- **THEN** 任务关联已认证用户的文档，客户端可查询状态，断开连接后任务继续执行。

### Requirement: 完整索引与有序嵌入

worker SHALL 读取属主文档并复用 P10 切分。Qwen 嵌入请求每批 MUST 至多 10 段且保持顺序。worker MUST 初始化 Milvus、按属主删除旧向量并一次写入全部向量和来源元数据。

#### Scenario: 文档超过十段

- **WHEN** 文档切出超过十段
- **THEN** 嵌入按顺序分批，Milvus 一次写入全部向量记录。

### Requirement: 重试重建取消与恢复

系统 SHALL 持久化 pending、running、succeeded、failed 和 cancelled。重试或重建 MUST 创建新任务并记录来源，失败原因 MUST 使用安全消息。

#### Scenario: 任务失败或 worker 重启

- **WHEN** 作业失败或租约过期
- **THEN** 按持久作业策略重试或终结，文档状态与领域任务同步。

#### Scenario: 手动重试与重建

- **WHEN** 属主对终态任务发起重试或重建
- **THEN** 产生新的任务 ID，保存来源 ID，且同一文档只有一个活跃任务。

#### Scenario: 取消运行中的任务

- **WHEN** 属主在向量提交前取消索引
- **THEN** worker 停止执行，领域任务和文档状态更新为 cancelled。
