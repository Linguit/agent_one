## ADDED Requirements

### Requirement: 独立安全 CLS 日志上传
工具 SHALL 使用官方 tencentcloud-cls-sdk-python，从本地 JSON 加载凭据；通过 endpoint 路由的 LogClient 调用 put_log_raw(topicId, groups)。region 保留于配置和每条日志，logsetId 仅人工关联。日志为固定无敏感信息结构，count 范围 1..1000。

#### Scenario: 生成预览
- **WHEN** 不指定上传确认参数
- **THEN** 仅生成日志并输出数量，不创建 SDK 客户端、不打印 secret

#### Scenario: 显式确认上传
- **WHEN** 操作者提供自己的凭据并显式确认 endpoint/topic，且 count 有效
- **THEN** 向该 endpoint/topic 上传有界日志，region 不改变客户端路由

#### Scenario: 非法参数或导入
- **WHEN** endpoint/count 无效，或只导入脚本
- **THEN** 不上传、不泄漏配置值
