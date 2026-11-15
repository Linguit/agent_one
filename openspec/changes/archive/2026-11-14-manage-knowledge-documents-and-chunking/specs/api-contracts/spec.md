## ADDED Requirements

### Requirement: 知识库文档接口契约

共享契约与 OpenAPI SHALL 登记默认知识库、文档列表与上传、文档详情与删除和切分预览，定义文档 DTO、上传政策、multipart 参数及 401、403 和重复冲突响应。

#### Scenario: 检查上传接口

- **WHEN** 客户端读取文档上传契约
- **THEN** 可以确定文件字段、策略参数和显式覆盖语义。
