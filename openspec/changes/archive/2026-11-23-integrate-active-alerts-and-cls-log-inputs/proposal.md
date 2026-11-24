## Why

P20 为后续 P21 诊断提供真实告警与日志输入，避免演示数据混入生产输入。CLS 写入必须由操作者明确选择目标后独立执行。

## What Changes

- 新增 deployment-global Prometheus v1 / Alertmanager v2 告警聚合、认证 API 与标准契约。
- 新增有界、脱敏、显式确认的独立 CLS 日志生成上传工具。
- 单源失败保留其他真实结果，全失败返回 503；不生成诊断或 provider 状态集合。

## Capabilities

### New Capabilities
- `active-alert-inputs`: 真实告警配置、标准化与认证读取。
- `cls-log-inputs`: 安全独立的 CLS 日志生成与上传。

### Modified Capabilities

无。

## Impact

后端 httpx provider、认证路由、共享 DTO、配置模板、官方 CLS SDK、独立脚本及测试。复用既有配置、认证和基础设施，不创建用户拥有的告警源，不自动调用外部写入。
