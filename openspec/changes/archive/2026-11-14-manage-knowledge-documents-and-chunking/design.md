## Context

FastAPI 已提供认证依赖和统一响应，SQLite 由 Alembic 管理，Milvus 已提供按属主、知识库和文档删除的接口。

## Goals / Non-Goals

支持默认知识库与文档生命周期，交付后续索引可直接调用的切分入口。本期范围止于文档和预览。

## Decisions

- 默认知识库由用户 ID 派生。每次访问先校验知识库，再按 owner、KB 和文档 ID 查询 SQLite。
- SQLite 保存提取正文和元数据，部分唯一索引约束活跃文档摘要。删除和覆盖先在写事务中软删除，再清理旧向量，成功后提交。清理失败回滚 SQLite，可重试。
- 上传采用 multipart。Markdown 支持 `text/markdown` 与 `text/plain`，PDF 使用 `application/pdf`。正文提取后保存，原始字节仅用于校验和计算摘要。
- 切分输出附带序号及字符范围，预览消费同一生成器的前 12 项。

## Risks / Trade-offs

SQLite 和 Milvus 之间没有分布式事务。Milvus 删除按旧文档 ID 幂等执行。若 SQLite 提交失败，重试可再次清理；已经删除的向量需要由未来索引流程重建。
