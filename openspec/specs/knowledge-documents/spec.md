## Purpose

为已认证用户提供默认知识库、文档管理和共享切分能力。

## Requirements

### Requirement: 属主限定的默认知识库

应用 SHALL 为每个用户提供唯一、稳定的默认知识库，并从可信认证上下文确定 owner。

#### Scenario: 默认知识库列表

- **WHEN** 已认证用户多次读取知识库列表
- **THEN** 每次都只返回该用户的默认知识库，且 ID 保持一致。

#### Scenario: 跨用户访问

- **WHEN** 用户访问另一用户的知识库
- **THEN** 返回 403，且未认证请求返回 401。

### Requirement: 上传与持久化

应用 SHALL 仅接受不超过 10 MiB 的 UTF-8 Markdown 或 PDF，扩展名与 MIME MUST 匹配。Markdown 接受 `text/markdown` 和 `text/plain`，PDF 接受 `application/pdf`，并使用 pypdf 提取正文。应用 MUST 保存文件名、大小、MIME、SHA-256、上传时间、索引状态、正文和切分配置。原始文件 MUST 留在上传生命周期内。

#### Scenario: 上传格式不合规

- **WHEN** 扩展名、MIME、大小或内容不符合政策
- **THEN** 返回验证错误且不创建文档。

### Requirement: 重复检测与删除

同 owner 和知识库的活跃摘要 MUST 唯一。显式覆盖与普通删除 MUST 软删除旧记录并按 owner、知识库和文档 ID 清理向量。

#### Scenario: 重复上传

- **WHEN** 上传相同摘要且未明确覆盖
- **THEN** 返回 BUSINESS_CONFLICT 409。

#### Scenario: 覆盖或删除

- **WHEN** 属主显式覆盖同摘要文档，或删除自己的文档
- **THEN** 旧文档从列表及详情中消失，向量清理范围限定为旧文档所属的租户、知识库及文档 ID。

#### Scenario: 向量清理失败

- **WHEN** Milvus 清理操作失败
- **THEN** 应用返回失败并回滚 SQLite 写事务，旧文档仍可读取。

### Requirement: 可复用切分与预览

应用 SHALL 提供 fixed-character、markdown-heading 和 paragraph 共用切分入口。仅 fixed-character 接受长度与重叠参数，默认 1200 与 200，重叠 MUST 小于长度。预览 MUST 限制为 12 段，每段至多 400 字符，并返回从零开始、左闭右开的正文字符范围。

#### Scenario: 预览已保存配置

- **WHEN** 请求文档切分预览
- **THEN** 使用该文档保存的配置对正文切分，并按预览上限返回结果。
