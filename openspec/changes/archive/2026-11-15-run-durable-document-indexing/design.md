## Context

P09 已持久化租约和重试，P10 在 SQLite 保存文档正文及切分配置。

## Goals / Non-Goals

实现显式调度、状态查询和恢复，前端提供上传与任务操作。

## Decisions

- 领域记录和作业在同一个 SQLite 事务中提交。通过 owner、resourceType 和 resourceId 关联。
- SQLite 触发器同步作业状态至任务和文档。queued 映射为 pending。每个文档只允许一个活跃任务。
- 重试与重建创建新的领域任务并保存来源。通用取消仍走 P09。
- worker 在嵌入结束后验证租约和文档状态，并在 SQLite 写事务中串行化同一数据库的向量替换和文档删除。
- Milvus 替换由初始化、删除、一次批量写入组成。SQLite 与 Milvus 分别提交，异常后可重试替换。

## Risks / Trade-offs

向量替换期间占用 SQLite 写锁。若进程在外部写入后退出，租约恢复会重新执行替换。
