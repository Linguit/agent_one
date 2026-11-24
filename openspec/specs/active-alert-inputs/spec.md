# active-alert-inputs

## Purpose

为后续诊断提供 deployment-global 真实标准化告警输入。

## Requirements

### Requirement: 全局真实告警聚合
系统 SHALL 从 deployment-global prometheusAlerts.sources 的 prometheus-v1 / alertmanager-v2 API 异步读取，支持 basicAuth 和 timeout，每条包含 alertname/service/severity/status/startsAt/labels/annotations/source/raw，不生成诊断或默认告警。

#### Scenario: 两类真实响应标准化
- **WHEN** 两类源返回有效 payload
- **THEN** 返回保留原生状态和源名称的标准 items，敏感信息脱敏

#### Scenario: 部分失败
- **WHEN** 一个源超时或响应无效，另一个源成功
- **THEN** 保留成功源的 items，不返回 provider 状态集合

#### Scenario: 全失败
- **WHEN** 所有源失败或未配置源
- **THEN** 返回固定脱敏 503 错误，不构造默认告警

### Requirement: 认证告警接口与无启动副作用
系统 SHALL 为 GET /aiops/alerts/active 定义认证、标准 DTO、401/403 契约；导入及普通启动不得读取告警 API 或上传 CLS。

#### Scenario: 未认证访问
- **WHEN** 请求无有效认证
- **THEN** 返回 401 且不调用告警源

#### Scenario: 全局源授权
- **WHEN** 已认证用户请求活跃告警
- **THEN** 读取相同 deployment-global 源，不接受客户端自报 owner 或源地址

#### Scenario: 普通启动
- **WHEN** 导入模块或启动应用
- **THEN** 不调用告警 API 或 CLS SDK
